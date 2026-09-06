# Phase 9.5 — Resilience & idempotency evidence

Audited all 6 of PHASE_09.md §9.5's chaos/resilience properties against the real
code first (not assumed), then built the tests that were genuinely missing. 3 of 6
already had solid coverage; 1 is a real, disclosed gap; 2 are prompt-driven (LLM
behavior) and verified by design + existing live evidence rather than a new offline
test.

## 1. Parallel 500s → retry, then marked error (not crash) — gap closed

`packages/parallel_client/client.py::call()`'s default retry policy already includes
the real `parallel.InternalServerError` (not just a stand-in fake), backing off
`(1, 4, 16)` before raising `ParallelError`; `agents/ouroboros/clear/specialist.py`'s
`verify_batch._one()` already isolates that failure per-claim. **Gap**: the existing
tests (`tests/packages/parallel_client/test_client.py`) only ever exercised this with
an explicit `retryable_errors=(_FakeStandIn,)` override, never the real default tuple
end to end. Added `test_call_retries_the_real_parallel_500_by_default` and
`test_call_exhausts_real_parallel_500_and_raises_parallel_error` (constructing a real
`parallel.InternalServerError` via a real `httpx.Response(500, ...)`), plus
`tests/agents/ouroboros/clear/test_specialist_resilience.py::
test_one_claims_parallel_failure_is_isolated_from_the_rest_of_the_batch` — a real
`verify_batch` call (only Parallel/ledger I/O mocked) confirming one claim's real
`ParallelError` ends up `status="error"` while a sibling claim in the same batch
still completes and gets real evidence written.

## 2. Task `status="failed"` → marked, but billing is a real, disclosed open gap

Marking is correctly implemented in two places (`reverify_worker/main.py`'s
`_record_task_failure`, `specialist.py`'s catch-all → `"error"`). **Billing is not
conditioned on outcome anywhere**: `packages/parallel_client/cost.py`'s `CostMeter`
records the *estimated* cost before a call runs (a pre-flight reservation), and
`CostMeter.record_actual()` — built specifically to correct that estimate afterward —
is never called from any production code path (only from its own unit test). So
today, a Task run that later comes back `"failed"` is billed the same as a
successful one.

**Not fixed this pass, deliberately** — this needs a business/product answer this
session doesn't have with confidence: *does Parallel itself charge for a Task run
that fails on their side* (network/compute consumed regardless of outcome), or not?
Guessing wrong in either direction is worse than the current, at-least-consistent
behavior: zeroing the internal estimate when Parallel actually did charge would
under-count real spend and make budget checks too permissive; leaving it as-is when
Parallel genuinely refunds failed runs means this project's own budget tracking is
conservatively *over*-counting, which is the safer direction to be wrong in if a
guess were forced. Flagged here rather than silently left as a passing checklist
item — a real open question, not a fixed gap.

## 3. Duplicate webhook deliveries → single evidence write — gap closed

`services/webhook_receiver/main.py` already dedupes correctly on the delivery's own
`webhook-id` via a Firestore doc (7-day TTL) before ever republishing to Pub/Sub —
`reverify_worker` (the only writer of Evidence for this event type) genuinely never
sees a duplicate. **Gap**: `services/webhook_receiver` had no test directory at all.
Added `tests/services/webhook_receiver/test_webhook_receiver_main.py` — a real
`handle_webhook` call through FastAPI's `TestClient`, with a **real, valid HMAC
signature** (the same construction `tests/packages/parallel_client/test_webhooks.py`
already uses for signature-verification tests), only Firestore/Secret
Manager/Pub-Sub-publish mocked: the same `webhook-id` posted twice returns `200` both
times (never a rejection — Parallel shouldn't see an error and keep retrying), but
`publish_json` is only called once.

## 4. Re-running ingest → no duplicate claims — already covered

`tests/packages/ledger/test_repositories.py::
test_claim_upsert_is_idempotent_and_stable_id` already directly asserts this at the
mechanism level (`Claim.compute_id`'s deterministic hash + `ON CONFLICT DO UPDATE`).
`services/ingest/main.py` also short-circuits on the GCS object level
(`Asset.compute_id`, guarding at-least-once Eventarc redelivery) — that specific
early-return isn't independently offline-tested (its own module's test file notes
it's covered by live verification, `docs/evidence/03-ingest.md`), a small, low-risk,
pre-existing gap not closed this pass given the deeper claim-level guarantee is what
actually prevents duplicate claims either way.

## 5. Agent run restarted mid-batch → resumes from pending/triaged only — by design, prompt-driven

This is deliberately encoded in the prompts, not incidental: `claim_triage.md` has an
explicit worked example for exactly this ("Resuming a partial run:
`list_claims(status="pending")` returns nothing... `list_claims(status="triaged")`
returns 50 claims left over..."), and every specialist independently re-discovers its
own batch via `list_claims(status="triaged", category=...)` rather than trusting
session state — the same `list_claims(project_id, category, status="triaged")` call
this session's own Phase 9.2 ADK eval work verified fires reliably in production
(`docs/evidence/09-evals.md`). Since this is LLM-driven behavior, not a deterministic
function, it isn't unit-testable the way items 1-4 are; PHASE_09.md's own acceptance
bar allows "once live in dev (evidence)" for exactly this class of behavior. Not
separately re-verified live this pass beyond what Phase 9.1's golden-set run and
Phase 9.2's ADK evals already exercised (both real runs against claims genuinely
sitting in mixed pending/verified/escalated states across the same project).

## 6. Budget cap hit mid-batch → stops gracefully — gap closed

`specialist.py`'s `check_budget`/`check_and_record_cost` (called per-claim, before
any real work) already raise `BudgetExceeded`, and `verify_batch._one`'s catch sets
the claim back to `status="pending", note="budget exceeded"` rather than `"error"` —
correctly distinguishing "retry me later once budget resets" from "something broke."
**Gap**: only the low-level `CostMeter` raise was tested
(`tests/packages/parallel_client/test_cost.py::
test_cost_meter_raises_when_over_budget`), not the batch-level graceful stop. Added
`test_budget_exceeded_mid_batch_stops_that_claim_gracefully` — a real `verify_batch`
call over two claims where the second's cost check raises `BudgetExceeded`, asserting
it ends up `pending`/`"budget exceeded"` while the first claim still completes
normally. The UI-side "shows a budget notice" half of this acceptance item wasn't
found anywhere in the frontend and wasn't built this pass (a real, separate,
un-scoped gap — flagging rather than silently treating as done).

## Summary

5 new tests added (`tests/packages/parallel_client/test_client.py` ×2,
`tests/agents/ouroboros/clear/test_specialist_resilience.py` ×2,
`tests/services/webhook_receiver/test_webhook_receiver_main.py` ×1) — full suite now
239 passing (up from 234), all green, `ruff`/`mypy --strict` clean. One real,
disclosed open question (item 2's billing-on-failure policy) and one real,
un-scoped UI gap (item 6's budget notice) — both flagged rather than silently
checked off.
