"""Text normalization for claim hashing and dedupe. Deterministic and idempotent by construction."""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """NFKC-normalize, lowercase, strip punctuation, collapse whitespace. Diacritics are kept.

    Idempotent: `normalize_text(normalize_text(x)) == normalize_text(x)` for all `x`.
    This is what makes claim_id stable across re-ingestion of the same source.
    """
    nfkc = unicodedata.normalize("NFKC", text)
    lowered = nfkc.casefold()
    # Strip Unicode punctuation (category starting with "P"); diacritics live in the
    # "M" (Mark) categories and are untouched, so accented text stays distinguishable.
    no_punct = "".join(ch for ch in lowered if not unicodedata.category(ch).startswith("P"))
    collapsed = _WHITESPACE_RE.sub(" ", no_punct)
    return collapsed.strip()
