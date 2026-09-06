# evals/adk

ADK eval sets for every real-reasoning agent in the tree: `ClaimTriage`/`RiskAssessor`
(PHASE_05.md §5.2/§5.4), the four CLEAR specialists + `FactAgent` (PHASE_09.md §9.2,
each verifying its own real `list_claims(project_id, category, status="triaged")`
batch-discovery call — the deterministic 7-step verification algorithm itself,
`specialist.py::_verify_one_claim`, doesn't need a separate eval), and `AskOuroboros`
(evalset exists but isn't run in CI — see "AskOuroboros" below).

## Running

Needs `google-adk`'s optional `[eval]` extra (pulls in `pandas` and friends). It's
deliberately **not** a project dependency — installing it into the shared `uv.lock`
pulled a starlette downgrade that would have shipped to every FastAPI service in this
repo, found live. Use `uv run --with` for an isolated overlay instead:

```
DB_HOST=localhost DB_NAME=ouroboros DB_USER=app DB_PASSWORD=localdev \
TOOLBOX_MCP_URL=http://localhost:5001 \
uv run --with "google-adk[eval]" --env-file .env python -c "
import asyncio
from google.adk.evaluation.agent_evaluator import AgentEvaluator
asyncio.run(AgentEvaluator.evaluate(
    agent_module='agents.ouroboros.agent',
    eval_dataset_file_path_or_dir='evals/adk/claim_triage.evalset.json',
    agent_name='ClaimTriage',
    num_runs=1,
))
"
```

Swap in `risk_assessor.evalset.json` / `agent_name='RiskAssessor'`, or any of
`music_agent`/`brand_agent`/`person_agent`/`location_art_agent`/`fact_agent`
(`agent_name='MusicAgent'`/`'BrandAgent'`/`'PersonAgent'`/`'LocationArtAgent'`/
`'FactAgent'`) for the others. `test_config.json` (auto-discovered by
`AgentEvaluator`) sets the passing criteria: `tool_trajectory_avg_score` ≥ 0.6,
`ANY_ORDER` match — see `generate.py`'s comments for why the threshold is lenient and
why only one tool call per case is asserted.

**mind the exact-match trap**: ADK's trajectory scorer requires *full dict equality*
on a matched call's args, even under `ANY_ORDER` (only call *order* is forgiving, not
a given call's own args) — found live, repeatedly, building the specialist sets:
`ClaimTriage` reliably calls `list_claims` bare (`{project_id}` only) at least once
per turn, but a specialist's own call is reliably a **three-key** exact match
(`project_id`, `category`, `status="triaged"`) every time — verified against 6+ real
runs each before committing to either shape. Don't guess this from a single run.

Fixture data, all real local-dev, no live `demo`/prod data touched:
- `ClaimTriage`: `scripts/seed_eval_fixtures.py` (5 small, isolated `eval-triage-N`
  projects).
- `RiskAssessor`: the real `demo` project's already-verified claims — run a real local
  CLEAR pass first (`scripts/seed.py` + a batch of claims through the pipeline) if
  those don't have Evidence yet.
- The four specialists + `FactAgent`: `evals/golden/{legal,factual}.yaml`'s own claims
  (`eval-golden-legal`/`eval-golden-factual`), seeded via
  `evals/run_golden.py::_seed_legal_project`/`_seed_factual_project` (idempotent,
  deterministic `claim_id`s — safe to call again before every eval run; PHASE_09.md
  §9.1's own golden set is the same fixture data, not duplicated).

## AskOuroboros

`ask_ouroboros.evalset.json` exists (5 cases, one per real evidence source
AskOuroboros can reach for) but is **not** run in CI's automated loop
(`.github/workflows/evals.yml`). Found live: `tool_trajectory_avg_score`'s exact-args
matching is a poor fit here — unlike a specialist's fixed category/status args,
AskOuroboros's own tool calls (`search_private_corpus(query=...)`,
`get_prior_decisions(entity_normalized=...)`) carry a model-composed free-text query
that legitimately varies run to run, and the model doesn't reliably check the ledger
*first* the way its own prompt's numbered steps suggest (observed exploring
`search_private_corpus`/`get_prior_decisions` before `list_claims` in one real run).
Kept as a real, hand-authored artifact and a starting point for a better-fitting
metric (`response_match_score` against a reference answer, or a custom LLM-judged
metric) rather than deleted — see `docs/DECISIONS.md` for the full note.

## Regenerating

`generate.py` builds every `.evalset.json` file from the real ADK `EvalCase`/`EvalSet`
schema (not hand-written JSON):

```
uv run --with "google-adk[eval]" python evals/adk/generate.py
```
