# Demo video script — 3:00

Record at 1080p on the real deployed `demo` project. No mockups, no staged data.
Live URL: https://web-492372502792.us-central1.run.app

---

## Before you hit record (do these, in this order)

These exist because of real, measured behaviour — skipping them is what makes a demo
look broken on camera.

1. **Pre-warm Ask Ouroboros.** Open the project → **Ask Ouroboros** → ask
   *"Can we show a Pepsi sign in the Mumbai scene?"* and **leave the answer on screen**.
   Real measured latency is **73–113 seconds** (Cloud Logging `httpRequest.latency`).
   You cannot wait for that on camera. Ask it before recording; film the finished answer.
2. **Sign in and land on the project page** so no auth screen appears mid-take.
3. **Open the tabs once** (Script, Video, Feed) so the PDF and video proxy are warm —
   first load fetches a signed URL and renders pages.
4. **Have two browser tabs ready:** the dashboard, and
   `/docs/architecture` for the closing shot.
5. **Do not click Run CLEAR expecting to see it finish.** A real pass takes many
   minutes and there is no progress bar in the UI — you show it *starting*, then move on.

---

## The script

| Time | Shot | Say |
|---|---|---|
| **0:00–0:12** | Landing page hero, slow scroll to the system schematic | "A clearance report is true the day it's written, and a little less true every day after. A brand gets sued, a fact gets corrected, an artist gets dropped — and nobody finds out until you're a week from delivery." |
| **0:12–0:28** | Cut to dashboard Overview. Cursor traces the Reality Drift ring, then spend, then the cadence badge | "Ouroboros treats a film as a set of claims about the real world. This is Reality Drift — how much of this project's risk picture has moved since anyone last looked. Real spend, real days to release, and the monitor cadence, which tightens as release approaches." |
| **0:28–0:45** | Scroll the claims worklist, worst-risk-first | "Eighty-two claims extracted from this production's script and cut, ranked worst risk first. These are the deliberately synthetic test assets — a screenplay seeded with real brands and people to exercise every clearance category, and a public-domain 1935 film for the factual pass." |
| **0:45–1:05** | **Script tab.** Page renders, claims pinned in the right rail. Hover one | "Gemini reads the script once and extracts every claim it makes — brands, music, people, locations, artwork — in English and Hindi, each pinned to the page it came from." |
| **1:05–1:30** | Click a claim → drawer opens. Slowly scroll the evidence: citations, confidence, risk | "And this is the part that matters. Not a verdict — evidence. Every claim carries its citations, the reasoning, and a confidence score, researched through Parallel. Cheap Search first; escalate to a Parallel Task only when confidence is low and the claim is high priority." |
| **1:30–1:48** | **Video tab.** Scrub the timeline; transcript on the right; click a timecoded claim | "Rough cuts get the same treatment. Gemini video understanding produces a timestamped transcript, and every factual claim in the narration is checked and timecoded — that's TRUE CUT." |
| **1:48–2:15** | **Feed tab.** Point at today's fresh events | "Every verified claim gets a Parallel Monitor watching it against the live web. When something actually changes, a webhook fires, the claim is re-verified, risk is rescored, and Reality Drift moves. The loop re-enters at *verify* — the script hasn't changed, only the world has." |
| **2:15–2:30** | Click **Run CLEAR** → toast appears. Don't wait. Cut to **Ask Ouroboros** (pre-warmed answer already on screen) | "A legal or editorial user can trigger a fresh pass at any time. And anyone can ask the ledger a question — grounded in our own claims, the studio's private corpus, and live web search." |
| **2:30–2:42** | Sidebar **"Viewing as"** → switch to **Producer** → Run CLEAR is now disabled | "Roles are enforced server-side, not hidden in the UI. A producer genuinely cannot start a run or override a claim." |
| **2:42–2:58** | Exports panel (one click), then cut to `/docs/architecture` — the loop diagram | "Legal exports an E&O evidence pack, a fact-check report, and a clearance log. Seven Cloud Run services, Agent Engine, a Postgres ledger — and a research API that can call *back* into our own ledger mid-task through MCP. The loop runs both ways." |
| **2:58–3:00** | End card: logo + wordmark | "Ouroboros. Research that feeds itself." |

---

## Honest gaps — do not stage these on camera

- **The webhook tail has never fired against a real signed production webhook.** The
  signing secret in this deployment is a placeholder (`docs/SECURITY.md`). Narrate the
  loop over *real events already in the Feed*; never fake a live detection.
- **There is no run-progress UI.** The backend writes real progress to Firestore
  (`_projector.run_progress`), but no frontend code reads it. Clicking Run CLEAR shows
  a toast and nothing more — so show the toast and move on, don't wait for a bar.
- **Reality Drift reads 0%** unless a monitor has caught a real change. The dashboard
  says so in plain language on screen — that's an honest state, not a broken one. If a
  judge asks, the in-app explanation already answers it.

---

## After recording

Two takes, edit to ≤3:00, burn in captions, upload public to YouTube, verify it plays
logged out. Paste the final URL into `README.md`'s hero line and the Devpost form.
