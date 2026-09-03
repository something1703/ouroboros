"""Model Armor screening for every untrusted-text path (AGENTS.md §6.6): ingested script/
video text, Parallel web excerpts, and Parallel Task outputs.

Endpoint verified against real Google Cloud docs (2026-09-03): sanitize calls need a
*regional* endpoint (`modelarmor.{region}.rep.googleapis.com`) — the global
`modelarmor.googleapis.com` endpoint only serves getFloorSetting/updateFloorSetting.
"""

from __future__ import annotations

import os
from functools import cache
from typing import Literal

from google.cloud import modelarmor_v1
from pydantic import BaseModel

from packages.common.errors import SafetyBlocked
from packages.common.logging import get_logger

ScreenContext = Literal["ingest", "web_excerpt", "task_output"]

TEMPLATE_ID = "ouroboros-default"

log = get_logger(__name__)


class ScreenResult(BaseModel):
    text: str  # unchanged, or with flagged spans stripped
    flagged: bool
    detected_categories: list[str]


def _region() -> str:
    return os.environ.get("OUROBOROS_REGION", "us-central1")


@cache
def _client() -> modelarmor_v1.ModelArmorClient:
    return modelarmor_v1.ModelArmorClient(
        client_options={"api_endpoint": f"modelarmor.{_region()}.rep.googleapis.com"}
    )


def _template_name() -> str:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    return modelarmor_v1.ModelArmorClient.template_path(project, _region(), TEMPLATE_ID)


def screen(text: str, context: ScreenContext) -> ScreenResult:
    """Screen `text` for prompt injection/jailbreak (blocking on high confidence) and PII
    (log only, per PHASE_03.md §3.4 — PII is expected in real scripts/transcripts and
    must never block ingest). Raises SafetyBlocked on a high-confidence PI/jailbreak
    match; otherwise returns a possibly-flagged result and the caller continues.
    """
    request = modelarmor_v1.SanitizeUserPromptRequest(
        name=_template_name(),
        user_prompt_data=modelarmor_v1.DataItem(text=text),
    )
    response = _client().sanitize_user_prompt(request=request)
    result = response.sanitization_result

    if result.filter_match_state != modelarmor_v1.FilterMatchState.MATCH_FOUND:
        return ScreenResult(text=text, flagged=False, detected_categories=[])

    detected: list[str] = []
    hard_block = False
    match_found = modelarmor_v1.FilterMatchState.MATCH_FOUND

    # `result.filter_results` has one entry per *configured* filter regardless of
    # whether it matched — found live: an earlier version of this function treated
    # mere presence of a filter's key as a match, hard-blocking every single call once
    # more than one filter was configured (malicious_uri/csam entries were always
    # present at NO_MATCH_FOUND). Every branch below checks that filter's own
    # match_state explicitly; nothing here infers a match from a key's presence.
    for filter_name, filter_result in result.filter_results.items():
        pi = filter_result.pi_and_jailbreak_filter_result
        if pi.match_state == match_found:
            detected.append(filter_name)
            if pi.confidence_level == modelarmor_v1.DetectionConfidenceLevel.HIGH:
                hard_block = True
            continue

        # SDP (Sensitive Data Protection / PII) is log-only — never blocks ingest;
        # real scripts/transcripts legitimately contain real people's names, etc.
        sdp = filter_result.sdp_filter_result
        if sdp.inspect_result.match_state == match_found:
            detected.append(filter_name)
            continue

        # RAI, malicious URI, CSAM, virus scan: all four share a top-level
        # match_state field. Any real match here is treated as a hard block — none of
        # these are expected in legitimate production material.
        for sub_result in (
            filter_result.rai_filter_result,
            filter_result.malicious_uri_filter_result,
            filter_result.csam_filter_filter_result,
            filter_result.virus_scan_filter_result,
        ):
            if sub_result.match_state == match_found:
                detected.append(filter_name)
                hard_block = True
                break

    log.warning(
        "model_armor_match",
        context=context,
        categories=detected,
        hard_block=hard_block,
    )

    if hard_block:
        raise SafetyBlocked(context, f"Model Armor matched: {', '.join(detected)}")

    return ScreenResult(text=text, flagged=True, detected_categories=detected)
