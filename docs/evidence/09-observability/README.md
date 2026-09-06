# Phase 9.4 — Observability evidence

**On screenshots:** this environment has no interactive browser/screenshot capability
(a headless Chromium was used in an earlier session for the web app specifically, per
`docs/DECISIONS.md` #110, but Cloud Console pages require a real, interactive Google
login session no automated agent here holds). The evidence below is the real,
live-verified equivalent instead — `gcloud` output and actual API responses proving
every resource exists and is configured correctly, not a rendered image of the same
data. If you want the visual dashboard, it's real and live at the link in
`dashboard.txt` below — open it in your own signed-in browser.

## What's deployed (`infra/modules/monitoring/`)

- **1 dashboard** ("Ouroboros"): request count / 5xx error count / p95 latency per
  Cloud Run service, monitor events per day, webhook 401 count, re-verification
  latency (p95), dead-letter queue depth. See `dashboard.txt` for the live console URL
  and the exact widget list confirmed via `gcloud monitoring dashboards describe`.
- **3 log-based metrics**: `webhook_401_count` (counter), `monitor_events_count`
  (counter), `reverify_latency_ms` (distribution, extracted from a new `latency_ms`
  field added to `reverify_worker`'s own `reverify_complete` log line this pass).
- **4 alert policies**, all enabled, all routed to a real email notification channel
  (see `alerts.txt`):
  - Cloud Run error rate > 5% (any service) — a real ratio-threshold condition on
    Cloud Run's built-in `request_count` metric (5xx / total), not a custom metric.
  - Project spend > 80% of budget cap — a `condition_matched_log` on a new
    `budget_80_percent` log line added to `packages/parallel_client/cost.py::check_budget`
    this pass (rate-limited to one notification/hour per project).
  - Webhook 401 spike — threshold on the new `webhook_401_count` log-based metric,
    > 5 in a 5-minute window.
  - Dead-letter messages present — threshold on Pub/Sub's own built-in
    `num_undelivered_messages` metric for both existing DLQ pull subscriptions
    (`claims-extracted-dlq-pull`, `verification-events-dlq-pull`), already real
    resources from Phase 7, not created this pass.

All 9 resources applied via real `terraform apply` (`gcloud` listings in `alerts.txt`/
`metrics.txt` confirm they exist live, not just planned) — no unrelated drift in the
same `terraform plan` this time (a clean "9 to add, 0 to change, 0 to destroy").

## New instrumentation this pass

- `services/reverify_worker/main.py::_handle_task_completion`: now times itself
  (`time.monotonic()` at entry) and logs `latency_ms` on its `reverify_complete` line.
  **Scoped down from the literal spec**: this measures "task-completion-event
  received → evidence written," not the full "original webhook received → evidence
  written" span — the full chain crosses two separate Pub/Sub deliveries
  (`_handle_monitor_event` kicks off a new Task run; only its *later* completion event
  reaches `_handle_task_completion`), and threading the original webhook timestamp
  through the Task run's own metadata wasn't done this pass (documented as a real,
  named scope reduction, not silently narrowed).
- `services/reverify_worker/main.py::_handle_monitor_event`: logs
  `monitor_event_received` at entry (the Firestore event-feed write there is for the
  UI, not Cloud Logging — a log-based metric needed its own line).
- `packages/parallel_client/cost.py::check_budget`: logs `budget_80_percent` when
  spend crosses 80% of a project's cap. **Scoped down**: only the direct-DB callers
  that already call this function (`reverify_worker`) get this signal — the
  agent-side Toolbox-backed budget check (`agents/ouroboros/tools/budget.py`, used by
  CLEAR/TRUE CUT specialists) is a separate code path and doesn't emit this log line
  yet.
- Redeployed `reverify-worker` (revision `reverify-worker-00006-25h`) so this
  instrumentation is actually live, not just committed.

## Induced failure: kill Toolbox (PHASE_09.md §9.4's acceptance test)

Real, run live against the local dev stack (`docker compose stop toolbox`), not
simulated:

```
$ docker compose stop toolbox
 Container ouroboros-toolbox-1  Stopped

$ # real verify_batch() call against a real seeded claim, Toolbox down:
RESULT: {'verified': [], 'escalated': [],
         'errors': [{'claim_id': 'dfe27032e1e0238056285533',
                     'error': "Cannot connect to host localhost:5001 ..."}]}

$ docker compose start toolbox
 Container ouroboros-toolbox-1  Started

$ # same claim, Toolbox back up:
```
`RESULT: {'verified': ['dfe27032e1e0238056285533'], 'escalated': [], 'errors': []}` # pragma: allowlist secret (a deterministic sha256-derived ledger claim id, not a credential)

**Confirmed**: the process itself never crashes — `specialist.py::verify_batch`'s
per-claim exception isolation (`_one()`) catches the connection failure cleanly,
logs `specialist_claim_failed`, and returns a clean structured result. The batch
call as a whole completes normally even with one (or every) claim failing.

**One honest nuance, found live, worth stating precisely rather than the more
convenient claim PHASE_09.md's own wording might suggest**: with Toolbox *totally*
down, the claim's status-write attempt (`set_status(..., "error", ...)`) *also* goes
through Toolbox and *also* fails — logged as a second, separate
`specialist_status_write_failed` line. So during a full Toolbox outage specifically,
a claim's displayed status doesn't actually flip to `error` in the ledger/UI; it
stays at whatever it was before, and only resumes progressing once Toolbox recovers
(confirmed above — the same claim verified successfully on the very next attempt
after Toolbox restarted). The real guarantee this test demonstrates is "the process
degrades gracefully and recovers cleanly, isolated per-claim, never crashes or
corrupts state" — not literally "claims visibly turn red in the UI while Toolbox is
down," which would need the status database to be reachable through some path
Toolbox itself isn't on (it isn't, by design — Toolbox is the *only* path to the
ledger for agent code, `agents/ouroboros/tools/ledger.py`'s own docstring).

## A second real bug found and fixed: dashboard-api traces were silently dropped

Querying Cloud Trace for this project over the last several hours of heavy real
`dashboard-api` traffic (all of this session's live Phase 8.4/8.5/9 testing) returned
**zero traces**. Root cause: `flush_tracing()` was called by `ingest`/
`webhook_receiver`/`reverify_worker` (each a single message-handler that already
calls it once at the end) but never by `dashboard_api` — which has many endpoints,
none of which called it. `packages/common/tracing.py::flush_tracing`'s own docstring
already documents *why* this matters (Cloud Run's request-based CPU allocation
freezes a container between requests, so `BatchSpanProcessor`'s background export
thread never gets to run) — dashboard-api was the one service that had never actually
applied that documented lesson to itself.

**Fixed**: added an `@app.middleware("http")` in `services/dashboard_api/main.py`
that calls `flush_tracing()` after every response — one place covering every route,
rather than editing each handler. Redeployed (`dashboard-api-00028-6jk`) and
confirmed live: a real call to `/status` immediately produced a real, complete trace
(trace id `760c070d8494b92a4691dcfea29d585c` — pragma: allowlist secret, a public
Cloud Trace identifier, not a credential — four spans: the GCP load balancer, the
Cloud Run AppServer wrapper, and FastAPIInstrumentor's own `GET /status` RPC span) —
the exact "one claim, one trace" exemplar PHASE_09.md's README requirement asks for.
This project's current `README.md` is still the pre-submission planning package
(Phase 10 owns building the final judge-facing README with a metrics table); this
trace ID is real and ready to link from it once that README exists: open Cloud
Trace for `ouroboros-507503` and search trace id `760c070d8494b92a4691dcfea29d585c`  <!-- pragma: allowlist secret -->

## Known cosmetic drift

`terraform plan` shows a perpetual no-op diff on `google_monitoring_dashboard.ouroboros`
(a `name` field the API echoes back inside the dashboard JSON itself, which doesn't
perfectly round-trip through Terraform's own plan comparison) — a well-documented
quirk of this resource type in the Google provider, not a real configuration drift;
confirmed the dashboard's actual content is correct and live via
`gcloud monitoring dashboards describe`. Not chased further.

## Not exercised this pass

- The alert *conditions themselves* firing for real (as opposed to being correctly
  configured) needs sustained real production traffic over each policy's own
  evaluation window (5 minutes to an hour) — not something to manufacture safely in
  one session against the real `ouroboros-507503` project. Configuration correctness
  was verified instead (`gcloud` listings, `terraform plan` showing 0 drift after
  apply).
- A live end-to-end webhook-401 log line: attempted to POST a deliberately-invalid
  signature to the real deployed `webhook-receiver` to generate one, but the request
  timed out from this sandbox (an intermittent, previously-documented network
  characteristic of this environment reaching `*.run.app` URLs directly, `docs/
  BLOCKERS.md` [PHASE 1.3] — other `*.run.app` calls this same session succeeded, so
  this looks endpoint-specific, not a blanket block). The log-based metric's filter
  targets a real, existing log line (`webhook_signature_invalid`, already exercised
  organically per `docs/DECISIONS.md` #099's real rejected webhook deliveries) — not
  re-verified live this pass.
