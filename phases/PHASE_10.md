# PHASE 10 — Remediation (stretch), demo, README, submission

**Goal:** Ship. Optional remediation only if everything else is green; then a 3-minute demo that shows the agent functioning as built, a README that lets a judge run it, the license visible, and the Devpost form submitted with hours to spare.

**Calendar:** Day 9 (8 Sep) → Day 10 (9 Sep, submit by **22:00 IST**; hard deadline 10 Sep 02:30 IST).
**Blocking inputs:** Phase 9 exit; `00_REQUIREMENTS §D`.

---

## 10.1 Remediation — Lyria temp cue (stretch; only if Day 9 starts green)

**Tasks**
- When `Risk.remediation_kind == "replace_music"`: `packages/gemini_client/lyria.py` generates a 30s instrumental cue from a mood prompt derived by Gemini from the scene (tempo, instrumentation, era, emotional arc) via the Lyria 3 API; store WAV in `ouroboros-artifacts`; attach to the claim as `remediation_asset`.
- UI: "Proposed temp cue" player in the claim drawer with a caveat: "AI-generated placeholder for editorial use; verify your Lyria licence terms."

**Acceptance**
- Two cues generated for two music claims; playable in UI.

## 10.2 Remediation — fictional brand mockup (stretch)

**Tasks**
- When `remediation_kind == "replace_brand"`: Gemini image generation renders a fictional brand mark and product mockup from a Gemini-written brief that explicitly avoids the real brand's name, colours, shapes and trade dress; run a Search (`fast`) to confirm the invented name isn't an existing trademark in the project's jurisdictions; store PNG; attach.
- UI: "Proposed replacement" card with the trademark-check citation.

**Acceptance**
- One mockup generated; the search-based name check is visible.

## 10.3 Gemini Live on-set Q&A (stretch; skip unless Day 9 afternoon is free)

- Minimal: Live API session (ADK `get-started-adk` path) wired to `AskOuroboros` tools; browser mic; 30-second demo clip. If not attempted, remove from README claims.

## 10.4 Demo video (≤ 3:00) — script

Record at 1080p, narrated in English, captions burned in. Show the real deployed `demo` env; no mockups. Suggested cut:

| Time | Shot | Say |
|---|---|---|
| 0:00–0:15 | Title card + dashboard | "Every film makes claims about the real world. Ouroboros verifies them — and keeps verifying them until release. Built on Google's Agent Platform with Parallel as the research layer." |
| 0:15–0:40 | Upload script → feed shows claims arriving | "Drop a script in. Gemini extracts every brand, song, person, location and artwork — in any language — into a claim ledger." |
| 0:40–1:15 | Run CLEAR → progress → script heatmap → open a claim drawer | "ADK agents fan out by category. Each calls Parallel Search to triage, then Parallel Task for structured evidence with citations and confidence. Notice this line: Parallel consulted our ledger through MCP mid-research — the loop runs both ways." |
| 1:15–1:35 | Video timeline (TRUE CUT) | "Rough cuts get the same treatment: timecoded fact-checks via Parallel's Responses API, escalated to deep research when contested." |
| 1:35–2:10 | Ouroboros feed with events **after** the submission divider; trigger a monitor; watch re-verification; drift changes; Slack ping | "High-risk findings get Parallel Monitors. When the world changes, a webhook lands, a new Task run chains the prior context, risk recomputes, and the Reality Drift score moves. As release nears, the cadence tightens to hourly." |
| 2:10–2:35 | Ask Ouroboros with mixed citations; export E&O pack | "Producers ask questions grounded in the ledger, the studio's private corpus, and Parallel-grounded Gemini. Legal exports an E&O-ready evidence pack." |
| 2:35–2:55 | Architecture diagram; metrics table | "Cloud Run, Cloud SQL via MCP Toolbox, Firestore, BigQuery, Pub/Sub, Agent Engine, Model Armor, IAP — under seven dollars of Parallel per script, eighty-five-plus percent field accuracy on our golden set." |
| 2:55–3:00 | End card | "Ouroboros. Research that feeds itself." |

**Tasks**
- Write the narration to `docs/DEMO_SCRIPT.md`; prepare a shot list; pre-warm the demo (start a run 10 min before recording; have a monitor `trigger` queued).
- Record two takes; edit; upload public to YouTube; add captions; verify plays logged-out.

**Acceptance**
- Video ≤ 3:00, public, English captions, shows real runtime behaviour.

## 10.5 README and repo hygiene

**Tasks**
- README sections: hero (tagline, video link, live URL), what it does (2 paragraphs), the three loops, architecture (embed `ouroboros_architecture.mermaid`), Parallel usage table (API → where in code, file/line links), Google Cloud usage table (service → where), quickstart (`make setup`, env, `make deploy`), running the demo project, evaluation results table, cost table, security summary link, roadmap, license, team.
- Ensure Parallel and Google Cloud calls are **obviously** in code: link to `packages/parallel_client/search.py`, `agents/ouroboros/clear/specialist.py`, `packages/gemini_client/grounding.py`.
- Move this planning package to `docs/plan/` and tick phase checklists.
- `LICENSE` present; **GitHub About → set license so it shows in the sidebar** (human action; verify with a screenshot).
- Clean: no secrets, no large binaries (fixtures in GCS with a download script), `.env.example` complete, CI green badge.
- Tag `v1.0.0-hackathon`.

**Acceptance**
- A fresh reviewer following the README reaches a running `dev` in < 30 min (dry-run by the agent on a scratch project if credits allow).

## 10.6 Devpost submission

**Tasks**
- Devpost form: project name "Ouroboros", tagline, description (reuse README hero + loops + impact/E&O paragraph), built-with tags (Google Cloud, Gemini, ADK, Agent Engine, Parallel, Cloud Run, Cloud SQL, Firestore, BigQuery, Pub/Sub), video URL, repo URL, hosted URL, **partner track = Parallel**, team members, images (5 screenshots + diagram).
- Submit by **22:00 IST 9 Sep**; verify the submission appears as "Submitted"; screenshot to `docs/evidence/10-submitted.png`.
- Post-submit: do not deploy to `demo` except for outage fixes; keep monitors running.

**Acceptance**
- Submission confirmed; all rule items in `README.md` non-negotiables ticked.

---

## Exit gate
- [ ] Video public and linked; repo public with visible license; hosted URL up with IAP test users documented for judges (per rules, provide test credentials in the Devpost "testing instructions" field if judges need access — or make a read-only judge account).
- [ ] Devpost shows Submitted, Parallel track.
- [ ] `demo` stable; alerts quiet; monitors active.

## Risks
- **Judges can't get past IAP** → create a `judge@` read-only account and put instructions in the submission; alternatively expose a read-only public replica of the dashboard for the demo project (flag `PUBLIC_READONLY_PROJECT=demo`).
- **Video overruns** → script is timed; cut TRUE CUT segment first if needed, never the loop segment.
- **Last-minute breakage** → freeze happened in 9.7; hotfix only through `main` with CI.
