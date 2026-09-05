# 7.1–7.6 — The Ouroboros loop, live evidence

All calls below are against the real deployed services in `ouroboros-507503`
(`webhook-receiver`, `reverify-worker`, `dashboard-api`), the real Parallel API, and the
real Cloud SQL/Firestore/Pub/Sub backing this project — no cassettes, no mocks.

## 7.1 — Webhook receiver

Real fixture: `fixtures/webhooks/monitor_event_1.json`, built around a real, active
Monitor (`monitor_4de84c9330364693a46348c619ecea62`, type `snapshot`) and its real claim
(`effbe6edcac98c252a3dec71`, project `demo`) from Phase 5's CLEAR pass — the only field
in it that could not be real is `data.event.event_group_id`, which Parallel only ever
issues inside a genuine `monitor.event.detected` webhook (see `docs/DECISIONS.md` #096).

| Test | Command | Result |
|---|---|---|
| Tampered signature | `scripts/replay_webhook.py --fixture monitor_event_1 --tamper` | `status=401` |
| Valid signed replay | `scripts/replay_webhook.py --fixture monitor_event_1` | `status=200` |
| Duplicate `webhook-id` | same `--webhook-id=dedup-test-123` sent twice | both `status=200`; **second call confirmed genuinely deduped**, not just coincidentally 200 (see below) |

Dedup confirmed via Cloud Logging, not just the HTTP status (which is 200 either way by
design): the second call produced a real `webhook_duplicate` structured log line —

```
2026-09-05T08:14:03.752055Z  webhook_duplicate  event_kind=monitor;webhook_id=dedup-test-123
```

— distinct from the fresh-event path, which instead published to Pub/Sub and returned
200 for a different reason (a new message, not a detected duplicate).

## 7.2 — Re-verification worker: wiring proven end-to-end for real

Both the plain replay and the dedup-test's fresh publish reached `reverify-worker` via
its real, OIDC-authenticated Pub/Sub push subscription (`verification-events-reverify`).
Cloud Logging on `reverify-worker` shows the full real call chain for each:

1. Pub/Sub push received, `monitor.event.detected` parsed, claim `effbe6edcac98c252a3dec71`
   looked up, cooldown/budget checks passed.
2. A **real** call to Parallel's `monitor.events(monitor_id, event_group_id=...)` API was
   made — confirmed via `parallel_call_rejected`/`reverify_event_failed` log lines
   carrying real Parallel `ref_id`s (e.g. `441dc2b8e97431869bb23ae8d2d6c67b`), not a stub.
3. That call correctly 422s: `"Could not find event group with id
   replay-fixture-event-group-1"` — expected, since that id is a fixture placeholder,
   not a real Parallel-issued one (`docs/DECISIONS.md` #096).
4. Pub/Sub retried the push per the configured `retryPolicy` (`ackDeadlineSeconds=20`)
   until `deadLetterPolicy.maxDeliveryAttempts=5` was hit, at which point **both**
   messages correctly landed in the dead-letter topic `verification.events.dlq` —
   confirmed by pulling them directly from `verification-events-dlq-pull`:

```
CloudPubSubDeadLetterSourceDeliveryCount: '5'
CloudPubSubDeadLetterSourceSubscription: verification-events-reverify
claim_id: effbe6edcac98c252a3dec71
kind: monitor
project_id: demo
```

**What this proves:** signature verify → dedupe → Pub/Sub publish → OIDC push delivery →
event parsing → claim/cooldown/budget lookup → a real Parallel API call → retry →
dead-letter, all genuinely wired and working. **What replay alone cannot prove:** the
Evidence/risk/drift/Slack tail past `monitor.events()` — that requires a real
`event_group_id`, which only a genuinely Parallel-detected event carries.

## 7.6 — `monitor.trigger()`: a real off-schedule check, attempted

Added `POST /internal/jobs/trigger-monitor/{monitor_id}` (`services/dashboard_api/main.py`)
wrapping Parallel's real `monitor.trigger()` API, specifically to get a genuinely
Parallel-originated event rather than wait an unknown amount of time for the existing
Monitor's own schedule. Called live against the same real, active
`monitor_4de84c9330364693a46348c619ecea62`:

```
TRIGGER 200 {"triggered":true,"monitor_id":"monitor_4de84c9330364693a46348c619ecea62","claim_id":"effbe6edcac98c252a3dec71"}
```

A 20-minute watch on `reverify-worker`'s logs afterward (polling for
`reverify_task_started`/`reverify_complete`) found nothing — an **honest, expected null
result**, not a bug: per Parallel's own `monitor.trigger()` docs, "an event is only
emitted if the execution detects a material change," and this Monitor's underlying claim
content (a 90-year-old public-domain film's provenance) is stable, so a re-check
correctly found nothing new to report.

## 7.3 — Coil tightening: run live against the real demo project

`POST /internal/jobs/tighten` called for real (as `sa-scheduler`, matching the real
Cloud Scheduler job `tighten-monitors`'s own identity):

```
TIGHTEN 200 {"total":51,"updated":0,"unchanged":51,"errors":[]}
```

`updated=0` is the **correct** result, not a no-op bug: the demo project's
`release_date` is `2026-10-10`; today is `2026-09-05`, i.e. 35 days out —
`frequency_for(35)` returns `"1d"` (the `>7 days` bucket), which is exactly what all 51
active monitors were already set to. The transition to `"1h"` only fires once the
project is ≤7 days from release (per `00_REQUIREMENTS §B3`'s judging-week design). The
real Cloud Scheduler job (`tighten-monitors`, daily 06:00 IST, Terraform-applied) will
correctly flip these to `1h` as that date approaches.

## 7.6 — Monitor count/type audit, live against the real ledger

| Metric | Value |
|---|---|
| Total monitors ever created (demo project) | 96 |
| Active | 51 |
| Cancelled | 45 |
| Distinct claims with an active monitor | 32 |
| Claims with >2 active monitors (anomaly check) | **0** |
| Snapshot / event_stream split (active) | roughly even, both represented |

**51 active exceeds PHASE_07.md §7.6's "cap 40 total" guideline.** Investigated rather
than assumed a bug: grouping active monitors by `claim_id` shows 32 distinct claims,
each with at most 2 active monitors (1 snapshot + 1 event_stream, exactly the pattern
`reporter.md`'s own rules describe for a claim that's both currently high-risk *and*
plausibly time-sensitive) — zero claims have more than 2, so this is **not** a
duplicate-creation bug (Reporter's `has_monitor` guard, `docs/DECISIONS.md` #075,
already prevents that on any retrigger). The overage instead reflects this specific
`dev` project's cumulative history across many real, iterative CLEAR/TRUE CUT passes
this session (Phase 5 and 6 each ran the pipeline multiple times investigating real
bugs — #087/#088 alone describes 4 consecutive real CLEAR runs) — each pass's newly
risk-assessed claims got their own real Monitors, and nothing in this project ever
prunes monitors for claims that a *later* pass superseded. The 45 cancelled monitors
have no matching `verification_history` note (grepped for `%monitor%cancel%`), meaning
they weren't cancelled through any documented ledger-tracked path — consistent with
being artifacts of ad-hoc debugging (e.g. this session's own scratch investigations)
rather than the coil-tightening job's own archived-project/human-`none` cancellation
path (PHASE_07.md §7.3), which has never actually run against a claim marked `none` in
this project.

Query style: every sampled `event_stream` query is a concise, natural-language "developments
regarding: `<claim_text>`" string with no boolean operators and no dates — matches
§7.6's requirement. All active monitors carry `frequency=1d`, consistent with the
tighten-job finding above.

**Real follow-up, not fixed here:** before a final demo, prune monitors belonging to
claims from earlier, now-superseded debugging (the seeded test claims from #086, the
video-legal-claim investigation from #087/#088) so the active count reflects only the
claims meant to be shown, not this session's full development history. See
`docs/DECISIONS.md` #098.

## Exit-gate status

- [x] Webhook receiver: signature verify, dedupe, Pub/Sub publish — proven live.
- [x] Re-verification worker wiring — proven live up through a real Parallel API call.
- [x] Coil-tightening job — scheduled (Cloud Scheduler `tighten-monitors`, Terraform-applied)
  **and** run live against the real demo project, producing the correct (unchanged)
  result for its current days-to-release.
- [x] Monitor count/type audit — done; one real, documented finding (51 active vs. a
  40 cap, root-caused as cumulative dev-session churn, not a duplication bug).
- [ ] **A genuinely Parallel-originated event completing the full Evidence → risk →
  drift → Slack tail** — not yet captured. `monitor.trigger()` ran for real but the
  underlying claim had no material change to report (an honest, expected null result,
  not a failure). This is the one remaining item blocking a clean exit-gate close;
  candidates: create a Monitor on a claim about a genuinely active topic (PHASE_07.md
  §7's own stated risk mitigation), or continue watching this project's existing
  Monitors' normal schedule for an organic fire.
- [ ] Slack alert on a real risk change — blocked on the above; `packages/common/slack.py`
  is implemented and wired into `reverify_worker`'s completion path but has not yet
  fired against a real event.

*(This document will be updated once a genuine Parallel-originated event completes the
loop.)*
