"""Responses API wrapper. Not exposed by the `parallel` SDK — called via the `openai`
SDK pointed at Parallel's base URL, `model="parallel"` (docs/vendor/parallel/README.md,
PARALLEL_INTEGRATION.md §4.3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache

import openai
from openai import OpenAI

from config.parallel import RESPONSES_EFFORT_DEFAULT, ResponsesEffort
from packages.claims.models import Citation
from packages.parallel_client.client import call
from packages.parallel_client.specs.loader import SPECS

_RESPONSES_RETRYABLE: tuple[type[Exception], ...] = (
    openai.RateLimitError,
    openai.InternalServerError,
    openai.APITimeoutError,
    openai.APIConnectionError,
)


@cache
def _client() -> OpenAI:
    from packages.common.secrets import get_secret

    return OpenAI(api_key=get_secret("PARALLEL_API_KEY"), base_url="https://api.parallel.ai/v1")


@dataclass(frozen=True)
class ResponsesResult:
    answer: dict[str, object]
    citations: list[Citation]


def ask(
    question: str,
    *,
    schema: str = "factual_quick",
    effort: ResponsesEffort = RESPONSES_EFFORT_DEFAULT,
    claim_id: str | None = None,
) -> ResponsesResult:
    schema_json = SPECS[schema]

    def _call() -> object:
        return _client().responses.create(
            model="parallel",
            input=question,
            reasoning={"effort": effort},
            text={"format": {"type": "json_schema", "name": schema, "schema": schema_json}},
        )

    sku = f"responses.{effort}"
    response = call(
        _call,
        api="responses",
        sku=sku,
        claim_id=claim_id,
        retryable_errors=_RESPONSES_RETRYABLE,
        status_error=openai.APIStatusError,
    )

    answer: dict[str, object] = json.loads(response.output_text)  # type: ignore[attr-defined]

    now = datetime.now(UTC)
    citations: list[Citation] = []
    for item in response.output:  # type: ignore[attr-defined]
        if getattr(item, "type", None) != "message":
            continue
        for part in item.content:
            for annotation in getattr(part, "annotations", None) or []:
                url = getattr(annotation, "url", None)
                if url:
                    citations.append(Citation(url=url, excerpt=None, retrieved_at=now))

    return ResponsesResult(answer=answer, citations=citations)
