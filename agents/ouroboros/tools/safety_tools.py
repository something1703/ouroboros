"""Safety tool (ADK_AGENTS.md §0) — thin wrapper around packages/safety/model_armor."""

from __future__ import annotations

from packages.safety.model_armor import screen


def safety_screen(text: str, context: str) -> dict[str, object]:
    """Screen untrusted text (a web excerpt, a Task output) through Model Armor before
    it reaches a prompt. `context` is one of 'ingest', 'web_excerpt', 'task_output'.
    Raises if the text is hard-blocked (high-confidence prompt injection/jailbreak) —
    the caller must catch `packages.common.errors.SafetyBlocked` and skip that one
    piece of text, never abort the whole batch."""
    result = screen(text, context=context)  # type: ignore[arg-type]
    return {
        "text": result.text,
        "flagged": result.flagged,
        "categories": result.detected_categories,
    }
