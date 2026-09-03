# PHASE 07 — The Ouroboros loop

**Goal:** The system re-verifies itself without human action. Monitors fire, webhooks land, Pub/Sub fans out, re-verification Task runs are chained with `previous_interaction_id`, the ledger and dashboard update, Reality Drift moves, Slack pings, and the cadence tightens as release day approaches. **Must be live by end of Day 6** so it accumulates real events before judging.

**Calendar:** Day 6 (afternoon) → Day 7 (morning).
**Blocking inputs:** Phases 5–6 (Monitors being created); `00_REQUIREMENTS §C1–C2`.
**Reads first:** `ARCHITECTURE.md §2.5`, `PARALLEL_INTEGRATION.md §4.6, §5`, `DATA_MODEL.md §6`.

---

## 7.1 Webhook receiver (`services/webhook_receiver/`)

**Tasks**
- Cloud Run, **public** ingress, `sa-webhook`. Routes: `POST /webhooks/parallel/monitor`, `POST /webhooks/parallel/task`, `GET /healthz`.
- Verify signature (from Phase 4.5); reject with 401 on failure; log a security event.
- Idempotency: Firestore doc `webhook_dedupe/{event_id|run_id}` with TTL 7d; duplicates → 200 no-op.
- Publish to Pub/Sub `verification.events` with attributes `{kind: monitor|task, project_id, claim_id}` (from `metadata` echoed by Parallel) — respond 200 within 2s.
- Terraform: topic, dead-letter topic, push subscription to `reverify_worker` with OIDC auth.

**Acceptance**
- `make replay-webhook` posts a recorded event → message appears on the topic; a tampered signature → 401; the same event twice → one message.

## 7.2 Re-verification worker (`services/reverify_worker/`)

**Tasks**
- Pub/Sub push handler. On `monitor` events: fetch events via `monitor.events(monitor_id, event_group_id)`; write raw event to Firestore `events/`; set claim `stale`; create a Task run with the claim's spec, `processor=core-fast`, `previous_interaction_id=event_id`, `metadata.cycle = n+1`, `wait=False` (completion via Task webhook).
- On `task` completion events: fetch result; parse Basis; write Evidence(cycle n+1); run `prescore` + a lightweight `RiskAssessor` call (direct Gemini call reusing the prompt, not a full Agent Engine run — cost/latency) → update `risk`, `risk_history`, `verification_history`; set status `verified`; write Firestore claim view + `events` entry with a computed **delta** (fields that changed between cycles).
- Recompute Reality Drift for the project; write `projects/{id}.reality_drift`, `drift_7d`, `last_change_at`.
- If new risk ≥ high or risk level changed → Slack notification (7.4).
- Budget check before every Task; on `BudgetExceeded` mark `stale` + note and alert.

**Acceptance**
- Replaying a recorded monitor event followed by a recorded task completion produces: Evidence cycle 2, a history entry with `actor=reverify_worker`, a delta, updated drift. Trace spans link webhook → worker → Parallel.

## 7.3 Coil tightening (Cloud Scheduler)

**Tasks**
- Cloud Scheduler job daily 06:00 IST → `dashboard_api /internal/jobs/tighten` (OIDC). For each active monitor: compute `frequency_for(days_to_release)`; if different, `monitor.update(frequency=…)`; write history note `frequency 1d→1h (7 days to release)`.
- Same job cancels monitors for archived projects and for claims a human marked `none`.
- Demo project's release date set so the transition to `1h` happens **during judging week** (see `00_REQUIREMENTS §B3`).

**Acceptance**
- Unit test with a fake clock over 90 days shows 1w→1d→1h transitions; running the job in `dev` updates monitors in Parallel (verify via `monitor.get`).

## 7.4 Slack alerts

**Tasks**
- Option A (preferred if approved): install Parallel's Monitor Slack integration for the demo channel.
- Option B: `packages/common/slack.py` posting Block Kit messages from `reverify_worker` on risk changes with claim, delta, top citation, dashboard deep link.
- Implement B regardless (needed for risk-change alerts, which Parallel's Slack app won't compute).

**Acceptance**
- A replayed event that changes risk posts to Slack with a working deep link.

## 7.5 Memory scoping + BigQuery enrichment path

**Tasks**
- Ensure every Task/Monitor call passes `memory_scope_key=studio_id`; `ClaimTriage` uses `memory.retrieve` and shows hits as "Seen in previous production" in the claim view.
- BigQuery: register Parallel's remote functions per the Parallel BigQuery integration doc (fetch `data-integrations/bigquery.md`); create a saved query `enrich_claims.sql` that enriches `claims_for_enrichment` with `rights_holder` for a small sample. This is a **secondary** path shown in the README/demo as "analysts can enrich the ledger from SQL."

**Acceptance**
- The saved query runs against 5 rows and returns enriched columns; documented in `docs/evidence/07-bq.md`.

## 7.6 Snapshot vs event-stream tuning

**Tasks**
- Review the monitors created on the demo project: cap 40 total; ensure snapshot monitors use `lite`; stream monitors use `location` and concise intent-style queries (no boolean operators, no dates).
- Add `monitor.trigger()` support behind an internal endpoint to force an off-schedule run for the demo.

**Acceptance**
- Triggered run produces an event visible in the dashboard feed within minutes; monitor count and daily cost logged.

---

## Exit gate
- [ ] Loop proven end-to-end **with real Parallel events** (not only replays): at least one monitor event → re-verification → delta → drift change → Slack, evidenced in `docs/evidence/07-loop.md` with timestamps.
- [ ] Coil-tightening job scheduled in `dev` and `demo`.
- [ ] Squash-merge.

## Risks
- **Monitors detect nothing during the window** → plant 3–5 claims about genuinely active topics (an ongoing court case, a brand in the news, a chart-moving song) so events are likely; keep `trigger` for the demo.
- **Webhook URL changes between dev/demo** → monitors carry the URL at creation; the tighten job also reconciles webhook URLs.
- **Runaway re-verification cost** → per-project cap + per-claim cooldown (no re-verify more than once per 6h).
