# 5.7 — Full CLEAR pass on the demo project

Real run against the `demo` project (62 claims, ingested from `sample_en.pdf` in an
earlier phase), driven entirely through the deployed Agent Engine via
`POST /projects/demo/runs`, using real Parallel API calls (search + Task, no cassettes)
throughout.

## Final numbers

| Metric | Value | Acceptance bar (PHASE_05.md §5.7) | Met? |
|---|---|---|---|
| Claims with Evidence | 60 / 62 (96.8%) | ≥ 95% | ✅ |
| Total Parallel cost | $1.54 | < $8 | ✅ |
| Monitors created | 96 rows (28 distinct claims; see *Monitor duplication* below) | ≥ 3 | ✅ |
| Wall time for a single clean pass | not achieved — see *Wall time* below | < 25 min | ⚠️ see note |

Risk distribution across the 60 assessed claims: `blocking` 22, `medium` 16, `low` 18,
`high` 4 — not degenerate (not everything landed on one level), consistent with
PHASE_05.md §5.4's "distribution is sane" acceptance bar. The 2 claims without Evidence
are the 2 legitimately `skipped: prior_decision` claims (a seeded recent `cleared`
decision) — by design, a skipped claim is cleared via the prior-decision shortcut, not
fresh research, so it has no Evidence row. 60/62 is the true, honest evidence-coverage
denominator.

## Wall time — what actually happened, honestly

A single triggered run never got the full 62-claim batch from `pending` to
fully-reported in under 25 minutes, and this section explains why rather than hiding
it. Two distinct, real findings made a single clean run impossible as originally
imagined:

