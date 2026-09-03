# PHASE 06 — TRUE CUT: the factual-claims head

**Goal:** A rough cut becomes a timecoded, cited fact-check with verdicts, corrected wording, archival provenance and developing-story flags — using Responses for speed and Task for depth — and it plugs into the same Risk/Reporter/Monitor spine as CLEAR.

**Calendar:** Day 5 (afternoon) → Day 6 (morning).
**Blocking inputs:** Phase 3.3 (video ingest), Phase 5 exit.
**Reads first:** `ADK_AGENTS.md §3`, `DATA_MODEL.md §2.5–2.6`.

---

## 6.1 `FactAgent`

**Tasks**
- Implement per `ADK_AGENTS.md §3.1`: for each factual claim, build the question as `claim_text` + transcript window ±20s (from `assets` segments stored at ingest) + on-screen text in window; call `responses.ask(schema=factual_quick, effort=medium)`.
- Escalation ladder: `unverifiable`/`contradicted` with low confidence, or priority ≤ 2 → `task.run(spec=factual_claim, processor=core-fast)`; still low and priority 1 → `pro`. Attach Responses citations as `Hints` to the Task input.
- Record Evidence(method=`responses` or `task`), set status; progress to Firestore.
- Concurrency 8 (Responses is sync ~15–20s).

**Acceptance**
- On `fixtures/cuts/sample.mp4` claims: 100% have a verdict; a planted false statistic returns `contradicted` with a `corrected_statement`; a planted true event returns `supported` with ≥ 2 citations. Batch of 25 claims < 8 min.

## 6.2 `ArchiveAgent`

**Tasks**
- For `archival`/`identity` claims: Search (objective "find the original source, catalog entry, or rights holder for this footage/photo/audio") with 2 queries built from on-screen text + visual description; pick ≤ 3 URLs from archive-like domains (heuristic list: `archive.org, gettyimages, apimages, britishpathe, criticalpast, nara.gov, loc.gov, bfi.org.uk, ndtv archive…` — used for ranking, **not** as `include_domains`); Extract with objective "provenance, date, rights holder, licensing terms"; then `task.run(spec=legal_location_artwork, processor=core-fast)` to structure.
- Evidence(method=`extract`) with the extracted markdown stored under `output.extract_md` (truncate 20k).

**Acceptance**
- Planted archival clip with a known source resolves to the correct rights holder with medium+ confidence.

## 6.3 TRUE CUT behaviours in shared agents

**Tasks**
- `ClaimTriage`: factual priority rubric (`ADK_AGENTS.md §3.3`).
- `RiskAssessor`: factual rubric; `is_developing_story` → at least `medium`.
- `Reporter`: `event_stream` Monitors for developing stories (`query = "developments regarding: " + claim_text`, `location` from project's primary territory, `processor=lite`), snapshot Monitors for contradicted/partial; fact-check report markdown grouped by timecode.
- `OuroborosCoordinator` routes `mode=truecut`; auto-run after cut ingest.

**Acceptance**
- End-to-end run on the sample cut: fact-check report exists; ≥ 1 event_stream monitor created for a developing-story claim (plant one in the sample narration, e.g., an ongoing legal case or election).

## 6.4 Timeline data for the UI

**Tasks**
- `dashboard_api`: `GET /assets/{id}/timeline` → segments + claims with `t_start_ms/t_end_ms`, verdict, risk, top citation; `GET /assets/{id}/segments` (transcript).
- Store a low-res proxy MP4 + poster frame in `ouroboros-artifacts` at ingest (ffmpeg) with a signed URL endpoint so the UI can scrub.

**Acceptance**
- Timeline JSON validates; signed URL plays in a browser.

## 6.5 Cross-head handoff (A2A — stretch, only if 6.1–6.4 green by Day 6 noon)

**Tasks**
- Expose `PersonAgent`/`BrandAgent` via ADK's A2A server; `ArchiveAgent`, on finding a third-party photo of a living person, sends an A2A task "verify likeness rights for {person}" that creates a legal claim and runs `PersonAgent`.
- Otherwise implement the same handoff as a direct tool call (`create_legal_claim_from_factual`) — the product behaviour is identical; only the protocol label differs. Document which was shipped.

**Acceptance**
- A planted archival photo of a living public figure results in a linked `person` legal claim with Evidence.

---

## Exit gate
- [ ] Full TRUE CUT pass on the sample cut with evidence in `docs/evidence/06-truecut-pass.md` (verdict table, cost, timings).
- [ ] Both heads share ClaimTriage/RiskAssessor/Reporter code paths (no forks).
- [ ] Squash-merge.

## Risks
- **Responses latency stacking** → concurrency 8; UI shows per-claim progress; never wait synchronously in HTTP handlers.
- **Over-flagging "developing story"** → prompt threshold "likely to change within 90 days"; cap event_stream monitors per project at 15 (config).
- **A2A time sink** → the fallback in 6.5 is explicitly acceptable.
