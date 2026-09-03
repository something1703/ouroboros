"""Offline unit tests for services/ingest's pure logic — naming-convention matching and
the within-asset dedupe merge (PHASE_03.md §3.1, §3.5). The full pipeline
(`_process_object`) is covered by live verification (docs/evidence/03-ingest.md): it's
mostly orchestration over Gemini/Cloud SQL/Firestore/Pub/Sub calls that aren't
meaningfully mockable without just re-testing FastAPI/SQLAlchemy themselves.
"""

from __future__ import annotations

import pytest

from packages.claims.enums import ClaimCategory, ClaimKind
from packages.claims.models import Claim, SourceRef
from services.ingest.main import _CUT_RE, _SCRIPT_RE, _dedupe


def _claim(
    *, page: int, entity_text: str = "Coca-Cola", category: ClaimCategory = ClaimCategory.BRAND
) -> Claim:
    source = SourceRef(asset_id="asset-1", page=page, excerpt=f"excerpt at page {page}")
    return Claim.new(
        project_id="demo",
        studio_id="studio-1",
        kind=ClaimKind.LEGAL,
        category=category,
        entity_text=entity_text,
        claim_text=f"{entity_text} appears on page {page}",
        language="en",
        source=source,
        jurisdictions=["us"],
    )


@pytest.mark.parametrize(
    ("name", "expected_project_id"),
    [
        ("scripts/demo/final_draft.pdf", "demo"),
        ("scripts/some-project-42/x.pdf", "some-project-42"),
    ],
)
def test_script_re_matches_valid_paths(name: str, expected_project_id: str) -> None:
    match = _SCRIPT_RE.match(name)
    assert match is not None
    assert match.group("project_id") == expected_project_id


@pytest.mark.parametrize(
    "name",
    [
        "scripts/demo/nested/x.pdf",  # extra path segment
        "scripts/demo/x.docx",  # wrong extension
        "cuts/demo/x.pdf",  # wrong prefix for a script
        "scripts/x.pdf",  # missing project_id segment
    ],
)
def test_script_re_rejects_invalid_paths(name: str) -> None:
    assert _SCRIPT_RE.match(name) is None


@pytest.mark.parametrize(
    ("name", "expected_project_id"),
    [
        ("cuts/demo/reel.mp4", "demo"),
        ("cuts/demo/reel.mov", "demo"),
    ],
)
def test_cut_re_matches_valid_paths(name: str, expected_project_id: str) -> None:
    match = _CUT_RE.match(name)
    assert match is not None
    assert match.group("project_id") == expected_project_id


def test_cut_re_rejects_wrong_extension() -> None:
    assert _CUT_RE.match("cuts/demo/reel.avi") is None


def test_dedupe_merges_same_category_and_normalized_text_within_asset() -> None:
    first = _claim(page=1)
    second = _claim(page=5)  # same entity/category, different page -> same normalized_text
    third = _claim(page=9, entity_text="Apple", category=ClaimCategory.BRAND)  # distinct

    merged = _dedupe([first, second, third])

    assert len(merged) == 2
    coca_cola = next(c for c in merged if c.entity_text == "Coca-Cola")
    assert coca_cola.claim_id == first.claim_id  # first occurrence wins the identity
    assert coca_cola.source.occurrences == 2
    assert len(coca_cola.source.all_refs) == 1
    assert coca_cola.source.all_refs[0]["page"] == 5


def test_dedupe_keeps_distinct_categories_for_same_text_separate() -> None:
    """The same surface text under two different categories must not merge — e.g. an
    artwork titled the same as a real person's name."""
    brand = _claim(page=1, entity_text="Chanel", category=ClaimCategory.BRAND)
    person = _claim(page=2, entity_text="Chanel", category=ClaimCategory.PERSON)

    merged = _dedupe([brand, person])

    assert len(merged) == 2
    assert {c.claim_id for c in merged} == {brand.claim_id, person.claim_id}


def test_dedupe_single_claim_is_unchanged() -> None:
    claim = _claim(page=1)
    merged = _dedupe([claim])
    assert merged == [claim]
    assert merged[0].source.occurrences == 1
    assert merged[0].source.all_refs == []
