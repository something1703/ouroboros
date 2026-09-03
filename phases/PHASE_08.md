# PHASE 08 — Dashboard & governance

**Goal:** A complete, role-aware product surface: script risk heatmap, video claim timeline, live Ouroboros feed, Reality Drift, grounded Q&A (Parallel grounding + private corpus), and E&O-grade exports — behind IAP with three roles. This is what the judges *see*; Design is a scored criterion.

**Calendar:** Day 7 (afternoon) → Day 8 (morning).
**Blocking inputs:** Phases 5–7; `00_REQUIREMENTS §C3–C5`.
**Reads first:** `/mnt/skills/public/frontend-design/SKILL.md` (mandatory before any UI code), `DATA_MODEL.md §4`.

---

## 8.1 `dashboard_api` completion

**Tasks**
- Endpoints: projects (list/get/create), assets (upload signed URL, list), claims (list with filters, get with full evidence history, patch `human_override` for status/risk with note → history `actor=human`), runs (start CLEAR/TRUECUT, SSE progress), events feed (paged), metrics (drift, spend, counts), exports (8.5), ask (8.4), internal jobs (tighten, bq_sync).
- Auth: read IAP JWT (`x-goog-iap-jwt-assertion`), verify, map email → role via `config/roles.yaml` (from `infra/iap_users.tfvars`); role enforced per endpoint (`legal` can override legal claims; `editorial` factual; `producer` read-only + exports).
- SSE endpoint streams Firestore `runs/{id}` and `events` changes.

**Acceptance**
- OpenAPI complete; role tests (403 matrix); SSE test.

## 8.2 Web app (`web/`) — foundation

**Tasks**
- Vite + React + TypeScript + Tailwind; design per frontend-design skill: dark editorial palette, one accent (ouroboros orange `#FB631B` nods to Parallel), monospace for IDs/timecodes, generous whitespace, zero template look.
- Layout: left nav (Projects → Project); top bar with **Reality Drift** gauge, spend, days-to-release and current monitor cadence (`1w/1d/1h` badge — the "coil").
- Project overview: counts by status and risk; "Ouroboros feed" (live, 8.3); quick actions (Run CLEAR, Run TRUE CUT, Trigger monitors — role-gated).

**Acceptance**
- Lighthouse a11y ≥ 90; works at 1280px and 390px; no console errors.

## 8.3 Script heatmap, video timeline, feed

**Tasks**
- **Script view:** render the PDF (pdf.js) with a per-page risk strip and inline pins per claim (color by risk); click → claim drawer: claim text, category, jurisdiction chips with territory flags, evidence summary, citations `[n]` with links, Basis confidence per field, `mcp_tool_calls` line ("Parallel consulted Ouroboros ledger: get_prior_decisions"), verification history timeline, monitor status, override controls (role-gated).
- **Video view:** proxy video player; claim markers on a scrubber colored by verdict; transcript panel synced to time; same claim drawer.
- **Feed:** live list of `events` entries: monitor detected / re-verified / risk changed, with deltas and timestamps; filter by kind; "since submission" divider (config `SUBMISSION_AT`) — visually proves the system kept working after the deadline.
- Empty/loading/error states designed, not default.

**Acceptance**
- Screenshots in `docs/evidence/08-ui/`; a user can go from project → page 12 pin → citation URL in ≤ 3 clicks.

## 8.4 Ask Ouroboros (grounded Q&A)

**Tasks**
- `AskOuroboros` agent (ADK) per `ADK_AGENTS.md §4`: tools = ledger read, Vertex AI Search datastore (create in Terraform; ingest `fixtures/private_corpus/` via a script), and Gemini grounding with `ToolParallelAiSearch` (`custom_configs={"mode":"basic","location": primary_territory}`; BYOK key from Secret Manager or Marketplace).
- Citation rendering: byte-offset-safe insertion of `[n]` markers per part; source list mixes ledger claims, corpus docs and web chunks, labelled.
- UI: chat drawer on the project page; example prompts ("Can we show a Pepsi sign in the Mumbai scene?", "What did we decide about Bohemian Rhapsody last year?").
- Guardrail line rendered under answers: "Evidence, not legal advice."

**Acceptance**
- Three scripted questions produce answers citing (a) a ledger claim, (b) a corpus doc, (c) a Parallel web source; `grounding_metadata.web_search_queries` logged. Evidence in `docs/evidence/08-ask.md`.

## 8.5 Exports

**Tasks**
- Read `/mnt/skills/public/pdf/SKILL.md` and `/mnt/skills/public/docx/SKILL.md` before implementing.
- **E&O evidence pack (PDF):** cover (project, date, drift, cadence), summary table by risk, then one page per `high`/`blocking` claim: claim, source ref, evidence fields, per-field confidence, citations with retrieval dates, verification history, human overrides with signer. Generated server-side (`weasyprint` or `reportlab`), stored in `ouroboros-artifacts`, signed URL.
- **Clearance log → Google Sheets:** one row per legal claim (columns per industry clearance-log convention: scene, page, item, category, rights holder, contact, status, risk, cost band, notes, last verified). Uses Sheets API with `sa-dashboard-api`.
- **Fact-check report (PDF):** timecode-ordered verdicts with corrected wording.

**Acceptance**
- All three exports generate for the demo project; PDF opens cleanly; Sheet populated; links visible in UI (producer role).

## 8.6 IAP + roles

**Tasks**
- Terraform: IAP on the dashboard Cloud Run (via load balancer + serverless NEG) or Cloud Run IAP integration where available; OAuth consent screen; `iap_users.tfvars` with three emails → roles.
- Role banner in UI; role-gated controls tested.

**Acceptance**
- Three test accounts see correct permissions; unauthenticated access is blocked; evidence screenshots.

## 8.7 Upload UX

**Tasks**
- Drag-and-drop upload to signed URL with prefix chosen by type; progress; on complete, the feed shows "Ingest started" and then claim counts rising (from Firestore).

**Acceptance**
- Uploading the sample script from the UI triggers ingest and auto-run.

---

## Exit gate
- [ ] A full user journey recorded as a 60-second GIF (`docs/evidence/08-journey.gif`): upload → claims appear → run → risk pins → claim drawer → ask → export.
- [ ] Role matrix passes; IAP live on `demo`.
- [ ] Squash-merge.

## Risks
- **IAP + Cloud Run setup time** → do it first thing in 8.6 with Terraform; fallback for `dev` only: Google Identity Services sign-in in the app with the same role mapping (never for `demo`).
- **UI scope creep** → the three views + feed + ask + exports are the whole surface; no settings pages, no admin.
- **Grounding quota** (200/min shared) → irrelevant at demo scale; still add client-side debounce.
