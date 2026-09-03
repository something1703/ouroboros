"""Search wrapper. See PARALLEL_INTEGRATION.md §4.1 and docs/vendor/parallel/README.md
for the real (corrected) request shape: `location`/`max_results` nest under
`advanced_settings`; `exclude_domains`/`include_domains`/`after_date` nest under
`advanced_settings.source_policy`.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from config.parallel import (
    DEFAULT_EXCLUDE_DOMAINS_LEGAL,
    JURISDICTIONS,
    SEARCH_MODE_DEFAULT,
    SUPPORTED_LOCATIONS,
    SearchMode,
)
from packages.claims.enums import LEGAL_CATEGORIES, ClaimCategory
from packages.common.logging import get_logger
from packages.parallel_client.client import call, get_client

log = get_logger(__name__)


class SearchHit(BaseModel):
    url: str
    title: str | None
    publish_date: str | None
    excerpts: list[str]


class SearchResult(BaseModel):
    hits: list[SearchHit]
    search_id: str
    session_id: str


def search(
    objective: str | None,
    queries: list[str],
    *,
    mode: SearchMode = SEARCH_MODE_DEFAULT,
    location: str | None = None,
    exclude_domains: list[str] | None = None,
    after_date: date | None = None,
    max_results: int = 10,
    session_id: str | None = None,
    category: ClaimCategory | None = None,
    claim_id: str | None = None,
) -> SearchResult:
    """`queries`: 1-3 concise (3-6 word) search queries — required by the real API even
    though `objective` is optional. `category`: when given and in `LEGAL_CATEGORIES`,
    `exclude_domains` defaults to `DEFAULT_EXCLUDE_DOMAINS_LEGAL` unless explicitly
    overridden (PARALLEL_INTEGRATION.md §4.1 — legal-category noise, not signal;
    factual searches get no default exclusion).
    """
    if exclude_domains is None and category is not None and category in LEGAL_CATEGORIES:
        exclude_domains = DEFAULT_EXCLUDE_DOMAINS_LEGAL

    advanced_settings: dict[str, object] = {"max_results": max_results}
    if location is not None:
        if location in SUPPORTED_LOCATIONS:
            advanced_settings["location"] = location
        else:
            log.warning("search_location_unsupported", location=location, claim_id=claim_id)

    source_policy: dict[str, object] = {}
    if exclude_domains:
        source_policy["exclude_domains"] = exclude_domains
    if after_date is not None:
        source_policy["after_date"] = after_date.isoformat()
    if source_policy:
        advanced_settings["source_policy"] = source_policy

    def _call() -> object:
        return get_client().search(
            search_queries=queries,
            objective=objective,
            mode=mode,
            advanced_settings=advanced_settings,  # type: ignore[arg-type]
            session_id=session_id,
        )

    sku = f"search.{mode}"
    raw = call(_call, api="search", sku=sku, claim_id=claim_id)

    hits = [
        SearchHit(
            url=r.url, title=r.title, publish_date=r.publish_date, excerpts=_screened(r.excerpts)
        )
        for r in raw.results  # type: ignore[attr-defined]
    ]
    return SearchResult(
        hits=hits,
        search_id=raw.search_id,  # type: ignore[attr-defined]
        session_id=raw.session_id,  # type: ignore[attr-defined]
    )


def _screened(excerpts: list[str]) -> list[str]:
    """Model Armor over every excerpt before it can reach a prompt (PARALLEL_INTEGRATION.md
    §4.1). A hard-blocked excerpt is dropped, not raised — one adversarial result must
    never sink an entire search call."""
    from packages.common.errors import SafetyBlocked
    from packages.safety.model_armor import screen

    screened: list[str] = []
    for excerpt in excerpts[:3]:
        try:
            result = screen(excerpt, context="web_excerpt")
        except SafetyBlocked as exc:
            log.warning("search_excerpt_dropped_by_safety", reason=exc.reason)
            continue
        screened.append(result.text)
    return screened


def build_objective(
    category: ClaimCategory, entity_text: str, jurisdictions: list[str]
) -> tuple[str, list[str]]:
    """Objective + search queries for one claim, steered by `config/jurisdictions.yaml`
    hints per jurisdiction (PARALLEL_INTEGRATION.md §4.1's "steer via objective +
    exclude_domains" — never a hard `include_domains` allow-list)."""
    hints = [
        str(JURISDICTIONS[code]["objective_hint"])
        for code in jurisdictions
        if code in JURISDICTIONS and "objective_hint" in JURISDICTIONS[code]
    ]
    hint_text = " ".join(hints)

    builders = {
        ClaimCategory.MUSIC: _music_objective,
        ClaimCategory.BRAND: _brand_objective,
        ClaimCategory.PERSON: _person_objective,
        ClaimCategory.LOCATION: _location_objective,
        ClaimCategory.ARTWORK: _artwork_objective,
        ClaimCategory.QUOTE: _quote_objective,
        ClaimCategory.EVENT: _event_objective,
        ClaimCategory.STATISTIC: _statistic_objective,
        ClaimCategory.ATTRIBUTION: _attribution_objective,
        ClaimCategory.ARCHIVAL: _archival_objective,
        ClaimCategory.IDENTITY: _identity_objective,
    }
    objective, queries = builders[category](entity_text, jurisdictions)
    if hint_text:
        objective = f"{objective} {hint_text}"
    return objective, queries


def _music_objective(entity: str, jurisdictions: list[str]) -> tuple[str, list[str]]:
    territories = ", ".join(jurisdictions) or "worldwide"
    return (
        f"Determine sync/composition/master rights status for the musical work "
        f"'{entity}' for distribution in {territories}.",
        [f"{entity} publisher rights", f"{entity} sync licensing"],
    )


def _brand_objective(entity: str, jurisdictions: list[str]) -> tuple[str, list[str]]:
    territories = ", ".join(jurisdictions) or "worldwide"
    return (
        f"Identify the trademark owner and product-placement clearance policy for "
        f"'{entity}' in {territories}.",
        [f"{entity} trademark owner", f"{entity} brand clearance policy"],
    )


def _person_objective(entity: str, jurisdictions: list[str]) -> tuple[str, list[str]]:
    territories = ", ".join(jurisdictions) or "worldwide"
    return (
        f"Determine whether '{entity}' is a living or historical public figure and any "
        f"right-of-publicity considerations for depiction in {territories}.",
        [f"{entity} biography", f"{entity} right of publicity"],
    )


def _location_objective(entity: str, jurisdictions: list[str]) -> tuple[str, list[str]]:
    return (
        f"Identify the owner/custodian of '{entity}' and any filming permit requirements.",
        [f"{entity} filming permit", f"{entity} location owner"],
    )


def _artwork_objective(entity: str, jurisdictions: list[str]) -> tuple[str, list[str]]:
    return (
        f"Determine the copyright status and rights holder for the artwork '{entity}'.",
        [f"{entity} copyright status", f"{entity} rights holder"],
    )


def _quote_objective(entity: str, jurisdictions: list[str]) -> tuple[str, list[str]]:
    return (
        f"Identify the source work and copyright status of the quoted text '{entity}'.",
        [f"{entity} original source", f"{entity} quote attribution"],
    )


def _event_objective(entity: str, jurisdictions: list[str]) -> tuple[str, list[str]]:
    return (
        f"Verify the factual accuracy of the claimed event: '{entity}'.",
        [f"{entity} fact check", f"{entity} timeline"],
    )


def _statistic_objective(entity: str, jurisdictions: list[str]) -> tuple[str, list[str]]:
    return (
        f"Verify the accuracy of the statistic: '{entity}'.",
        [f"{entity} source data", f"{entity} statistic verification"],
    )


def _attribution_objective(entity: str, jurisdictions: list[str]) -> tuple[str, list[str]]:
    return (
        f"Verify who is actually responsible for: '{entity}'.",
        [f"{entity} attribution", f"{entity} who said"],
    )


def _archival_objective(entity: str, jurisdictions: list[str]) -> tuple[str, list[str]]:
    return (
        f"Determine the provenance and rights holder of the archival material: '{entity}'.",
        [f"{entity} archival footage source", f"{entity} footage rights"],
    )


def _identity_objective(entity: str, jurisdictions: list[str]) -> tuple[str, list[str]]:
    return (
        f"Verify the identity claim: '{entity}'.",
        [f"{entity} identity verification", f"{entity} who is"],
    )
