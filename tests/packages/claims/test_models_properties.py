from datetime import UTC, datetime

from hypothesis import given
from hypothesis import strategies as st

from packages.claims.enums import ClaimCategory, ClaimKind
from packages.claims.models import Claim, SourceRef

_categories = st.sampled_from(list(ClaimCategory))


@given(
    project_id=st.text(min_size=1, max_size=20),
    category=_categories,
    normalized_text=st.text(min_size=1, max_size=50),
    asset_id=st.text(min_size=1, max_size=20),
    page=st.one_of(st.none(), st.integers(min_value=0, max_value=10_000)),
)
def test_compute_id_is_deterministic(
    project_id: str, category: ClaimCategory, normalized_text: str, asset_id: str, page: int | None
) -> None:
    a = Claim.compute_id(
        project_id=project_id,
        category=category,
        normalized_text=normalized_text,
        asset_id=asset_id,
        page_or_t_start=page,
    )
    b = Claim.compute_id(
        project_id=project_id,
        category=category,
        normalized_text=normalized_text,
        asset_id=asset_id,
        page_or_t_start=page,
    )
    assert a == b
    assert len(a) == 24


def test_compute_id_differs_on_project() -> None:
    kwargs = {
        "category": ClaimCategory.MUSIC,
        "normalized_text": "bohemian rhapsody",
        "asset_id": "asset-1",
        "page_or_t_start": 12,
    }
    a = Claim.compute_id(project_id="project-a", **kwargs)  # type: ignore[arg-type]
    b = Claim.compute_id(project_id="project-b", **kwargs)  # type: ignore[arg-type]
    assert a != b


def test_new_produces_stable_claim_id_across_reingestion() -> None:
    source = SourceRef(asset_id="asset-1", page=12, excerpt="A Coca-Cola can sits on the table.")

    first = Claim.new(
        project_id="demo",
        studio_id="studio-1",
        kind=ClaimKind.LEGAL,
        category=ClaimCategory.BRAND,
        entity_text="Coca-Cola",
        claim_text="A Coca-Cola can is visible on the table in Sc. 12",
        language="en",
        source=source,
        jurisdictions=["us"],
    )
    second = Claim.new(
        project_id="demo",
        studio_id="studio-1",
        kind=ClaimKind.LEGAL,
        category=ClaimCategory.BRAND,
        entity_text="Coca-Cola",
        claim_text="A Coca-Cola can is visible on the table in Sc. 12",
        language="en",
        source=source,
        jurisdictions=["us"],
    )

    assert first.claim_id == second.claim_id
    assert first.normalized_text == "cocacola"


def test_new_stamps_utc_timestamps() -> None:
    source = SourceRef(asset_id="asset-1", page=1, excerpt="excerpt")
    claim = Claim.new(
        project_id="demo",
        studio_id="studio-1",
        kind=ClaimKind.FACTUAL,
        category=ClaimCategory.EVENT,
        entity_text="Some event",
        claim_text="Something happened",
        language="en",
        source=source,
        jurisdictions=["us"],
    )
    assert claim.created_at.tzinfo is not None
    assert claim.created_at == claim.updated_at
    assert claim.created_at <= datetime.now(UTC)
