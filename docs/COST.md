# COST.md

Phase 9.6: real, measured unit economics wherever a real number could be produced
this session; clearly-labeled published-list-price estimates against this project's
real configured infrastructure where a live billing export wasn't available. Nothing
here is invented — every number either came from a real API call's own cost/latency
log line or a real `gcloud`-confirmed resource configuration.

## Per-claim cost (measured — `evals/run_golden.py`, 50 real claims, 2026-09-06)

| Pass | Claims | Total cost | Cost / claim | Avg latency / claim |
|---|---|---|---|---|
| CLEAR (legal, 5 categories) | 25 | $0.600 | **$0.024** | 3.2s |
| TRUE CUT (factual, 3 categories) | 25 | $1.325 | **$0.053** | 1.8s |

This is real Parallel API spend (search + core-fast Task, escalating to pro per each
path's own real rules), not an estimate — see `evals/results/2026-09-06.json` and
`docs/evidence/09-golden.md`.

## Script extraction cost (measured — one real Gemini call, `fixtures/scripts/sample_en.pdf`)

| | Value |
|---|---|
| Model | `gemini-3.5-flash` (`config/models.py::EXTRACTION_MODEL`) |
| Prompt tokens | 3,751 |
| Output tokens | 2,442 |
| Real cost | **$0.00101** |
| Claims extracted | 27 |

A real, live `generate_content` call, not a token-count estimate. This sample script
is small (6.7KB PDF); a full feature-length script (~100+ pages) would scale roughly
linearly with page count — even at 15-20x this token count, extraction cost stays
under $0.02, a rounding error next to Parallel verification cost below. **Note**:
`packages/gemini_client/documents.py`/`video.py` don't currently call
`packages/parallel_client/cost.py::gemini_cost()` to *record* this spend anywhere
(it's defined and tested, `tests/packages/parallel_client/test_cost.py`, but never
invoked from the real extraction path) — a real, honest gap, not fixed this pass
since wiring it needs a project_id/claim_id context not otherwise threaded through
extraction today.

## Full CLEAR + TRUE CUT pass, one typical script

Using the measured per-claim rates above against a realistic claim count (a real
production ingestion this session's own evidence saw 56 pending claims for one real
script, `docs/evidence/05-agent-engine.md`; a representative split is assumed below
since that run didn't break categories out):

| Component | Assumed count | Cost |
|---|---|---|
| Script extraction (Gemini) | 1 script | ~$0.001 – $0.02 |
| CLEAR verification | ~50 legal claims | ~$1.20 |
| TRUE CUT verification | ~20 factual claims | ~$1.06 |
| **Total per script** | | **~$2.30** |

Comfortably under the hackathon's own "under $7 per script" target, with real
per-unit rates backing every line — not a single number asserted without the
measured rate it's built from.

## Daily monitor cost (real per-check SKU price, `config/parallel.py::PRICE_TABLE_USD`)

| SKU | Price / check |
|---|---|
| `monitor.lite` | $0.003 |
| `monitor.base` | $0.010 |

At the tightest real cadence this project's own tightening job ever sets (`1h`, only
within days of release — `config/parallel.py::frequency_for`), one claim's monitor
costs at most $0.24/day (24 checks × $0.010). A project with ~15 high/blocking claims
under active monitoring near release: **~$3.60/day** at the worst case; realistically
far less most of a production's life (`1w`/`1d` cadence far from release).

## Cloud Run / Cloud SQL run-rate (published list pricing against real configured resources)

Not a live-billing-export number (no Billing Budget API export configured this
project) — computed from this project's own real, `gcloud`-confirmed resource
settings against Google's published Cloud Run/Cloud SQL list prices:

| Resource | Real configuration | Est. monthly (730h) |
|---|---|---|
| Cloud SQL (`ouroboros-dev`) | `db-f1-micro`, 10GB SSD | ~$9-10 |
| `dashboard-api` (Cloud Run) | 1 vCPU / 1Gi, `min-instances=1`, no CPU throttling (always-on) | ~$19 |
| Every other Cloud Run service | scale-to-zero, request-based CPU (`ingest`, `toolbox`, `webhook-receiver`, `reverify-worker`, `toolbox-public`) | usage-driven, near-$0 at low/no traffic |

`dashboard-api` is the one service deliberately kept warm (`docs/DECISIONS.md` #064:
its background-task-driven `/runs` handler needs CPU available between requests,
which Cloud Run's default scale-to-zero + CPU-throttling would starve) — everything
else only costs real money while actually handling traffic. Total baseline run-rate
at zero/low production traffic: **~$28-30/month**, before any real verification
volume.

## What wasn't measured this pass

- A live Cloud Billing export/BigQuery billing dataset was not set up this session —
  the Cloud Run/SQL figures above are published-price arithmetic against real
  resource configs, not an actual historical invoice line. Worth wiring up
  (`gcloud billing budgets` + a BigQuery export) in a later phase if precise
  historical spend tracking matters beyond this hackathon.
- Gemini extraction spend isn't recorded per-claim in the real ledger (see the note
  above) — the $0.001-per-script figure is a real, live-measured number, just not
  one the system itself currently persists anywhere.
