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

# --- The four CLEAR specialists + FactAgent ----------------------------------------
# PHASE_09.md §9.2. Fixture data: evals/golden/legal.yaml + factual.yaml's own claims,
# seeded via evals/run_golden.py's `_seed_legal_project()`/`_seed_factual_project()`
# (idempotent, deterministic claim_ids -- Claim.compute_id) -- run one of those (or the
# whole golden-set run) before `adk eval` against these sets, exactly like
# scripts/seed_eval_fixtures.py is a prerequisite for claim_triage/risk_assessor above.
# claim_ids below were captured live from a real seed run (see evals/adk/README.md).

_MUSIC_CLAIMS = [
    "dfe27032e1e0238056285533",  # pragma: allowlist secret
    "4884113b230ffcb29a876e35",  # pragma: allowlist secret
    "fb035fbae4afe9f581637957",  # pragma: allowlist secret
    "8709732c715a2dacb6ad5540",  # pragma: allowlist secret
    "0c18458f9d52c472a6cb5b6e",  # pragma: allowlist secret
]
_BRAND_CLAIMS = [
    "688bbc2f4c271a8670e7ba79",  # pragma: allowlist secret
    "6dbb5a468cb36492afa8db7f",  # pragma: allowlist secret
    "2cce33f9b0ff157afd943707",  # pragma: allowlist secret
    "4da95c1e7e4b2e721eb3358b",  # pragma: allowlist secret
    "8aefa3aa7b592df0c0099e7b",  # pragma: allowlist secret
]
_PERSON_CLAIMS = [
    "f9d132077cfd067aae852dd4",  # pragma: allowlist secret
    "7e9a41db7a815f474060375d",  # pragma: allowlist secret
    "bd6b2c7cc397150aa5b9e796",  # pragma: allowlist secret
    "9543d95bed4dacccbb7577bf",  # pragma: allowlist secret
    "88587a733ef0e99518309f32",  # pragma: allowlist secret
]
_LOCATION_ARTWORK_CLAIMS = [
    "e4435c58f4bdfa38fef32a7f",  # location -- pragma: allowlist secret
    "57f3f728f72d1b7cc907098c",  # location -- pragma: allowlist secret
    "d9a1d28f84f69425c90c8afb",  # location -- pragma: allowlist secret
    "c9669620b98c0a5544981c53",  # artwork -- pragma: allowlist secret
    "77cf55f98ea8c022ba02ca90",  # artwork -- pragma: allowlist secret
]
_FACTUAL_CLAIMS = [
    "3dd37f3c560aa933759f664a",  # pragma: allowlist secret
    "65784df8a56b8c80ea925304",  # pragma: allowlist secret
    "b68d75587b61f167e6e2ce31",  # pragma: allowlist secret
    "f8f0317f8a7d5925bd7bfd44",  # pragma: allowlist secret
    "c4f738c2e61cb2cf188517a8",  # pragma: allowlist secret
]


def _specialist_case(eval_id: str, project_id: str, category: str) -> EvalCase:
    # Asserts `list_claims(project_id=..., category=..., status="triaged")` -- the
    # specialist's real first move is to discover its own batch, not receive claim_ids
    # handed to it in the user turn (that's RiskAssessor's own, different, flexible
    # framing -- see `_risk_case` above). Found live, across 6 repeated real runs: a
    # specialist's own list_claims call is exact-match reliable on all three of these
    # keys every time (unlike ClaimTriage's bare `project_id`-only call, which handles
    # every category and doesn't filter this tightly) -- ADK's trajectory scorer
    # requires full dict equality even under ANY_ORDER matching (only call *order* is
    # forgiving, not a given call's own args), so this had to be nailed down exactly
    # rather than guessed from a single run.
    return EvalCase(
        eval_id=eval_id,
        conversation=[
            Invocation(
                invocation_id="inv1",
                user_content=_content("Verify this batch of claims."),
                intermediate_data=IntermediateData(
                    tool_uses=[
                        _fc(
                            "list_claims",
                            project_id=project_id,
                            category=category,
                            status="triaged",
                        )
                    ]
                ),
            )
        ],
        session_input=_session(project_id),
    )


def _specialist_set(
    eval_set_id: str,
    name: str,
    tool_name: str,
    categories: list[str],
    project_id: str,
) -> EvalSet:
    """`categories` has one entry per case -- usually all the same value (one fixed
    category per specialist), except LocationArtAgent, which really does handle two
    (`location` and `artwork` both route to `legal_location_artwork`)."""
    cases = [
        _specialist_case(f"{eval_set_id}_{i}", project_id, category)
        for i, category in enumerate(categories, start=1)
    ]
    return EvalSet(
        eval_set_id=eval_set_id,
        name=name,
        description=(
            f"PHASE_09.md 9.2 -- {len(cases)} cases against evals/golden's real seeded "
            f"claims (project '{project_id}'), each verifying {name}'s first real tool "
            f"call (list_claims), the same batch-discovery step that precedes its real "
            f"{tool_name} call."
        ),
        eval_cases=cases,
    )


