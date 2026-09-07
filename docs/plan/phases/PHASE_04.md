# PHASE 04 — Parallel integration layer

**Goal:** A typed, metered, tested `packages/parallel_client/` that implements every contract in `PARALLEL_INTEGRATION.md`. After this phase, no other code ever imports `parallel` directly, and a CLI can verify a single claim end-to-end from the terminal.

**Calendar:** Day 3.
**Blocking inputs:** Phase 2 exit (cost meter, ledger); Parallel API key.
**Reads first:** `PARALLEL_INTEGRATION.md` (all), `DATA_MODEL.md §2`.

---

## 4.1 Client core

**Tasks**
- `client.py`: one lazily-constructed `Parallel(api_key=get_secret("PARALLEL_API_KEY"), timeout=60)`; retry wrapper per `PARALLEL_INTEGRATION.md §6`; every call tagged with `metadata={"env": OUROBOROS_ENV, ...}` where the API supports metadata (Task, Monitor).
- Structured logging of `api, sku, latency_ms, warnings, claim_id`.
- Fetch and store the latest docs pages as markdown under `docs/vendor/parallel/` (`search`, `task-quickstart`, `specify-a-task`, `access-research-basis`, `monitor-quickstart`, `quickstart-snapshot`, `webhook-setup`, `responses-quickstart`, `entity-search`, `extract-quickstart`, `mcp-tool-call`, `memory`) by appending `.md` to each URL. Re-check SDK method names against these before coding.

**Acceptance**
- `python -m parallel_client.smoke` performs one turbo search and prints cost; `cost_events` row exists.

## 4.2 Search wrapper

**Tasks**
- Implement `search()` per §4.1 of the integration doc, including `SUPPORTED_LOCATIONS` guard, default `exclude_domains` for legal categories, `session_id` passthrough, Model Armor screening of excerpts.
- Objective builder `build_objective(category, entity_text, jurisdictions) -> (objective, queries)` using `config/jurisdictions.yaml` hints; unit-tested for each category.

**Acceptance**
- Cassette tests for fast/basic modes; a test asserting `include_domains` is never set unless explicitly passed; screened excerpts never contain the planted injection string.

## 4.3 Task wrapper + specs

**Tasks**
- `specs/loader.py` validating every JSON in `specs/` against §3 rules at import; fails fast with the offending rule.
- Author the five specs from `DATA_MODEL.md §2` (`legal_music`, `legal_brand`, `legal_person`, `legal_location_artwork`, `factual_claim`) and `factual_quick`.
- `task.run()` per §4.2: input builder with 4k-char cap, `mcp_servers` attachment (URL from env; token from Phase 5.6 — accept `None` for now), `previous_interaction_id`, `memory_scope_key`, `wait` mode with `api_timeout`, non-wait mode returning `RunHandle`.
- `basis.py`: parse to domain `FieldBasis[]`; `overall_confidence` min-rule over required fields; per-element entries kept but not required.
- Escalation helper `should_escalate(evidence, claim) -> bool` per `ADK_AGENTS.md §2.2 step 6`.

**Acceptance**
- Cassettes for each spec (famous song, major brand, living public figure, a landmark, a well-documented historical event). Parsed `Evidence` objects validate. A deliberately invalid spec in a test raises at import.

## 4.4 Responses, Entity Search, Extract

**Tasks**
- `responses.ask()` with structured output schema `factual_quick`; map citations/annotations → `Citation[]`.
- `entity.search()` → normalized results.
- `extract.extract()` with ≤ 5 URLs, objective, Model Armor screening; returns markdown + excerpts.

**Acceptance**
- Cassette tests; p50 latency recorded in `docs/evidence/04-latency.md` (Responses medium ~15–20s expected).

## 4.5 Monitor + Memory wrappers

**Tasks**
- `monitor.create_snapshot / create_stream / update / cancel / events` per §4.6, with `metadata` routing keys and the frequency policy function `frequency_for(days_to_release)`.
- `memory.retrieve()`; graceful no-op if the org has memory disabled (log once).
- `webhooks.py`: event models for `monitor.event.detected` and Task run status events; signature verification implemented per the fetched `webhook-setup.md` (document the header/algorithm in code comments).

**Acceptance**
- Unit tests for frequency policy boundaries (61→1w, 60→1d, 8→1d, 7→1h). Webhook signature test vectors (valid, tampered, replayed).

## 4.6 Verification CLI (developer tool, later reused by agents)

**Tasks**
- `scripts/verify_claim.py --claim-id X [--processor core-fast] [--escalate]` runs: search → task → basis → prescore → prints a table and writes Evidence to the ledger (flag `--dry-run` to skip writes).
- `scripts/verify_batch.py --project demo --category music --concurrency 5`.

**Acceptance**
- Running the batch on the seeded demo project's music claims produces Evidence rows with citations and confidence; total cost printed and matches `cost_events`.

---

## Exit gate
- [ ] 100% of `packages/parallel_client` covered by cassette or unit tests; `make test` offline-green.
- [ ] One real end-to-end `verify_claim` transcript saved to `docs/evidence/04-verify.txt` showing Basis with ≥ 2 citations and a confidence.
- [ ] Spend so far logged; still < $2 Parallel.
- [ ] Squash-merge.

## Risks
- SDK method names may differ from this plan (`client.task_run.create` vs others) → the vendored docs in 4.1 are authoritative; adapt wrappers, keep the public function signatures.
- Task latency variance → default `core-fast`; batch concurrency 5–10; UI must never block on a Task.
