"""Pure-logic coverage for packages.parallel_client.task: spec+input char budget
truncation (PARALLEL_INTEGRATION.md §3), forbidden processor guard, and the escalation
rule (ADK_AGENTS.md §2.2 step 6).
"""

from __future__ import annotations

import json

import pytest

from packages.claims.enums import Confidence
from packages.parallel_client.task import _fit_spec_and_input, build_input, run, should_escalate

_SMALL_SPEC = {
    "type": "object",
    "properties": {"a": {"type": "string"}},
    "required": ["a"],
    "additionalProperties": False,
}


def test_build_input_caps_at_max_chars() -> None:
    from config.parallel import TASK_MAX_INPUT_CHARS

    huge_excerpt = "x" * (TASK_MAX_INPUT_CHARS * 2)
    text = build_input("claim", jurisdictions=["us"], excerpt=huge_excerpt, top_urls=[])
    assert len(text) == TASK_MAX_INPUT_CHARS


def test_fit_spec_and_input_leaves_short_input_untouched() -> None:
    result = _fit_spec_and_input(_SMALL_SPEC, "short input", name="test_spec")
    assert result == "short input"


def test_fit_spec_and_input_truncates_input_when_over_budget() -> None:
    from config.parallel import TASK_SPEC_PLUS_INPUT_MAX_CHARS

    long_input = "y" * TASK_SPEC_PLUS_INPUT_MAX_CHARS
    result = _fit_spec_and_input(_SMALL_SPEC, long_input, name="test_spec")
    assert len(result) < len(long_input)
    assert len(json.dumps(_SMALL_SPEC)) + len(result) <= TASK_SPEC_PLUS_INPUT_MAX_CHARS


def test_forbidden_processor_prefix_raises() -> None:
    with pytest.raises(ValueError, match="forbidden"):
        run("input", "legal_brand", claim_id="c1", project_id="demo", processor="ultra")


def test_should_escalate_low_confidence_high_priority() -> None:
    assert should_escalate(Confidence.LOW, 1) is True
    assert should_escalate(Confidence.LOW, 2) is True


def test_should_escalate_false_when_priority_too_low() -> None:
    assert should_escalate(Confidence.LOW, 3) is False


def test_should_escalate_false_when_confidence_not_low() -> None:
    assert should_escalate(Confidence.MEDIUM, 1) is False
    assert should_escalate(Confidence.HIGH, 1) is False
    assert should_escalate(Confidence.UNKNOWN, 1) is False
