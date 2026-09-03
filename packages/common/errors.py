"""Typed exceptions. Services map these to HTTP; agents catch and record them into verification_history."""

from __future__ import annotations


class OuroborosError(Exception):
    """Base class for every domain error raised inside Ouroboros."""


class ParallelError(OuroborosError):
    """A Parallel API call failed after retries (429/5xx/timeout exhausted, or an unexpected error)."""


class ParallelValidationError(ParallelError):
    """A Parallel API call was rejected as a 4xx — never retried."""


class BudgetExceeded(OuroborosError):
    """A project's Parallel spend cap (`PARALLEL_PROJECT_BUDGET_USD`) would be exceeded by this call."""

    def __init__(self, project_id: str, spent_usd: float, cap_usd: float) -> None:
        self.project_id = project_id
        self.spent_usd = spent_usd
        self.cap_usd = cap_usd
        super().__init__(
            f"project {project_id}: spend ${spent_usd:.4f} would exceed cap ${cap_usd:.2f}"
        )


class SafetyBlocked(OuroborosError):
    """Model Armor hard-blocked a piece of text; the caller must record and continue with the next item."""

    def __init__(self, context: str, reason: str) -> None:
        self.context = context
        self.reason = reason
        super().__init__(f"safety block in context={context!r}: {reason}")


class NotFound(OuroborosError):
    """A referenced entity (project, asset, claim, evidence) does not exist in the ledger."""

    def __init__(self, kind: str, identifier: str) -> None:
        self.kind = kind
        self.identifier = identifier
        super().__init__(f"{kind} not found: {identifier}")
