# PHASE 05 — CLEAR: the legal-claims head on Agent Engine

**Goal:** A deployed ADK multi-agent system that takes a project/asset, triages claims, fans out across four specialists, produces Evidence + Risk for every claim, writes E&O-ready summaries, and creates Monitors for high-risk findings. Parallel Task runs can call back into our Toolbox MCP.

**Calendar:** Day 4 → Day 5 (morning).
**Blocking inputs:** Phases 2–4 exit.
**Reads first:** `ADK_AGENTS.md` (all), `ARCHITECTURE.md §2.3`.

---

## 5.1 ADK app skeleton (`agents/ouroboros/`)

**Tasks**
- `agent.py` exports `root_agent = OuroborosCoordinator`.
- `tools/` implements every shared tool in `ADK_AGENTS.md §0` as ADK `FunctionTool`s with docstrings that double as tool descriptions; ledger tools loaded from Toolbox via `toolbox-core` (`ledger_read`, `ledger_write` toolsets).
- `prompts/` with one markdown per agent following `ADK_AGENTS.md §6` checklist; a `render(prompt_name, **vars)` helper injecting `{{jurisdictions}}`, `{{objective_hint}}`, `{{release_date}}`.
- `adk web` runs locally against the local Toolbox; `adk run` scripts for each head.

**Acceptance**
- `adk web` shows the agent tree; the coordinator routes `mode=clear` to `CLEAR` and refuses to research itself (test with a "find the rights holder of X" prompt → it transfers).

## 5.2 `ClaimTriage`

**Tasks**
- Implement per `ADK_AGENTS.md §2.1` with `output_schema=TriageOutput`.
- Dedupe across assets of the same project by `normalized_text`+`category` (keep both source refs).
- Prior-decision skip rule; memory retrieve (optional) attached as quoted `prior_context`.
- Writes status `triaged` via `set_status` with history note.

**Acceptance**
- On the demo project, produces four batches; a claim with a seeded prior decision lands in `skipped`. ADK eval set `evals/adk/claim_triage.evalset.json` (5 cases) passes.

## 5.3 Specialists (`clear/specialist.py` + four thin agents)

**Tasks**
- Shared `verify_batch(batch, category, spec, extra_tools)` implementing the 7-step algorithm in `ADK_AGENTS.md §2.2` with `asyncio.Semaphore(5)`; the LLM writes objectives/queries via a small structured call, everything else is code.
- Per-claim `firestore.write_run_progress`.
- `MusicAgent` adds Entity Search when `composition_rights_holder`/`master_rights_holder` are null.
- `BrandAgent` adds Extract on `brand_clearance_policy_url` if present and re-runs a `lite-fast` Task to summarize depiction guidelines (cheap).
- `PersonAgent` Entity Search for estates/agents; `LocationArtAgent` Extract on permit pages.
- Error isolation: one claim's failure never aborts the batch; recorded as `error` with message.

**Acceptance**
- Music batch on demo project: ≥ 90% of claims end `verified`/`escalated`; each Evidence has ≥ 1 citation; escalation triggers on a planted low-confidence priority-1 claim (use a cassette). Batch of 20 claims completes < 6 min with core-fast.

## 5.4 `RiskAssessor` and `Reporter`

**Tasks**
- `RiskAssessor`: reads Evidence, calls `prescore`, may adjust ±1 level with rationale; writes `risk` + `risk_history` + Firestore claim view; `territory_flags` per jurisdiction derived from `territory_notes`.
- `Reporter`: 60-word summaries with `[n]` citation indices; creates Monitors (snapshot for high/blocking; event_stream for litigious brands/persons) via `parallel.monitor_create` with `frequency_for(days_to_release)` and webhook URL from env; writes `report_md` into latest Evidence output; updates project summary.
- Both use `gemini-3.1-pro-preview`, temperature 0.3, structured outputs.

**Acceptance**
- Every verified claim has a Risk; distribution is sane on demo data (not all `high`). Monitors exist in Parallel for every high/blocking claim and are recorded in `monitors` table. `evals/adk/risk_assessor.evalset.json` (5 cases) passes.

## 5.5 Agent Engine deployment (`agents/deploy/`)

**Tasks**
- `deploy.py` using `vertexai.agent_engines` (`AdkApp` wrapper): requirements pinned, env vars (Toolbox URL, project, env), `sa-agent-engine` with Secret Manager + Firestore + Pub/Sub + Cloud SQL client roles.
- `dashboard_api` endpoint `POST /projects/{id}/runs` that creates a session and calls `stream_query` on the deployed engine; persists `runs/{run_id}` progress to Firestore; returns `run_id`.
- A Pub/Sub push subscription on `claims.extracted` → `dashboard_api /internal/runs/auto` that starts a CLEAR run automatically after ingest (feature flag `AUTO_RUN_AFTER_INGEST=true`).
- Update `deploy.yml` to redeploy the engine on `main`.

**Acceptance**
- `AGENT_ENGINE_RESOURCE_NAME` set; a run started from the API completes on the demo project; Cloud Trace shows spans across API → Engine → Parallel.

## 5.6 Two-way MCP: expose Toolbox to Parallel Task runs

**Tasks**
- Add a **public** Cloud Run route for Toolbox (or a thin proxy service `services/toolbox_public/`) that: requires `Authorization: Bearer <static token from Secret Manager PARALLEL_MCP_TOKEN>`, exposes **only** the `parallel_readonly` toolset, rate-limits 60 req/min, logs every call with `tool_name` and caller.
- `task.run()` attaches this server as `mcp_servers` with `allowed_tools=["get_claim","get_prior_decisions","list_claims"]`.
- Dashboard shows, per Evidence, the `mcp_tool_calls` Parallel made (from the Task result) — a visible "Parallel asked Ouroboros about…" line.

**Acceptance**
- A Task run on a claim with a seeded prior decision shows an `mcp_tool_calls` entry naming `get_prior_decisions`; the proxy log shows the call; an unauthenticated request is rejected.

## 5.7 Full CLEAR pass on the demo project

**Tasks**
- Run end-to-end from ingest to report on `sample_en.pdf`; capture timings, cost, risk distribution to `docs/evidence/05-clear-pass.md`.
- Fix prompt issues found (over/under-escalation, empty territory notes).

**Acceptance**
- ≥ 95% of claims have Evidence; total Parallel cost < $8; wall time < 25 min; ≥ 3 Monitors created.

---

## Exit gate
- [ ] 5.1–5.7 green with evidence.
- [ ] `make deploy` redeploys Agent Engine; a run can be triggered from the API.
- [ ] `docs/DECISIONS.md` updated with any prompt/rubric adjustments.
- [ ] Squash-merge.

## Risks
- **Agent Engine cold starts / packaging** → keep dependencies minimal in the engine image; do heavy lifting in `packages/`.
- **LLM drifting from structured outputs** → `output_schema` everywhere; temperature ≤ 0.3; eval sets.
- **Toolbox public exposure** → read-only toolset, bearer token, rate limit, audit log. Never expose write tools to Parallel.
