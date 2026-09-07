# PHASE 09 — Quality: evaluation, hardening, observability, cost

**Goal:** Prove the system is correct, safe, observable and affordable — with numbers in the README. This phase converts "it works on my machine" into evidence a judge can verify in five minutes.

**Calendar:** Day 8 (afternoon).
**Blocking inputs:** Phases 1–8.
**Reads first:** `ADK_AGENTS.md §7`, `AGENTS.md §6`.

---

## 9.1 Golden set

**Tasks**
- `evals/golden/legal.yaml` (25 claims) and `evals/golden/factual.yaml` (25 claims) with expected key fields: e.g., composition rights holder for a famous song; trademark owner for a global brand; living/deceased for a public figure; public-domain status for a landmark; supported/contradicted for well-documented events and statistics. Mix jurisdictions (`in, us, gb, de, jp`) and languages (5 Hindi/Spanish claim texts).
- Human spot-check request written to `docs/BLOCKERS.md` (20 items) — proceed while awaiting.
- Runner `evals/run_golden.py`: verifies each via the same code path as the specialists (core-fast), computes field accuracy, citation presence, confidence calibration (how often `high` is correct), cost, latency; writes `evals/results/<date>.json` and a markdown table.

**Acceptance**
- Field accuracy ≥ 85% legal, verdict accuracy ≥ 85% factual; `high` confidence precision ≥ 90%; results table in `docs/evidence/09-golden.md`.

## 9.2 Vertex AI Evaluation + ADK evals in CI

**Tasks**
- ADK eval sets for `ClaimTriage`, specialists (one each), `RiskAssessor`, `FactAgent`, `AskOuroboros` (≥ 5 cases each) run via `adk eval` in CI on cassettes.
- Vertex AI Evaluation (Gen AI evaluation service) with rubric-based metrics: `RiskAssessor` rationale quality (coherence, grounded in evidence), `AskOuroboros` groundedness and citation correctness on 15 Q&A pairs. Runner `evals/run_vertex.py`; results stored; `make evals`.

**Acceptance**
- CI job `evals` green; Vertex scores recorded in README table.

## 9.3 Security hardening

**Tasks**
- Threat checklist in `docs/SECURITY.md` and verify each: webhook signature + replay window; Toolbox public proxy read-only + token + rate limit; Model Armor on every untrusted text path (grep test that `screen()` is called in ingest, search, extract, task-output paths); IAP on UI; SAs least privilege (`gcloud projects get-iam-policy` diff against `infra/README.md`); no secrets in logs (log scrubber test); Cloud Run ingress settings audited; Firestore rules deny client writes; dependency audit (`pip-audit`, `npm audit`).
- Prompt-injection red-team: 10 planted excerpts (in a synthetic script and in a mocked web result) attempting to alter verdicts or exfiltrate; assert none change outputs.

**Acceptance**
- `docs/SECURITY.md` with pass/fail per item, all pass; red-team test suite green.

## 9.4 Observability

**Tasks**
- Dashboards (Cloud Monitoring): requests/errors/latency per service; Parallel spend per project (from `cost_events` via log-based metric or BigQuery); monitor events per day; re-verification latency (webhook → evidence written).
- Alerts: error rate > 5% (any service), spend > 80% of cap, webhook 401 spike, dead-letter messages > 0.
- Trace exemplars linked from the README ("one claim, one trace").

**Acceptance**
- Screenshots in `docs/evidence/09-observability/`; an induced failure (kill Toolbox) triggers the error alert and the UI shows claims as `error`, not crashes.

## 9.5 Resilience & idempotency tests

**Tasks**
- Chaos tests: Parallel 500s (mock) → retries then `error`; Task `failed` → not billed, marked; duplicate webhooks → single evidence; ingest re-run → no dupes; agent run restarted mid-batch → resumes from `pending/triaged` only.
- Budget test: set cap $1 on a scratch project → batch stops gracefully, UI shows budget notice.

**Acceptance**
- All pass in CI (mocked) and once live in `dev` (evidence).

## 9.6 Cost & performance report

**Tasks**
- Measure and record: full CLEAR pass cost/time; TRUE CUT pass; daily monitor cost; Gemini spend; Cloud Run/SQL run-rate. Produce `docs/COST.md` with a per-project unit-economics table and the "under $7 per script" claim backed by data.
- Tune: concurrency, `basic` vs `fast` where quality demanded it, cache Entity Search results per entity per day.

**Acceptance**
- `docs/COST.md` complete; numbers reused in README and demo script.

## 9.7 Freeze `demo` environment

**Tasks**
- Deploy `main` to `demo`; seed the demo project; run CLEAR + TRUE CUT; confirm monitors are active with the webhook pointing at `demo`; set `SUBMISSION_AT`; snapshot Cloud SQL.
- From here, `demo` receives only hotfixes via `main`.

**Acceptance**
- `demo` URL works with IAP; feed shows live events; drift non-zero after the first monitor cycle.

---

## Exit gate
- [ ] README metrics table populated from real runs (accuracy, cost, latency, security checklist link).
- [ ] `demo` frozen and monitored.
- [ ] Squash-merge.

## Risks
- **Golden-set labelling time** → agent drafts labels from Task `pro` runs on 50 items ($5) and the human spot-checks 20; disagreements resolved by the human.
- **Vertex evaluation API changes** → vendor the current docs page; if blocked > 2h, fall back to ADK evals + a Gemini-as-judge script and note it in `docs/DECISIONS.md`.