music_set = _specialist_set(
    "music_agent",
    "MusicAgent",
    "verify_music_batch",
    ["music"] * len(_MUSIC_CLAIMS),
    "eval-golden-legal",
)
brand_set = _specialist_set(
    "brand_agent",
    "BrandAgent",
    "verify_brand_batch",
    ["brand"] * len(_BRAND_CLAIMS),
    "eval-golden-legal",
)
person_set = _specialist_set(
    "person_agent",
    "PersonAgent",
    "verify_person_batch",
    ["person"] * len(_PERSON_CLAIMS),
    "eval-golden-legal",
)
location_art_set = _specialist_set(
    "location_art_agent",
    "LocationArtAgent",
    "verify_location_artwork_batch",
    ["location", "location", "location", "artwork", "artwork"],
    "eval-golden-legal",
)
fact_set = _specialist_set(
    "fact_agent",
    "FactAgent",
    "verify_fact_batch",
    ["event", "statistic", "attribution", "event", "statistic"],
    "eval-golden-factual",
)

# --- AskOuroboros --------------------------------------------------------------------
# PHASE_09.md §9.2. One case per real tool AskOuroboros can reach for
# (ask_ouroboros.md's own worked examples: ledger claim, corpus doc, live web), plus two
# more exercising the ledger path against different claims -- 5 cases total. Session
# state carries `question` (agents/ouroboros/ask/ask_ouroboros.py::_instruction reads
# ctx.state["question"]), matching how `initialize_run` populates it for a real "ask"-
# mode run (agents/ouroboros/tools/session_tools.py).

_ASK_CASES = [
    (
        "ask_ouroboros_ledger_claim",
        "Is there an existing claim about the Coca-Cola product placement in this project?",
        "list_claims",
        {"project_id": "eval-golden-legal"},
    ),
    (
        "ask_ouroboros_ledger_specific_claim",
        f"What's the status of claim {_BRAND_CLAIMS[0]}?",
        "get_claim",
        {"claim_id": _BRAND_CLAIMS[0]},
    ),
    (
        "ask_ouroboros_corpus_precedent",
        "What did we decide about Beatles music rights last time?",
        "search_private_corpus",
        {"query": "Beatles music rights clearance decision"},
    ),
    (
        "ask_ouroboros_studio_guideline",
        "What's our studio policy on depicting real living persons?",
        "search_private_corpus",
        {"query": "studio policy real person depiction"},
    ),
    (
        "ask_ouroboros_live_web",
        "Is Coca-Cola still an actively registered trademark?",
        "ask_grounded",
        {"question": "Is Coca-Cola still an actively registered trademark?"},
    ),
]

ask_cases = [
    EvalCase(
        eval_id=eval_id,
        conversation=[
            Invocation(
                invocation_id="inv1",
                user_content=_content(question),
                intermediate_data=IntermediateData(tool_uses=[_fc(tool_name, **tool_args)]),
            )
        ],
        session_input=_session("eval-golden-legal", question=question),
    )
    for eval_id, question, tool_name, tool_args in _ASK_CASES
]

ask_set = EvalSet(
    eval_set_id="ask_ouroboros",
    name="AskOuroboros",
    description=(
        "PHASE_09.md 9.2 -- 5 cases, one per real evidence source AskOuroboros can "
        "reach for (a ledger claim list/lookup, a private-corpus precedent search, a "
        "live Parallel-grounded web question), matching "
        "agents/ouroboros/prompts/ask_ouroboros.md's own worked examples."
    ),
    eval_cases=ask_cases,
)


if __name__ == "__main__":
    all_sets = (
        ("claim_triage", triage_set),
        ("risk_assessor", risk_set),
        ("music_agent", music_set),
        ("brand_agent", brand_set),
        ("person_agent", person_set),
        ("location_art_agent", location_art_set),
        ("fact_agent", fact_set),
        ("ask_ouroboros", ask_set),
    )
    for name, eval_set in all_sets:
        path = _EVALS_DIR / f"{name}.evalset.json"
        path.write_text(
            json.dumps(eval_set.model_dump(mode="json", exclude_none=True), indent=2) + "\n"
        )
        print(f"wrote {path}")
