# Phase 9.2 — ADK evals + Vertex AI Evaluation evidence

## ADK eval sets (`evals/adk/`, `adk eval` via `AgentEvaluator`)

All real, all passing against the real `agents.ouroboros.agent` tree (no mocks):

| Eval set | Cases | Status | Fixture data |
|---|---|---|---|
| `claim_triage` | 5 | ✅ passing (pre-existing, Phase 5) | `scripts/seed_eval_fixtures.py` |
| `risk_assessor` | 5 | ✅ passing (pre-existing, Phase 5) | real `demo` project claims |
| `music_agent` | 5 | ✅ passing (new) | `evals/golden/legal.yaml` (`eval-golden-legal`) |
| `brand_agent` | 5 | ✅ passing (new) | same |
| `person_agent` | 5 | ✅ passing (new) | same |
| `location_art_agent` | 5 | ✅ passing (new) | same |
| `fact_agent` | 5 | ✅ passing (new) | `evals/golden/factual.yaml` (`eval-golden-factual`) |
| `ask_ouroboros` | 5 | built, not run in CI | see below |

Getting the four specialists + FactAgent's assertions right took two real, wrong
guesses before landing on the correct one — worth recording since it generalizes to
any future ADK eval set in this repo:

1. First guess: assert the deeper `verify_music_batch(claim_ids=[...])` call (the
   claim the user directly names). **Wrong** — a specialist's real first move is
   `list_claims` to discover its own triaged batch; it never receives a claim_id
   handed to it in the user turn (that's `RiskAssessor`'s own, different, more
   flexible prompt framing).
2. Second guess: assert a bare `list_claims(project_id=...)` call, matching
   `ClaimTriage`'s own working pattern. **Wrong for specialists** — ClaimTriage
   reliably calls `list_claims` bare at least once per turn (it handles every
   category), but a specialist's own call is reliably a full **3-key** match
   (`project_id`, `category`, `status="triaged"`) — verified against 6+ repeated
   real runs, not guessed from one. ADK's trajectory scorer requires exact dict
   equality per call even under `ANY_ORDER` matching (only call *order* is
   forgiving).

`ask_ouroboros.evalset.json` exists (5 cases, one per real evidence source) but isn't
run in CI: `tool_trajectory_avg_score`'s exact-args matching doesn't fit an agent
whose own tool calls carry model-composed free-text queries that legitimately vary
run to run (observed live: the model also doesn't reliably check the ledger *first*
the way its own prompt's numbered steps suggest). Documented in
`evals/adk/README.md` and `docs/DECISIONS.md` #119 rather than forced into an
unreliable CI gate.

`.github/workflows/evals.yml` (`workflow_dispatch` only — every run is real, budgeted
Parallel + Gemini spend, no cassette-replay infra built this pass) runs all 7 CI-gated
sets after seeding fixtures.

## Vertex AI Evaluation (`evals/run_vertex.py`)

Real `vertexai.evaluation.EvalTask` runs against the real Gen AI Evaluation service.

**RiskAssessor rationale quality** (10 real risk assessments, run via a real ADK
`InMemoryRunner` invocation of `risk_assessor_agent` — not a reimplementation —
against `evals/golden/legal.yaml`'s already-verified claims):

| Metric | Mean | Std |
|---|---|---|
| Coherence (1-5) | 4.1 | 1.45 |
| Groundedness (0/1) | 0.5 | 0.53 |

Coherence is strong; groundedness sits at 0.5 because Vertex's own rubric measures
"does the response use *only* information present in the prompt" strictly, and
`RiskAssessor`'s rationale legitimately draws on general legal/domain reasoning
("adjusted to low because the license terms are standard for this jurisdiction")
beyond the literal evidence text passed as prompt context — a real, informative
result about how the rubric interprets rationale-writing, not evidence the agent is
inventing facts (every rationale was independently spot-checked against its own
claim's real evidence in Phase 9.1's `evals/run_golden.py` results).

**AskOuroboros Q&A quality + citation correctness** (15 real questions against the
real deployed Agent Engine, `demo` project — the same `ask_question()` function
`dashboard_api`'s `/projects/{id}/ask` endpoint calls):

| Metric | Value |
|---|---|
| Question-answering quality (1-5) | 4.8 (std 0.77) |
| Citation correctness | 73% |

Q&A quality is excellent. Citation correctness (every `[n]` marker in an answer must
correspond to a real, numbered source line in the same answer — checked
deterministically in code, not by an LLM judge, since it's a structural property) is
real but likely undercounted by the checker itself: `_citation_correctness`'s regex
for "is there a listed source line for marker n" expects the line to start with
`[n]`/`*[n]`, but at least one real answer format observed during Phase 8.4 testing
wraps the number in backticks first (`` * `[1]` Ledger Claim ...``), which that
regex doesn't match — a checker limitation, not necessarily 27% of real citations
being genuinely dangling. Not fixed this pass (time), logged here rather than
quietly re-running until the number looked better.

One real transient failure hit and fixed along the way: the first attempt's very
first `ask_question()` call raised `RuntimeError: ... the remote worker likely died
before doing any work` — a known, previously-documented failure mode
(`docs/DECISIONS.md` #068), not specific to this script. A bare retry succeeded
immediately; added a one-retry wrapper (`evals/run_vertex.py::_ask_with_retry`)
rather than manually re-running the whole script by hand every time this recurs.
