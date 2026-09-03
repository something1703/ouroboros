"""PARALLEL_INTEGRATION.md §3 spec-rule enforcement, and PHASE_04.md §4.3's acceptance
criterion: "A deliberately invalid spec in a test raises at import."
"""

from __future__ import annotations

import pytest

from packages.parallel_client.specs.loader import SPECS, SpecValidationError, validate_spec

_VALID = {
    "type": "object",
    "properties": {"a": {"type": "string"}},
    "required": ["a"],
    "additionalProperties": False,
}


def test_real_specs_all_loaded_and_valid() -> None:
    for name in (
        "legal_music",
        "legal_brand",
        "legal_person",
        "legal_location_artwork",
        "factual_claim",
    ):
        assert name in SPECS


def test_missing_required_field_raises() -> None:
    spec = {**_VALID, "properties": {"a": {"type": "string"}, "b": {"type": "string"}}}
    with pytest.raises(SpecValidationError, match="required"):
        validate_spec(spec, name="bad_missing_required")


def test_additional_properties_true_raises() -> None:
    spec = {**_VALID, "additionalProperties": True}
    with pytest.raises(SpecValidationError, match="additionalProperties"):
        validate_spec(spec, name="bad_additional_properties")


def test_root_any_of_raises() -> None:
    spec = {**_VALID, "anyOf": [{"type": "string"}]}
    with pytest.raises(SpecValidationError, match="anyOf"):
        validate_spec(spec, name="bad_any_of")


@pytest.mark.parametrize(
    "keyword", ["pattern", "minLength", "maxLength", "format", "minimum", "uniqueItems"]
)
def test_forbidden_keyword_raises(keyword: str) -> None:
    spec = {
        "type": "object",
        "properties": {"a": {"type": "string", keyword: "x" if keyword == "format" else 1}},
        "required": ["a"],
        "additionalProperties": False,
    }
    with pytest.raises(SpecValidationError, match="forbidden keyword"):
        validate_spec(spec, name="bad_forbidden_keyword")


def test_nesting_beyond_five_raises() -> None:
    # Build a chain of 6 nested objects, each with one required property.
    innermost: dict[str, object] = {"type": "string"}
    node = innermost
    for _ in range(6):
        node = {
            "type": "object",
            "properties": {"nested": node},
            "required": ["nested"],
            "additionalProperties": False,
        }
    with pytest.raises(SpecValidationError, match="nesting"):
        validate_spec(node, name="bad_nesting")


def test_spec_over_char_budget_raises() -> None:
    huge_description = "x" * 20_000
    spec = {
        "type": "object",
        "properties": {"a": {"type": "string", "description": huge_description}},
        "required": ["a"],
        "additionalProperties": False,
    }
    with pytest.raises(SpecValidationError, match="chars"):
        validate_spec(spec, name="bad_too_long")


def test_valid_spec_with_array_of_objects_passes() -> None:
    """Mirrors legal_brand's `trademark_registrations` shape — nested object items in
    an array must still satisfy the object rules recursively."""
    spec = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"x": {"type": "string"}},
                    "required": ["x"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }
    validate_spec(spec, name="ok_array_of_objects")  # does not raise
