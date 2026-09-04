"""Task wrapper + specs. See PARALLEL_INTEGRATION.md §4.2 and docs/vendor/parallel/README.md."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TypedDict

from config.parallel import (
    FORBIDDEN_TASK_PROCESSOR_PREFIXES,
    TASK_DEFAULT_TIMEOUT_S,
    TASK_MAX_INPUT_CHARS,
    TASK_PROCESSOR_DEFAULT,
    TASK_SPEC_PLUS_INPUT_MAX_CHARS,
)
from packages.claims.enums import Confidence
from packages.claims.models import FieldBasis
from packages.parallel_client.basis import overall_confidence, parse_basis
from packages.parallel_client.client import call, env_metadata, get_client
from packages.parallel_client.specs.loader import SPECS


class McpServer(TypedDict, total=False):
    type: str
    name: str
    url: str
    headers: dict[str, str]
    allowed_tools: list[str]


@dataclass(frozen=True)
class TaskResult:
    run_id: str
    content: dict[str, object] | str
    basis: list[FieldBasis]
    overall_confidence: Confidence
    processor: str


@dataclass(frozen=True)
class RunHandle:
    """A Task run that hasn't completed yet (`wait=False`) — completion arrives via
    webhook (`task_run.status` events, PARALLEL_INTEGRATION.md §5)."""

    run_id: str


def build_input(
    claim_text: str, *, jurisdictions: list[str], excerpt: str, top_urls: list[str]
) -> str:
    codes = ", ".join(jurisdictions)
    urls = ", ".join(top_urls[:5])
    text = f"{claim_text}\nJurisdictions: {codes}\nContext: {excerpt}\nHints: {urls}"
    return text[:TASK_MAX_INPUT_CHARS]


def _fit_spec_and_input(spec_json: dict[str, Any], task_input: str, *, name: str) -> str:
    """PARALLEL_INTEGRATION.md §3: spec + input <= 25k chars; truncate `input` first
    (search-URL hints) if it doesn't fit — never silently drop the spec."""
    spec_len = len(json.dumps(spec_json))
    overflow = spec_len + len(task_input) - TASK_SPEC_PLUS_INPUT_MAX_CHARS
    if overflow <= 0:
        return task_input
    if overflow >= len(task_input):
        raise ValueError(f"spec {name!r} alone exceeds the spec+input budget")
    return task_input[: len(task_input) - overflow]


def run(
    task_input: str,
    spec: str,
    *,
    claim_id: str,
    project_id: str,
    cycle: int = 1,
    processor: str = TASK_PROCESSOR_DEFAULT,
    mcp_servers: list[McpServer] | None = None,
    previous_interaction_id: str | None = None,
    memory_scope_key: str | None = None,
    wait: bool = True,
    timeout_s: int = TASK_DEFAULT_TIMEOUT_S,
) -> TaskResult | RunHandle:
    if any(processor.startswith(prefix) for prefix in FORBIDDEN_TASK_PROCESSOR_PREFIXES):
        raise ValueError(f"processor {processor!r} is forbidden in the pipeline")

    spec_json = SPECS[spec]
    task_input = _fit_spec_and_input(spec_json, task_input, name=spec)
    metadata: dict[str, str | float | bool] = dict(
        env_metadata(project_id=project_id, claim_id=claim_id, cycle=str(cycle), spec=spec)
    )
    sku = f"task.{processor}"

    def _create() -> object:
        return get_client().task_run.create(
            input=task_input,
            processor=processor,
            task_spec={"output_schema": {"type": "json", "json_schema": spec_json}},
            metadata=metadata,
            mcp_servers=mcp_servers,  # type: ignore[arg-type]
            previous_interaction_id=previous_interaction_id,
            memory_scope_key=memory_scope_key,
        )

    task_run = call(_create, api="task", sku=sku, claim_id=claim_id)
    run_id: str = task_run.run_id  # type: ignore[attr-defined]

    if not wait:
        return RunHandle(run_id=run_id)

    def _result() -> object:
        return get_client().task_run.result(run_id, api_timeout=timeout_s)

    result = call(_result, api="task_result", sku=sku, claim_id=claim_id)
    output = result.output  # type: ignore[attr-defined]
    basis = parse_basis(output.basis)
    required_fields = list(spec_json["properties"].keys())
    confidence = overall_confidence(basis, required_fields=required_fields)

    return TaskResult(
        run_id=run_id,
        content=output.content,
        basis=basis,
        overall_confidence=confidence,
        processor=processor,
    )


def should_escalate(evidence_confidence: Confidence, priority: int) -> bool:
    """ADK_AGENTS.md §2.2 step 6: escalate to `processor=pro` only when confidence is
    low on a high-priority claim — escalation is data-driven, not automatic."""
    return evidence_confidence == Confidence.LOW and priority <= 2
