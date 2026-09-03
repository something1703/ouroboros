# PHASE 03 — Ingest: from asset to Claim Ledger

**Goal:** Drop a screenplay PDF or a rough cut into GCS and, within minutes, the Claim Ledger holds every legal and factual claim with precise source references, in any language, screened by Model Armor, deduplicated and idempotent.

**Calendar:** Day 2 (afternoon) → Day 3 (morning).
**Blocking inputs:** Phase 2 exit; `00_REQUIREMENTS §B1–B2` (sample script(s) and cut).
**Reads first:** `DATA_MODEL.md §1`, `AGENTS.md §4.3`.

---

## 3.1 Event plumbing

**Tasks**
- Terraform: Eventarc trigger on `ouroboros-intake-{env}` `object.finalized` → Cloud Run `ingest` (`sa-ingest`, internal ingress, Eventarc SA invoker).
- Pub/Sub topic `claims.extracted` (+ dead-letter topic) with schema `{project_id, asset_id, kind, claim_count, run_hint}`.
- Object naming convention enforced: `scripts/{project_id}/{filename}.pdf`, `cuts/{project_id}/{filename}.{mp4|mov}`. Anything else → log + ignore (200).
- `services/ingest/main.py`: CloudEvent parsing, idempotency by `(bucket, name, generation)` stored in `assets` (skip if seen).

**Acceptance**
- Uploading a text file to a wrong prefix produces one WARN log and no rows. Uploading the same PDF twice produces one `assets` row.

## 3.2 Script understanding (`packages/gemini_client/documents.py`)

**Tasks**
- Read `/mnt/skills/public/pdf-reading/SKILL.md` before implementing (agent-side reading of PDFs for tests).
- `extract_script_claims(gcs_uri, project) -> list[Claim]` using `gemini-3.5-flash` with the PDF as a `Part.from_uri`, `response_schema=ScriptExtraction` (Pydantic → JSON schema) containing `claims[]` with: category, entity_text, claim_text, page, scene_number, scene_heading, channel (`dialogue|action_line`), excerpt (≤ 500 chars), language.
- Chunking: > 60 pages → split into 40-page windows with 2-page overlap using `pypdf` page ranges uploaded as separate GCS objects; merge by `claim_id` (dedupe across overlap).
- Prompt (`gemini_client/prompts/script_extraction.md`): defines each category with 3 examples; instructs to include **every** real brand, song/lyric, real named person, real venue/landmark, artwork, quoted text; ignore fictional entities; output language of the excerpt as BCP-47; never invent page numbers (use the PDF page index).
- Safety settings per `AGENTS.md §4.3`; on a blocked chunk, record `assets.notes` and continue.
- Multilingual: no translation at extraction; `claim_text` is written in English, `excerpt` verbatim in source language.

**Acceptance**
- On `fixtures/scripts/sample_en.pdf`: ≥ 90% recall against a hand-labelled list of 30 known entities (`fixtures/scripts/sample_en.labels.yaml`), 0 fictional-entity false positives in a 20-claim sample. Same test on the non-English script with ≥ 80% recall.
- p95 extraction time for a 120-page script < 3 min.

## 3.3 Video understanding (`packages/gemini_client/video.py`)

**Tasks**
- `extract_cut_claims(gcs_uri, project) -> list[Claim]` using `gemini-3.5-flash` video input with timestamped output; `response_schema=CutExtraction` containing `segments[]` (t_start_ms, t_end_ms, speaker, transcript) and `claims[]` with channel `narration|dialogue|on_screen_text|visual`, t_start/t_end, category (factual set + legal `brand/person/artwork` for visuals), excerpt.
- Chunk > 45 min into 20-min windows (ffmpeg in the container) with 30s overlap; merge by `claim_id`.
- Two passes for quality: pass 1 transcript+on-screen text; pass 2 claim extraction from the transcript window plus the video (so claims quote exact narration).
- Prompt (`prompts/cut_extraction.md`): factual claim definition ("a statement that could be checked against a source"), examples of statistic/event/attribution/archival/identity; instruct to flag `archival` when footage looks historical/third-party.

**Acceptance**
- On `fixtures/cuts/sample.mp4`: ≥ 85% recall on a hand-labelled list of 20 claims; timestamps within ±3s.

## 3.4 Model Armor screening (`packages/safety/`)

**Tasks**
- `screen(text, context: Literal["ingest","web_excerpt","task_output"]) -> ScreenResult` calling Model Armor `sanitizeUserPrompt` with a template that enables prompt-injection/jailbreak detection and PII detection (log only).
- Policy: on injection detected → strip the flagged spans, add `safety_flags` to the claim/evidence, continue. On hard block → raise `SafetyBlocked`; ingest records and continues with the next chunk.
- Terraform: Model Armor template `ouroboros-default`.

**Acceptance**
- Unit test with a planted "ignore previous instructions" excerpt shows flag + strip. Screening adds < 300 ms p95 per chunk (batched).

## 3.5 Ledger write + projections + events

**Tasks**
- Ingest pipeline: extract → screen → dedupe → `ClaimRepo.upsert_many` → `Projector.claim_view` for each → `Projector.project_summary` → publish `claims.extracted`.
- Dedupe rule: same `normalized_text` + category within an asset → one claim, `source.excerpt` of the first occurrence, plus `occurrences` count and `all_refs[]` stored in `source` JSON.
- Write `assets` row with page_count/duration, language, `ingested_at`.

**Acceptance**
- End-to-end: upload sample script → claims visible in Cloud SQL and Firestore; Pub/Sub message received by a test subscriber. Trace shows `ingest > extract > screen > upsert > project > publish`.

## 3.6 Ingest API for the dashboard (thin)

**Tasks**
- `dashboard_api`: `POST /projects/{id}/assets` (signed-URL upload to the right prefix), `GET /projects/{id}/assets`, `GET /projects/{id}/claims?status=&category=`.
- The demo may upload via `gsutil`; the UI upload is Phase 8.

**Acceptance**
- OpenAPI docs render; contract tests pass.

---

## Exit gate
- [ ] Both fixtures ingest end-to-end with the recall targets met (evidence: `docs/evidence/03-recall.md` with the label comparison table).
- [ ] Re-ingest is a no-op (idempotent).
- [ ] Model Armor active in `dev`.
- [ ] Squash-merge.

## Risks
- **Video input limits/latency** → keep the demo cut ≤ 10 min; chunking exists for longer.
- **Page numbering drift with chunking** → always compute `page` from the chunk offset, and test on the last chunk.
- **Extraction over-inclusion** (fictional brands) → few-shot negatives in the prompt; the label test guards it.
