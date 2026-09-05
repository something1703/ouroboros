"""Extract wrapper. Cap 5 URLs per claim; Model Armor screens every excerpt and the
full-content markdown before either reaches a prompt (PARALLEL_INTEGRATION.md §4.5).
"""

from __future__ import annotations

from pydantic import BaseModel

from packages.common.errors import SafetyBlocked
from packages.common.logging import get_logger
from packages.parallel_client.client import call, get_client

log = get_logger(__name__)

_MAX_URLS = 5


class ExtractHit(BaseModel):
    url: str
    title: str | None
    markdown: str | None
    excerpts: list[str]


def extract(
    urls: list[str],
    *,
    objective: str,
    full_content: bool = False,
    claim_id: str | None = None,
) -> list[ExtractHit]:
    capped = urls[:_MAX_URLS]
    if len(urls) > _MAX_URLS:
        log.warning(
            "extract_urls_truncated", requested=len(urls), used=_MAX_URLS, claim_id=claim_id
        )

    def _call() -> object:
        return get_client().extract(
            urls=capped,
            objective=objective,
            advanced_settings={"full_content": full_content},
        )

    response = call(_call, api="extract", sku="extract", claim_id=claim_id)

    hits: list[ExtractHit] = []
    for result in response.results:  # type: ignore[attr-defined]
        markdown = (
            _screened(result.full_content, claim_id=claim_id) if result.full_content else None
        )
        excerpts = [
            text
            for excerpt in result.excerpts
            if (text := _screened(excerpt, claim_id=claim_id)) is not None
        ]
        hits.append(
            ExtractHit(url=result.url, title=result.title, markdown=markdown, excerpts=excerpts)
        )
    return hits


def _screened(text: str, *, claim_id: str | None) -> str | None:
    from packages.safety.model_armor import screen

    try:
        return screen(text, context="web_excerpt").text
    except SafetyBlocked as exc:
        log.warning("extract_content_dropped_by_safety", reason=exc.reason, claim_id=claim_id)
        return None
