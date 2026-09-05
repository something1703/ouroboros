from hypothesis import given
from hypothesis import strategies as st

from packages.claims.normalize import normalize_text


@given(st.text())
def test_normalize_is_idempotent(text: str) -> None:
    once = normalize_text(text)
    twice = normalize_text(once)
    assert once == twice


@given(st.text())
def test_normalize_has_no_leading_trailing_whitespace(text: str) -> None:
    normalized = normalize_text(text)
    assert normalized == normalized.strip()


@given(st.text())
def test_normalize_collapses_internal_whitespace(text: str) -> None:
    normalized = normalize_text(text)
    assert "  " not in normalized


def test_normalize_keeps_diacritics() -> None:
    assert normalize_text("Café Möbius") == "café möbius"


def test_normalize_strips_punctuation() -> None:
    assert normalize_text("Coca-Cola, Inc.!") == "cocacola inc"


def test_normalize_lowercases() -> None:
    assert normalize_text("BOHEMIAN RHAPSODY") == "bohemian rhapsody"
