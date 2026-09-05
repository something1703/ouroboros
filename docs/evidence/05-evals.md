# Phase 5.2 / 5.4 — ADK eval set evidence

`evals/adk/claim_triage.evalset.json` and `evals/adk/risk_assessor.evalset.json`, 5
real cases each — see `evals/adk/README.md` for how to run them and `generate.py`'s
comments for the full design rationale (`docs/DECISIONS.md` #058 covers the two real
findings that shaped it: `tool_trajectory_avg_score`'s exact-args matching against real,
somewhat inconsistent model behavior, and `RiskAssessor`'s claim_ids coming from
conversation history rather than session state in the real pipeline).

## Both sets pass, 10/10, against the real local agent

```
$ DB_PASSWORD=localdev uv run --with "google-adk[eval]" --env-file .env python -c "..."
=== ClaimTriage ===
... 5 cases, no EvalStatus.FAILED lines ...
=== RiskAssessor ===
... 5 cases, no EvalStatus.FAILED lines ...
$ echo $?
0
```

Fixture data: `scripts/seed_eval_fixtures.py` (5 small, isolated `eval-triage-N`
projects covering: a simple no-prior-decision case, a prior-decision skip, a
multi-category batch, an `artwork` claim exercising the shared `location_artwork`
spec, and an unrelated-prior-decision case confirming the skip logic is entity-specific
rather than project-wide) for `ClaimTriage`; the real `demo` project's already-verified
local-dev claims (real Evidence + prescores from a real local CLEAR pass) for
`RiskAssessor`.
