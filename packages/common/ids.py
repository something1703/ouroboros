"""ID helpers. Deterministic claim_id hashing lives in packages/claims (it is domain logic, not infra)."""

from __future__ import annotations

from ulid import ULID


def new_ulid() -> str:
    """A new lexicographically-sortable unique id, for Evidence, events, and the like."""
    return str(ULID())
