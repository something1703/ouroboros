"""overall_confidence's min-rule (PARALLEL_INTEGRATION.md §4.2) and Citation/FieldBasis
parsing from a real `parallel.types.FieldBasis` shape.
"""

from __future__ import annotations

import parallel.types as parallel_types

from packages.claims.enums import Confidence
from packages.parallel_client.basis import overall_confidence, parse_basis


def _raw_basis(field: str, confidence: str | None) -> parallel_types.FieldBasis:
    return parallel_types.FieldBasis(
        field=field,
        reasoning="because",
        confidence=confidence,
        citations=[parallel_types.Citation(url="https://example.com", excerpts=["an excerpt"])],
    )


def test_parse_basis_maps_confidence_and_first_excerpt() -> None:
    parsed = parse_basis([_raw_basis("work_title", "high")])
    assert len(parsed) == 1
    assert parsed[0].confidence == Confidence.HIGH
    assert parsed[0].citations[0].excerpt == "an excerpt"


def test_parse_basis_none_confidence_maps_to_unknown() -> None:
    parsed = parse_basis([_raw_basis("work_title", None)])
    assert parsed[0].confidence == Confidence.UNKNOWN


def test_overall_confidence_is_min_across_required_fields() -> None:
    basis = parse_basis(
        [_raw_basis("a", "high"), _raw_basis("b", "low"), _raw_basis("c", "medium")]
    )
    assert overall_confidence(basis, required_fields=["a", "b", "c"]) == Confidence.LOW


def test_overall_confidence_ignores_fields_outside_required() -> None:
    """A basis entry for a nested/extra field (e.g. Parallel's own
    `trademark_registrations.0`) must not drag down the overall score."""
    basis = parse_basis([_raw_basis("a", "high"), _raw_basis("a.0", "low")])
    assert overall_confidence(basis, required_fields=["a"]) == Confidence.HIGH


def test_overall_confidence_missing_field_counts_as_unknown() -> None:
    basis = parse_basis([_raw_basis("a", "high")])
    assert overall_confidence(basis, required_fields=["a", "b"]) == Confidence.UNKNOWN


def test_overall_confidence_all_high_is_high() -> None:
    basis = parse_basis([_raw_basis("a", "high"), _raw_basis("b", "high")])
    assert overall_confidence(basis, required_fields=["a", "b"]) == Confidence.HIGH
