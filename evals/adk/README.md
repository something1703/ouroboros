# evals/adk

ADK eval sets for CLEAR's LLM-judgment sub-agents (PHASE_05.md §5.2/§5.4): `ClaimTriage`
and `RiskAssessor` — the two agents where the LLM does real reasoning, not a
deterministic passthrough (see `agents/ouroboros/clear/specialist.py`'s docstring on
why the four category specialists don't need one).

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

Swap in `risk_assessor.evalset.json` / `agent_name='RiskAssessor'` for the other set.
`test_config.json` (auto-discovered by `AgentEvaluator`) sets the passing criteria:
`tool_trajectory_avg_score` ≥ 0.6, `ANY_ORDER` match — see `generate.py`'s comments for
why the threshold is lenient and why only one tool call per case is asserted.

Both eval sets need real local-dev fixture data:
- `ClaimTriage`: `scripts/seed_eval_fixtures.py` (5 small, isolated `eval-triage-N`
  projects).
- `RiskAssessor`: the real `demo` project's already-verified claims — run a real local
  CLEAR pass first (`scripts/seed.py` + a batch of claims through the pipeline) if
  those don't have Evidence yet.

## Regenerating

`generate.py` builds both `.evalset.json` files from the real ADK `EvalCase`/`EvalSet`
schema (not hand-written JSON):

```
uv run python evals/adk/generate.py
```