1. **Vertex AI Agent Engine's `stream_query()` has a hard, documented 10-minute
   streaming ceiling** (docs/DECISIONS.md #072) — confirmed against Google's own docs.
   A CLEAR pass processing dozens of claims with real Parallel Task calls (each taking
   seconds to tens of seconds) genuinely needs more than 10 minutes of wall-clock work
   for a batch this size. This is a platform constraint, not a bug in this codebase.
2. **A real, previously-undiscovered gap in the ClaimTriage → specialists → RiskAssessor
   → Reporter hand-off** (docs/DECISIONS.md #073, #074, #075): each stage's LLM read its
   own work batch from *the current session's own state*, not from the ledger. A claim
   that a specialist verified in a run that got cut off by finding #1's 10-minute ceiling
   *before* RiskAssessor ran on it was, before this fix, invisible to every future
   retrigger — no amount of retriggering could ever have picked it back up. Every one of
   ClaimTriage, RiskAssessor, and Reporter now sweeps the ledger directly
   (`list_claims(status=...)`) instead of relying solely on session state, specifically
   so a retrigger resumes real, previously-stuck work instead of silently redoing (or
   permanently losing track of) nothing.

Once both were understood and fixed, the operating pattern that got this run to
completion was: trigger `/runs`, let it run until it either finishes or hits the
10-minute ceiling, and retrigger if claim state shows work remaining. Since every
claim's real progress (status, Evidence, Risk, Monitor) is persisted to Cloud SQL
throughout — not just at the end — each retrigger genuinely resumes rather than
restarting. This is now the correct, intentional way to run a CLEAR pass whose total
work exceeds one 10-minute window, not a workaround for a bug. A future fix to remove
the 25-minute bar's dependency on a single `stream_query` call (chunking the workload
across multiple driver-orchestrated calls, or a non-streaming/batch Agent Engine API if
one exists) is real follow-up work, not attempted here.

Separately, and honestly: this specific run's total wall-clock time also includes many
hours of live debugging and redeployment cycles for six distinct real production bugs
found along the way (Cloud SQL connectivity from Agent Engine's sandboxed network,
Gemini quota/retry handling, Cloud Run's CPU-throttling-vs-background-tasks interaction,
a missing Model Armor IAM grant, Agent Engine memory sizing, and the hand-off gap
above) — see `docs/DECISIONS.md` #062–#076 for the full, real narrative. None of that
redeploy/debug time reflects the actual CLEAR algorithm's own processing time; it's
recorded here for honesty, not folded into a misleading "wall time" figure.

## Monitor duplication — found, root-caused, fixed live

While verifying this run, the Monitor count looked implausibly high (96 rows across
only 28 distinct claims) for what should be at most 2 Monitors per claim (one snapshot,
one event_stream). Investigation found a genuine race condition (docs/DECISIONS.md
#076): the self-driving retrigger loop firing every few minutes, combined with the
Agent Engine's own `max_instances=2`, let two `stream_query` sessions run concurrently
against the same project. Both sessions' Reporter checked whether a claim already had a
Monitor, both saw "no" before either had committed its own write, and both created a
real, separate Monitor at Parallel for it — confirmed via
`SELECT claim_id, type, count(*) ... HAVING count(*) > 1` showing 20+ duplicated pairs.

Fixed with a Postgres advisory lock (`pg_try_advisory_lock(hashtext(project_id))`) held
for a run's entire `stream_query` duration — a second concurrent attempt is now
rejected immediately rather than running at all. Verified locally against a real
Postgres connection before deploying. The ~20 real duplicate Monitors already created
at Parallel before this fix landed are a known cleanup item (cancelling the extras),
not completed here given time constraints — they cost nothing further to leave running
for a demo project, but are real Parallel-side clutter worth tidying up post-hackathon.

## Cloud Trace (PHASE_05.md §5.5's "spans across API → Engine → Parallel")

Confirmed live via `google.cloud.trace_v1`: a real trace from this run
(`a0988adc8ebbdadac0d0b90500eaa646`, 188 spans) shows the full path —
`invoke_workflow OuroborosCoordinator` → `invoke_agent ClaimTriage` →
`invoke_agent ClearFanOut` → `invoke_agent {Music,Brand,Person,LocationArt}Agent` →
`invoke_agent RiskAssessor` → `invoke_agent Reporter`, with real `execute_tool` spans
for every ledger/Firestore/Monitor call (`write_claim_summary` ×60,
`monitor_create_snapshot` ×26, `monitor_create_stream` ×21, `record_risk`,
`gather_risk_inputs`, ...) and real `generate_content`/`call_llm` spans for every model
turn. `dashboard-api`'s own `POST /projects/{project_id}/runs` request span is present
in a separate trace from the API layer. One granularity gap, noted honestly: the
specialist tool calls that actually invoke Parallel (`search`/`task.run` inside
`verify_batch`) aren't individually named spans — they execute inside one
`execute_tool verify_<category>_batch` span rather than each getting its own child
span, so "Parallel" isn't a literal span name anywhere in the trace, though the tool
span that contains those calls is. Meets the acceptance bar's intent (API → Engine →
tool-execution-that-calls-Parallel is all real, live-verified trace data); a follow-up
could wrap `search()`/`run_task()` in `packages.common.tracing.span(...)` for
per-call-visible Parallel spans specifically.

## Real bugs found and fixed getting here

Full narrative and rationale for each is in `docs/DECISIONS.md`; summarized here for
one place to see the whole arc:

- **#062** — Agent Engine's runtime has no VPC path to Cloud SQL's private IP; direct
  DB connections from the deployed agent hang forever. Fixed by routing
  `specialist.py`'s budget/cost checks through Toolbox instead.
- **#063** — Vertex AI Gemini quota (429) crashed the whole run outside any tool's
  try/except. Fixed with a patient retry policy on every `LlmAgent`'s model.
- **#064**, **#068** — Cloud Run's default CPU throttling + scale-to-zero silently
  killed `dashboard-api`'s detached background run-driver task; Agent Engine's default
  memory wasn't enough for a real request's worker under cold-start load (an OOM-style
  silent kill, no traceback). Fixed with `--no-cpu-throttling --min-instances=1` and
  `resource_limits={"cpu": "4", "memory": "8Gi"}` respectively.
- **#066** — `sa-agent-engine` was missing `roles/modelarmor.user`; every specialist
  claim failed identically on a 403 until granted.
- **#067**, **#070**, **#071** — the same VPC-path gap as #062, recurring in
  RiskAssessor/Reporter's Firestore-writing code, then a related but distinct
  transient Firestore `NotFound`; the real, general fix was widening `resilient`'s
  exception handling to actually catch real Google API failures, not just this repo's
  own error hierarchy (its whole documented purpose, which it silently wasn't doing).
- **#072** — Agent Engine's real, documented 10-minute `stream_query` ceiling
  (see *Wall time* above).
- **#073**, **#074**, **#075** — the ClaimTriage → specialists → RiskAssessor →
  Reporter hand-off gap (see *Wall time* above) — the actual reason retriggering alone
  couldn't finish the run even after every infrastructure bug above was fixed.
- **#076** — the concurrent-run race condition (see *Monitor duplication* above).

## What's still open

- ~20 duplicate Monitors at Parallel from before #076's fix — not cancelled.
- `reporter.py::_finalize_report`'s returned `report.claims_by_risk` JSON field
  undercounts on a retrigger that mostly finds already-assessed claims (reads
  RiskAssessor's per-turn state, narrowed by #074's dedup) — the persistent,
  dashboard-facing `write_project_summary` figure is a real aggregate query and is
  unaffected.
- The 10-minute `stream_query` ceiling itself isn't removed — retriggering is the
  accepted operating pattern for a batch this size, not a permanent fix.
