"""Pure-logic coverage for agents/ouroboros/clear/specialist.py — the public-domain
excerpt heuristic (step 3 of ADK_AGENTS.md §2.2's algorithm). No ADK runtime, no
network: just the plain function.
"""

from __future__ import annotations

from agents.ouroboros.clear.specialist import _looks_public_domain
from packages.parallel_client.search import SearchHit


def _hit(*excerpts: str) -> SearchHit:
    return SearchHit(
        url="https://example.com", title=None, publish_date=None, excerpts=list(excerpts)
    )


def test_no_hits_is_not_public_domain() -> None:
    assert _looks_public_domain([]) is False


def test_ordinary_excerpt_is_not_public_domain() -> None:
    hits = [_hit("This song is controlled by Sony Music Publishing.")]
    assert _looks_public_domain(hits) is False


def test_explicit_public_domain_phrase_matches() -> None:
    hits = [_hit("This 1922 recording is now in the public domain in the US.")]
    assert _looks_public_domain(hits) is True


def test_royalty_free_phrase_matches() -> None:
    hits = [_hit("Available as a royalty-free track for any commercial use.")]
    assert _looks_public_domain(hits) is True


def test_match_can_be_in_any_hit_or_excerpt() -> None:
    hits = [
        _hit("Nothing relevant here."),
        _hit("Also nothing.", "But this one says no license required for personal use."),
    ]
    assert _looks_public_domain(hits) is True


def test_case_insensitive() -> None:
    hits = [_hit("PUBLIC DOMAIN since 1926.")]
    assert _looks_public_domain(hits) is True
