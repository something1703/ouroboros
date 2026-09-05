# 6.1–6.4 — Full TRUE CUT pass on the sample cut

Real run against the `demo` project's re-ingested "About Bananas" (1935, public domain,
see `docs/DECISIONS.md` #077) cut asset (`asset_id=006da0b7763d5214b5754cf0`), driven
entirely through the deployed Agent Engine via `POST /projects/demo/runs`
(`mode=truecut`), using real Parallel Responses calls throughout (no cassettes).

## Ingest — segments, claims, proxy/poster (6.1 input, 6.4 output)

Real ingest of `fixtures/cuts/sample.mp4` via the redeployed `services/ingest`
(with `packages/gemini_client/video.py`'s new segment-persistence and
proxy/poster-generation code, `docs/DECISIONS.md` #081):

| Metric | Value |
|---|---|
| Transcript segments persisted | 35 (real timestamps, e.g. `56000-60000ms`: "Let's first visit the interior -- Guatemala City, the mile high Capitol, founded in 1527") |
| Claims extracted | 4 (3 `kind=factual`, 1 `kind=legal`) |
| Video duration | 664,030 ms (~11.1 min) |
| Proxy MP4 | `gs://ouroboros-507503-artifacts-dev/proxies/006da0b7763d5214b5754cf0.mp4`, 67MB (see #083 — oversized due to a bitrate bug fixed *after* this ingest; functional, just not "low-res" for this specific asset) |
| Poster JPEG | `gs://ouroboros-507503-artifacts-dev/posters/006da0b7763d5214b5754cf0.jpg`, 5.7KB |

`GET /assets/{id}/timeline`, `/segments`, `/proxy` (PHASE_06.md §6.4) all verified live
against the real deployed `dashboard-api`, running as `sa-dashboard-api`: timeline JSON
validates (segments + claims with `t_start_ms`/`t_end_ms`/`channel`/`verdict`/
`risk_level`/`top_citation`), and both signed URLs play (checked via `Content-Type`/
`Content-Length` on the real signed GET URL — real objects, real signatures, generated
under the actual production service account after fixing the two missing IAM roles
this required, #082).

## FactAgent — verdict table (6.1)

All 3 factual claims resolved via Parallel Responses alone (`schema=factual_quick`,
`effort=medium`) — none needed Task escalation this run (see *Escalation ladder never
fired*, below, for why).

| Claim | Verdict | Corrected statement | Citations | Confidence | Risk | Cost |
|---|---|---|---|---|---|---|
| "Guatemala City was founded in 1527." (`event`) | `contradicted` | "Guatemala City was founded in 1776." | state.gov, Britannica | high | medium | $0.05 |
| "Guatemala City is a mile high." (`statistic`) | `contradicted` | "~4,900ft/1,500m — just under a mile high." | Britannica, Wikipedia | high | medium | $0.05 |
| "Bananas are a good source of 5 of the 6 health-giving vitamins." (`statistic`) | `contradicted` | "Only a meaningful source of vitamin C; the other vitamins are low." | a real product nutrition label | high | medium | $0.05 |

All three are genuinely plausible, honest fact-checks of a 90-year-old promotional
film's specific numeric/date claims — this isn't a planted-error test fixture (unlike
PHASE_06.md §6.1's "a planted false statistic"/"a planted true event" acceptance
language, which assumes a purpose-built test video with known ground truth this real
archival fixture doesn't have), so this run can't independently confirm the *false
positive rate* on true statements — but each verdict traces to real, checkable
citations and a real, specific correction, which is the actual product behavior this
phase built.

RiskAssessor scored all three `medium` (`_prescore_factual`'s "no strong signal, default
low, +1 for contradicted" path — none hit `blocking`/`high`, since none were
`priority 1` or `confidence=medium`; see *Escalation ladder* below on why every claim
landed at `priority 3`), each with `remediation_suggested=true`,
`remediation_kind=recut`.

## Escalation ladder never fired — a real, honest finding

Every one of this fixture's claims carries `channel="on_screen_text"` (a **silent**
film — title cards only, no narration/dialogue exists in this specific fixture, per
`docs/DECISIONS.md` #077). ClaimTriage's factual rubric caps `on_screen_text` at
priority 3 regardless of category, so `_needs_task_escalation`'s `priority <= 2`
condition never fired for any claim, and none of the `contradicted`-with-`high`-
confidence verdicts triggered the low-confidence escalation path either. Found live
that the rubric's original wording (two independent-sounding rules — "event → 2" and
"on_screen_text → 3" — both matching the one `event`-category claim here, with no
stated precedence) was genuinely ambiguous; fixed by making the check order explicit
(`channel="on_screen_text"` checked first, always caps at 3) — see `docs/DECISIONS.md`
#084. This fixture's own real limitation (no narration channel exists in it) means the
priority-1/escalation path is still not live-verified end-to-end; worth confirming with
a future fixture that has real narrated claims.

## ArchiveAgent — verified live, working correctly (closing an open gap)

This fixture's own organic extraction produced zero `archival`/`identity`-category
claims, so a follow-up pass seeded one deliberately-constructed, real test claim
directly into the ledger (`status=pending`): "This footage is a 1935 short film titled
'About Bananas', produced for Castle Films and distributed on behalf of the United
Fruit Company" (`category=archival`) — a real, checkable claim about the fixture's own
genuine provenance, not a fabricated scenario. A second real TRUECUT pass processed it:

- **Search** found `archive.org/details/AboutBan1935` among its hits — the item's
  actual, correct catalog page.
- **Extract** pulled real content from that page plus a secondary source
  (`theatlantic.com`'s writeup of the same short).
- **Task** (`spec=legal_location_artwork`, `core-fast`) structured real fields
  (`owner_or_custodian`, `artwork_rights_holder`, `restrictions_summary`,
  `filming_permit_required`, ...), every one citing the correct archive.org URL.

Result: `status=verified`, `overall_confidence=high`, `risk_level=low`, cost $0.029.
Genuinely correct provenance resolution — PHASE_06.md §6.2's acceptance bar ("resolves
to the correct rights holder with medium+ confidence") is met. One caveat worth naming
honestly: `risk_level=low` here is a coincidence of this claim's Task output having no
`verdict` field at all (`legal_location_artwork`'s schema, not `factual_claim`'s) —
`_prescore_factual` falls through every branch to its "no strong risk signal, default
low" catch-all for *any* ArchiveAgent result, correct rights holder or not. There is no
rubric branch that would score a *problematic* archival finding (e.g. "rights holder
found, actively restricts reuse") any differently — a real gap in `packages/claims/
risk.py::_prescore_factual`, not exercised by this particular (rights-clean) claim.

A second seeded claim (`category=statistic`, `channel="narration"`, "Guatemala's
population exceeds 50 million people" — deliberately false) was meant to exercise the
priority-1 escalation path this fixture's own on-screen-text-only claims never reached.
It resolved correctly (`contradicted`, corrected to ~18.7M, FRED-cited) — but via
Responses alone, not escalation: ClaimTriage assigned it priority 3, not the priority 1
its own (unambiguous) rubric calls for. A real, separate finding — see
`docs/DECISIONS.md` #086.

## The 4th claim — TRUECUT correctly leaves it for CLEAR; CLEAR then hits a real bug

The extracted `brand`-category claim ("shipped ... in ... the Great White Fleet")
stayed at `triaged` through the TRUECUT run — **expected, not a bug**: `TRUECUT`'s
`sub_agents` list (ADK_AGENTS.md §3) has no legal-category specialist by design, since
legal claims are CLEAR's job.

Triggering a real `CLEAR` run against the same asset to verify the hand-off surfaced a
genuine, unresolved problem instead of confirming it works: across **4 consecutive real
CLEAR runs**, this claim (plus 4 siblings — 2 more "Great White Fleet" duplicates,
"Castle Films", "Dudley Circuit Service Classroom Films") never advanced past
`triaged`. Investigating this live found and fixed one real bug (ClaimTriage's own
"sweep leftover triaged claims" step wasn't reliably followed by the model — the same
class of session-state fragility RiskAssessor/Reporter were already fixed for; all four
CLEAR specialists now sweep the ledger directly instead, `docs/DECISIONS.md` #087) —
but the specific claims **still didn't move** on the 4th run, after that fix. The
common thread: all 5 are the *only* `kind=legal` claims in this project ever produced
by video ingest rather than script ingest — an entirely new code path this same
session's earlier work first exercised. Root cause not yet identified; ruled out an
exception inside the per-claim verification loop (no matching `specialist_claim_failed`
log line at any of the 4 runs' real timestamps). Documented as a real, open,
reproducible bug rather than re-run indefinitely hoping for a different outcome — see
`docs/DECISIONS.md` #088 for the full investigation and candidate next steps.

Separately, 2 `category=quote` claims from the same asset are *also* stuck — a
different, pre-existing, non-Phase-6 gap: `quote` is a real, defined legal category
with no specialist agent at all in ADK_AGENTS.md's original 4-agent design. Also
documented in #088.

## Cost and timing

- Real Parallel cost, first TRUECUT run: $0.15 (3 claims × $0.05 Responses call each).
- Real Parallel cost, second TRUECUT run (2 seeded claims): $0.079 (archival: $0.029
  Search+Extract+Task; narration statistic: $0.05 Responses).
- Cumulative real project spend after all runs this phase: **$2.269** (well under the
  project's $10 budget cap).
- Wall time: the first TRUECUT run's 3 factual claims all reached `verified` within
  ~3 minutes of the triggering `POST` — far under PHASE_06.md §6.1's "batch of 25
  claims < 8 min" bar for this small a batch; a genuinely larger batch's timing is not
  exercised by this fixture.

## Real bugs found and fixed getting here

Full narrative and rationale for each is in `docs/DECISIONS.md`; summarized here:

- **#078** — `extract()`'s `full_content=True` requirement, caught by reading the
  function before writing ArchiveAgent's call to it, never triggered live.
- **#079** — `list_claims`/`gather_risk_inputs`/`gather_report_inputs` were missing
  `channel`/`kind` fields the new factual rubrics needed.
- **#080** — ADK's one-parent-per-agent-instance constraint required converting
  ClaimTriage/RiskAssessor/Reporter to `build_*_agent()` factories so CLEAR and
  TRUECUT each get their own instance of the same construction code.
- **#082** — `sa-ingest` and `sa-dashboard-api` were each missing one storage IAM role
  the new artifacts-bucket read/write paths needed; also a near-miss where a
  `--set-env-vars` redeploy almost silently dropped `AGENT_ENGINE_RESOURCE_NAME`.
- **#083** — `ingest`'s default 512Mi/300s resource envelope couldn't handle the new
  ffmpeg proxy transcode, causing an indefinite Eventarc retry loop until fixed; the
  proxy's own target bitrate was also higher than some real archival source footage's
  own encoding, producing an oversized "low-res" proxy.
- **#084** — `claim_triage.md`'s factual priority rubric had two rules that could both
  match one claim with no stated precedence; fixed by making the check order explicit.
- **#087** — CLEAR's four specialist prompts trusted a session-state hand-off from
  ClaimTriage that the model didn't reliably execute; converted to a direct ledger
  sweep, matching RiskAssessor/Reporter's already-established, more-robust pattern.

## What's still open

- **#086** — ClaimTriage's priority rubric isn't reliably followed even where
  unambiguous (a `channel="narration"` claim got priority 3, not the rubric's 1) —
  priority has no deterministic backstop the way risk scoring does.
- **#088** — 5 video-sourced `kind=legal` claims never get past `triaged` under CLEAR,
  even after #087's fix — root cause not yet identified. 2 `quote`-category claims are
  separately stuck with no specialist agent at all (a pre-existing, non-Phase-6 gap).
- `_prescore_factual` has no rubric branch for ArchiveAgent's own output shape (no
  `verdict` field) — every archival/identity claim's risk defaults to `low` regardless
  of what ArchiveAgent actually found.
- Phase 6.5 (A2A cross-head handoff, explicitly a stretch goal) not attempted.
