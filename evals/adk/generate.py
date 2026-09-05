"""Generates claim_triage.evalset.json and risk_assessor.evalset.json (PHASE_05.md
§5.2/§5.4) using the real EvalCase/EvalSet pydantic schema (constructed via the real
ADK classes, not hand-written JSON, per this project's "verify, don't guess API
schemas" discipline). Re-run after re-seeding fixture data:

    uv run --with "google-adk[eval]" python evals/adk/generate.py

Fixture data: scripts/seed_eval_fixtures.py (5 isolated eval-triage-N projects for
ClaimTriage; RiskAssessor reuses the real "demo" project's already-verified claims, so
run a real local CLEAR pass on demo first if those claim_ids don't have Evidence yet).
"""

import json
from pathlib import Path

from google.adk.evaluation.eval_case import EvalCase, IntermediateData, Invocation, SessionInput
from google.adk.evaluation.eval_set import EvalSet
from google.genai import types

_EVALS_DIR = Path(__file__).parent


def _content(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def _fc(name: str, **args: object) -> types.FunctionCall:
    return types.FunctionCall(name=name, args=args)


def _session(project_id: str, **extra_state: object) -> SessionInput:
    state = {
        "project_id": project_id,
        "studio_id": "studio-eval",
        "jurisdictions": ["us", "gb"],
        "release_date": "2026-12-01",
        "run_id": "eval-run",
        **extra_state,
    }
    return SessionInput(app_name="ouroboros", user_id="eval-user", state=state)


# --- ClaimTriage -----------------------------------------------------------------
# tool_trajectory_avg_score, ANY_ORDER match (evals/adk/test_config.json), expecting
# only a single-key `list_claims(project_id=...)` call. Found live: the model calls
# list_claims *multiple times* per turn with varying optional args (sometimes with
# `status`/`category`/`result_limit`, sometimes without) -- no fixed multi-key args
# dict reliably appears in every run, but a bare `{"project_id": ...}` call
# consistently does. set_status/get_prior_decisions calls carry randomly-generated
# IDs or LLM-chosen ordering and are deliberately left unasserted (see
# docs/DECISIONS.md).

_TRIAGE_PROJECTS = [
    ("claim_triage_simple_no_prior_decision", "eval-triage-1"),
    ("claim_triage_prior_decision_causes_skip", "eval-triage-2"),
    ("claim_triage_multi_category_batch", "eval-triage-3"),
    ("claim_triage_artwork_uses_location_artwork_batch", "eval-triage-4"),
    ("claim_triage_unrelated_prior_decision_does_not_skip", "eval-triage-5"),
]

triage_cases = [
    EvalCase(
        eval_id=eval_id,
        conversation=[
            Invocation(
                invocation_id="inv1",
                user_content=_content("Begin claim triage."),
                intermediate_data=IntermediateData(
                    tool_uses=[_fc("list_claims", project_id=project_id)]
                ),
            )
        ],
        session_input=_session(project_id),
    )
    for eval_id, project_id in _TRIAGE_PROJECTS
]

triage_set = EvalSet(
    eval_set_id="claim_triage",
    name="ClaimTriage",
    description=(
        "PHASE_05.md 5.2 -- 5 cases against local-dev fixture projects "
        "(scripts/seed_eval_fixtures.py's eval-triage-1..5), each verifying "
        "ClaimTriage's first real tool call (list_claims for that project)."
    ),
    eval_cases=triage_cases,
)

# --- RiskAssessor ------------------------------------------------------------------
# Fixture data: the real "demo" project's already-verified local-dev claims (real
# Evidence + prescores from a real local CLEAR pass). RiskAssessor's prompt
# (agents/ouroboros/prompts/risk_assessor.md) tells it to read claim_ids from state's
# *_results keys -- true only in the real pipeline, where those keys are the
# specialists' own tool call/response events, still visible in the *conversation
# history* of the same session (confirmed live: gather_risk_inputs takes claim_ids as
# a plain model-supplied parameter, not a tool_context-injected read of
# session.state). An isolated eval of RiskAssessor alone has no such history to
# inherit, so the claim_ids are named directly in the user message instead -- a
# reasonable stand-in for "a human directly asks RiskAssessor to assess these
# claims," which the prompt's flexible framing supports.

_DEMO_CLAIMS = {
    "music": "dfbca044ffb083fc275b791d",
    "brand": "97dfd8f22a95e4908916efc8",
    "person": "369b8bf8f6783cb5e04296e1",
    "location_artwork": "effbe6edcac98c252a3dec71",
}


def _risk_case(eval_id: str, claim_ids: list[str]) -> EvalCase:
    ids_text = ", ".join(claim_ids)
    return EvalCase(
        eval_id=eval_id,
        conversation=[
            Invocation(
                invocation_id="inv1",
                user_content=_content(
                    f"Assess risk for these already-verified claim_ids: {ids_text}"
                ),
                intermediate_data=IntermediateData(
                    tool_uses=[_fc("gather_risk_inputs", claim_ids=claim_ids)]
                ),
            )
        ],
        session_input=_session("demo"),
    )


risk_cases = [
    _risk_case("risk_assessor_music_claim", [_DEMO_CLAIMS["music"]]),
    _risk_case("risk_assessor_brand_claim", [_DEMO_CLAIMS["brand"]]),
    _risk_case("risk_assessor_person_claim", [_DEMO_CLAIMS["person"]]),
    _risk_case("risk_assessor_location_artwork_claim", [_DEMO_CLAIMS["location_artwork"]]),
    _risk_case(
        "risk_assessor_multiple_categories_one_batch",
        [_DEMO_CLAIMS["music"], _DEMO_CLAIMS["brand"]],
    ),
]

risk_set = EvalSet(
    eval_set_id="risk_assessor",
    name="RiskAssessor",
    description=(
        "PHASE_05.md 5.4 -- 5 cases against the real 'demo' project's already-verified "
        "local-dev claims (real Evidence + prescores from a real local CLEAR pass), "
        "each verifying RiskAssessor's first real tool call (gather_risk_inputs with "
        "exactly the claim_ids named in the user message)."
    ),
    eval_cases=risk_cases,
)

if __name__ == "__main__":
    for name, eval_set in (("claim_triage", triage_set), ("risk_assessor", risk_set)):
        path = _EVALS_DIR / f"{name}.evalset.json"
        path.write_text(
            json.dumps(eval_set.model_dump(mode="json", exclude_none=True), indent=2) + "\n"
        )
        print(f"wrote {path}")
