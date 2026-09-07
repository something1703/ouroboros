# 00 — Requirements from the human

Everything the coding agent will need from you, grouped by when it is needed. **Blocking** means the phase cannot start without it. Provide values via `.env` (never commit) or via Secret Manager once Phase 1.4 exists.

---

## A. Blocking for Phase 1 (Day 1 morning)

| # | Item | Why | Where it goes |
|---|---|---|---|
| A1 | **GCP project ID** (new, dedicated) with **billing enabled** and the $100 hackathon credits + your $150 applied | Everything | `GOOGLE_CLOUD_PROJECT` |
| A2 | **Owner or Editor + Project IAM Admin** on that project for the identity running `gcloud` | Terraform needs to create service accounts and bindings | `gcloud auth application-default login` |
| A3 | **Region decision**: recommend `us-central1` for all regional services and `global` for Gemini | Agent Engine, Cloud SQL, Cloud Run, Eventarc must co-locate | `GOOGLE_CLOUD_LOCATION=global`, `OUROBOROS_REGION=us-central1` |
| A4 | **Parallel account** at platform.parallel.ai + **API key** (free credits are auto-granted; add a card to unlock $5/month recurring free tier — no charge) | All Parallel calls (BYOK path) | Secret `PARALLEL_API_KEY` |
| A5 | **GitHub repo** (public, empty) named `ouroboros` — or tell the agent the URL | Rules require public repo with license visible | `GIT_REMOTE` |
| A6 | **Decision: Marketplace or BYOK for Gemini grounding?** Recommendation: **BYOK** for speed (Marketplace subscription can take time and needs billing-admin). If you do subscribe to Marketplace later, the code supports both. | Phase 8 grounded Q&A | `PARALLEL_GROUNDING_MODE=byok` |

## B. Blocking for Phase 2–3 (Day 1 evening / Day 2)

| # | Item | Why | Where it goes |
|---|---|---|---|
| B1 | **Sample screenplay PDF(s)** — at least one you have rights to demo publicly (public-domain script, your own, or a synthetic one). Ideally 60–120 pages with real brands, songs, real people, locations. **Also one non-English script** (Hindi/Spanish) for the multilingual demo. | Ingest + demo | `fixtures/scripts/` |
| B2 | **Sample rough cut** — a 3–10 minute documentary-style video with narration containing checkable factual claims and on-screen text. You must have rights to show it publicly. | TRUE CUT ingest + demo | `fixtures/cuts/` (large files go to GCS, not git) |
| B3 | **Demo project metadata**: film title, genre, release date (set ~30 days after judging so "coil tightening" is visible), shooting countries, distribution territories (pick from the 37 Parallel-supported codes: e.g. `in`, `us`, `gb`, `de`, `jp`) | Seed data, geo-scoped search | `fixtures/projects/demo.yaml` |

## C. Needed for Phase 7–8 (Day 6–7)

| # | Item | Why | Where it goes |
|---|---|---|---|
| C1 | **Public HTTPS domain or acceptance of the default `*.run.app` URL** for webhooks and the dashboard | Parallel webhooks need a reachable URL | `PUBLIC_BASE_URL` |
| C2 | **Slack workspace + channel** where high-risk alerts should land, and permission to install Parallel's Monitor Slack app (optional but cheap) | Alerts | `SLACK_WEBHOOK_URL` or Parallel Slack install |
| C3 | **Google account emails** for three test users mapped to roles Legal / Editorial / Producer | IAP + role demo | `infra/iap_users.tfvars` |
| C4 | **Private corpus documents** (5–20 files): fake-but-realistic prior clearance logs, a licence agreement template, a legal playbook. Can be synthetic. | Vertex AI Search grounding | `fixtures/private_corpus/` |
| C5 | **Google Sheet** (empty) shared with the runtime service account as Editor | Clearance-log export | `SHEETS_EXPORT_ID` |

## D. Needed for Phase 10 (Day 9–10)

| # | Item | Why |
|---|---|---|
| D1 | **YouTube or Vimeo account** for the demo video (public) | Submission |
| D2 | **Devpost account** with the hackathon joined, team members added | Submission |
| D3 | **Screen-recording setup** (OBS or Loom), a quiet room, and 2 hours blocked for recording + edit | Demo |
| D4 | **Decision on team name and project tagline** — proposed: "Ouroboros — research that feeds itself" | Submission |

## E. Decisions the human must make (answer inline)

| # | Decision | Recommendation | Your answer |
|---|---|---|---|
| E1 | Spelling: *Ouroboros* vs *Ouroborus* | Ouroboros (classical) | **Ouroboros** (confirmed 2026-09-02) |
| E2 | Include TRUE CUT in the demo video, or CLEAR only? | Both, ~90s / ~60s split, if Phase 6 is green by Day 6 | |
| E3 | Remediation stretch (Lyria cue / image mockup) — attempt at all? | Only if Phases 1–9 are green by Day 8 noon | |
| E4 | Gemini Live API on-set Q&A — attempt at all? | Skip unless Day 9 is free | |
| E5 | Repo license | Apache-2.0 | **Apache-2.0** (confirmed 2026-09-02) |
| E6 | Per-project Parallel budget cap for the demo | $10 | |

## F. Things the agent will generate itself (you do not need to supply)

- Terraform for all GCP resources, service accounts, IAM bindings
- Cloud SQL schema and migrations
- Synthetic golden-set claims for evaluation (Phase 9) — you will be asked to spot-check 20 of them
- All prompts, schemas, Dockerfiles, CI config
- The demo video **script** (you record it)

## G. Cost expectations (so nothing surprises you)

- Google Cloud: Cloud SQL (smallest tier ~$10/10 days), Cloud Run (near-zero at demo scale), Agent Engine (per-use), Gemini tokens (≈ $5–20 for the whole build incl. video understanding), Vertex AI Search (small), BigQuery (near-zero). **Budget $60 of your credits; expect to use $30.**
- Parallel: a full CLEAR pass on a 120-page script ≈ **$6–7**; a TRUE CUT pass ≈ **$3–4**; 30 daily lite monitors ≈ **$0.09/day**. Free credits cover the build; keep the per-project cap at $10.
