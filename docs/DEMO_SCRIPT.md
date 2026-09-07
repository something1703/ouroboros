# Demo video script

Per `docs/plan/phases/PHASE_10.md` §10.4. Record at 1080p, narrated in English, captions burned in. Show the real deployed `demo` env — no mockups, no staged data. ≤3:00 total.

**Before recording:** start a real run 10 minutes ahead of time (Run CLEAR or TRUE CUT on the demo project) so it has real progress to show on camera rather than a cold start, and have a monitor `trigger` queued so the loop segment (1:35–2:10) has something to react to live rather than waiting on a real webhook mid-recording.

| Time | Shot | Say |
|---|---|---|
| 0:00–0:15 | Title card + dashboard | "Every film makes claims about the real world. Ouroboros verifies them — and keeps verifying them until release. Built on Google's Agent Platform with Parallel as the research layer." |
| 0:15–0:40 | Upload script → feed shows claims arriving | "Drop a script in. Gemini extracts every brand, song, person, location and artwork — in any language — into a claim ledger." |
| 0:40–1:15 | Run CLEAR → progress → script heatmap → open a claim drawer | "ADK agents fan out by category. Each calls Parallel Search to triage, then Parallel Task for structured evidence with citations and confidence. Notice this line: Parallel consulted our ledger through MCP mid-research — the loop runs both ways." |
| 1:15–1:35 | Video timeline (TRUE CUT) | "Rough cuts get the same treatment: timecoded fact-checks via Parallel's Responses API, escalated to deep research when contested." |
| 1:35–2:10 | Ouroboros feed with events **after** the submission divider; trigger a monitor; watch re-verification; drift changes; Slack ping | "High-risk findings get Parallel Monitors. When the world changes, a webhook lands, a new Task run chains the prior context, risk recomputes, and the Reality Drift score moves. As release nears, the cadence tightens to hourly." |
| 2:10–2:35 | Ask Ouroboros with mixed citations; export E&O pack | "Producers ask questions grounded in the ledger, the studio's private corpus, and Parallel-grounded Gemini. Legal exports an E&O-ready evidence pack." |
| 2:35–2:55 | Architecture diagram; metrics table | "Cloud Run, Cloud SQL via MCP Toolbox, Firestore, BigQuery, Pub/Sub, Agent Engine, Model Armor — two to five cents a claim, over ninety percent field accuracy on our legal golden set." |
| 2:55–3:00 | End card | "Ouroboros. Research that feeds itself." |

**Known honest gap to work around on camera:** the re-verification loop's tail (webhook → new evidence → Slack) has never fired against a real signed production webhook — the signing secret in this deployment is still a placeholder (`docs/SECURITY.md`). For the 1:35–2:10 segment, either use `monitor.trigger()` against a claim with a real `event_stream` Monitor and show the resulting 401-then-documented-gap honestly, or narrate the mechanism over the dashboard's event feed from an earlier real detection rather than staging a live one that will fail on camera. Do not fabricate a webhook success.

**After recording:** two takes, edit, upload public to YouTube, add captions, verify it plays logged out. Paste the final URL into `README.md`'s hero line (currently a placeholder) and into the Devpost submission form.
