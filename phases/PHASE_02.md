# PHASE 02 — Claim Ledger

**Goal:** The system of record exists, is migrated, is reachable through the MCP Toolbox for Databases, mirrors to Firestore and BigQuery, and is fully typed. Everything downstream writes to and reads from this.

**Calendar:** Day 1 evening → Day 2 morning.
**Blocking inputs:** Phase 1 exit; `00_REQUIREMENTS §B3` (demo project metadata).
**Reads first:** `DATA_MODEL.md` (all), `ARCHITECTURE.md §2.2`.

---

## 2.1 Domain models (`packages/claims/`)

**Tasks**
- Implement every Pydantic model in `DATA_MODEL.md §1` exactly. Include `Claim.compute_id()` and `normalize_text()` (NFKC, lowercase, strip punctuation/whitespace, collapse spaces; keep diacritics).
- `packages/claims/risk.py`: deterministic pre-score function `prescore(evidence, claim, jurisdictions) -> (RiskLevel, float, rationale_bullets)` implementing the rubric in `ADK_AGENTS.md §2.3`.
- `packages/claims/drift.py`: `reality_drift(claims_with_history) -> DriftResult` per `DATA_MODEL.md §6`.
- Property-based tests (hypothesis): normalization is idempotent; `claim_id` stable across re-runs; drift ∈ [0,1].

**Acceptance**
- `mypy --strict packages/claims` clean; ≥ 30 unit tests pass.

## 2.2 Cloud SQL + migrations (`packages/ledger/`)

**Tasks**
- Terraform: Cloud SQL PostgreSQL 16, smallest tier (`db-f1-micro` or `db-custom-1-3840`), private IP, automated backups, `ouroboros` database, `app` user with password from Secret Manager.
- SQLAlchemy 2 models for every table in `DATA_MODEL.md §3`; Alembic `0001_initial`.
- Repository layer: `ProjectRepo, AssetRepo, ClaimRepo, EvidenceRepo, RiskRepo, HistoryRepo, MonitorRepo, CostRepo, PriorDecisionRepo` with **upsert-by-id** semantics and transactional helpers (`record_evidence_and_status` does evidence insert + history append + claim status update in one transaction).
- `scripts/seed.py`: creates the demo project from `fixtures/projects/demo.yaml`, three prior decisions for the demo studio.

**Acceptance**
- `alembic upgrade head` on Cloud SQL (via Cloud SQL Auth Proxy) and on local postgres.
- Integration tests (local postgres in CI via service container): upsert idempotency, transaction rollback on failure, index usage on `claims(project_id,status)` (EXPLAIN in a test).

## 2.3 MCP Toolbox for Databases (`services/toolbox/`)

**Tasks**
- `tools.yaml`:
  - `sources.ouroboros_pg` (cloud-sql-postgres; IAM auth for Cloud Run; password auth locally).
  - Tools (parameterized SQL, read-only unless stated):
    - `get_claim(claim_id)` → claim + latest evidence + risk.
    - `list_claims(project_id, status?, category?, limit=50)`.
    - `get_prior_decisions(studio_id, entity_normalized)`.
    - `get_project(project_id)`.
    - `record_evidence(evidence_json)` **write** — inserts evidence + history, guarded by a CHECK that `cycle` is next.
    - `set_status(claim_id, status, note, ref_json)` **write**.
  - Toolsets: `ledger_read` (first four), `ledger_write` (last two), `parallel_readonly` = `ledger_read` only.
- Dockerfile wrapping the official Toolbox image with the config; Cloud Run service `toolbox` (internal ingress + IAM auth; the public Parallel-facing path is added in Phase 5.6 with a bearer token).
- Python access: `toolbox-core` `ToolboxSyncClient` helper in `packages/ledger/toolbox_client.py` that loads toolsets as ADK-compatible tools.

**Acceptance**
- `curl` against the Toolbox MCP endpoint lists the six tools.
- ADK smoke test: a throwaway `LlmAgent` with `ledger_read` tools answers "list pending claims for project demo" correctly against seeded data.

## 2.4 Firestore projections (`packages/ledger/projections.py`)

**Tasks**
- Functions `project_summary(project_id)`, `claim_view(claim_id)`, `event_entry(...)`, `run_progress(...)` that build the documents in `DATA_MODEL.md §4` from ledger rows and write them (batched, idempotent by doc id).
- A `Projector` service class invoked by every writer (ingest, agents, workers) after commits. Single-writer rule: Firestore is derived; never the source.
- Security rules: deny all client writes; reads only via the dashboard API (server-side) — the React app reads through `dashboard_api` SSE/REST, not directly. (Keeps IAP the only auth boundary.)

**Acceptance**
- Seed → `projects/demo` exists with correct counts; updating a claim status updates the claim doc within 1s (test).

## 2.5 BigQuery mirror

**Tasks**
- Terraform: dataset `ouroboros`, tables matching ledger (partition by `DATE(created_at)`), view `claims_for_enrichment` (claim_id, entity_text, category, jurisdictions) for Phase 7.5.
- `services/dashboard_api/jobs/bq_sync.py`: nightly full mirror via Cloud Scheduler → Cloud Run job; `cost_events` streamed via `insert_rows_json` on write.

**Acceptance**
- After seed + one manual sync, `SELECT COUNT(*) FROM ouroboros.claims` matches Cloud SQL.

## 2.6 Cost meter

**Tasks**
- `packages/parallel_client/cost.py` price table + `CostMeter(project_id)` context manager writing `cost_events` (estimate → actual).
- `ProjectRepo.spend(project_id)`; `BudgetExceeded` raised when projected spend > cap.
- Also meter Gemini calls (token-based estimate from `usage_metadata`; prices in `config/models.py`) so the dashboard shows total spend.

**Acceptance**
- Unit tests for every SKU; a test that the 11th $1 call against a $10 cap raises.

---

## Exit gate
- [ ] All 2.x acceptance criteria pass; evidence in `docs/evidence/02-*`.
- [ ] `make seed` idempotent (run twice → same row counts).
- [ ] Toolbox reachable from a local ADK agent and from Cloud Run.
- [ ] Squash-merge.

## Risks
- Cloud SQL private IP + Cloud Run connector misconfig is the classic day-one sink → follow the Toolbox Cloud Run + Cloud SQL guide verbatim; test with the Auth Proxy first.
- Toolbox IAM auth vs password auth differences local/cloud → keep both source definitions in `tools.yaml` selected by env var.
