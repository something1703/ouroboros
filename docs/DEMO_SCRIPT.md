# Demo video script — 3:00

Record at 1080p on the real deployed project. No mockups, no staged data.
**Live:** https://web-492372502792.us-central1.run.app

---

## Before you hit record

Each of these exists because of something measured, not a hunch.

1. **Pre-warm Ask Ouroboros.** Open the project → **Ask Ouroboros** → ask *"Can we show a
   Pepsi sign in the Mumbai scene?"* and **leave the answer on screen**. Real measured
   latency is **73–113 seconds** (Cloud Logging `httpRequest.latency`). You cannot wait
   for that on camera. Ask before recording; film the finished answer.
2. **Sign in first** so no auth screen appears mid-take.
3. **Open Script, Video and Feed once** so the PDF and the video proxy are warm.
4. **Second browser tab** parked on `/docs/architecture` for the closing shot.
5. **Do not click Run CLEAR expecting to watch it finish.** A real pass takes minutes and
   there is no progress bar. You show it *starting*, then move on.

---

## 0:00 — 0:20 · The problem

**Screen:** the landing page, slowly scrolling down to the system schematic.

> "A clearance report is true on the day it is written, and a little less true every day
> after. A brand gets sued. A historical fact gets corrected. An artist gets dropped by
> their label. And nobody finds out which parts rotted until someone is in a colour suite,
> a week from delivery."

Do not say the product name yet. Land the problem first.

---

## 0:20 — 0:40 · The answer

**Screen:** cut to the dashboard Overview. Cursor traces the Reality Drift ring, then the
spend figure, then the cadence badge.

> "Ouroboros treats a film as a set of claims about the real world. This is Reality Drift —
> how much of this project's risk picture has moved since anyone last looked. Real spend
> against a real cap. Days to release. And the monitor cadence, which tightens on its own
> as that date gets closer."

Say a number that is on screen out loud. It proves the page is live.

---

## 0:40 — 0:55 · What is in the ledger

**Screen:** scroll the claims worklist, worst risk first.

> "Eighty-two claims, extracted from this production's script and its cut, ranked worst
> risk first. These are deliberately synthetic test assets — a screenplay seeded with real
> brands and real people to exercise every clearance category, and a public-domain 1935
> film for the factual pass."

That one sentence about test assets kills the "why is a banana documentary next to Tata
Motors" question before a judge can ask it. Say it plainly and move on — it reads as test
rigour, not as an excuse.

---

## 0:55 — 1:15 · The script pass

**Screen:** the **Script** tab. A page renders with claims pinned in the right rail. Hover
one so it highlights.

> "Gemini reads the script once and extracts every claim it makes — brands, music, people,
> locations, artwork — in English and in Hindi. Each one is pinned to the page it came
> from, so a lawyer can go straight to the line."

---

## 1:15 — 1:40 · Evidence, not verdicts *(the part that matters)*

**Screen:** click a claim. The drawer opens. Scroll it slowly — citations, reasoning,
confidence, risk level.

> "And this is the part that matters. Not a verdict — evidence. Every claim carries its
> citations, the reasoning behind them, and a confidence score, researched through
> Parallel. Cheap Search first. It escalates to a full Parallel Task only when confidence
> is low *and* the claim is high priority. Two and a half cents a claim, measured."

Slow down here. Let the citations sit on screen for a beat. This is the whole product.

---

## 1:40 — 1:58 · The cut

**Screen:** the **Video** tab. Scrub the timeline; transcript on the right; click a
timecoded claim.

> "Rough cuts get the same treatment. Gemini video understanding produces a timestamped
> transcript, and every factual claim in the narration gets checked and timecoded. That is
> TRUE CUT."

---

## 1:58 — 2:20 · The loop

**Screen:** the **Feed** tab. Point at the most recent events.

> "Every verified claim gets a Parallel Monitor watching it against the live web. When
> something actually changes, a webhook fires, that one claim is re-verified, its risk is
> rescored, and Reality Drift moves. The loop re-enters at *verify* — the script has not
> changed. Only the world has."

Narrate over **real events already in the feed**. Never stage a live detection — the
webhook signing secret in this deployment is a placeholder (`docs/SECURITY.md`), and a
faked success is the one thing that would sink this.

---

## 2:20 — 2:35 · Trigger it, and ask it

**Screen:** click **Run CLEAR** — the toast appears. Do not wait. Cut straight to
**Ask Ouroboros**, where the pre-warmed answer is already on screen.

> "A legal or editorial user can trigger a fresh pass at any time. And anyone can ask the
> ledger a question — grounded in our own claims, the studio's private corpus, and live
> web search."

---

## 2:35 — 2:47 · The roles are real

**Screen:** sidebar **"Viewing as"** → switch to **Producer**. Run CLEAR greys out.

> "Roles are enforced server-side, not hidden in the UI. A producer genuinely cannot start
> a run, and genuinely cannot override a claim."

Twelve seconds, and it proves the security model is real rather than decorative. Do not
cut this to save time.

---

## 2:47 — 3:00 · The loop that runs backwards

**Screen:** the Exports panel for one beat, then cut to `/docs/architecture` — the ring
diagram.

> "Legal exports an E&O evidence pack, a fact-check report, and a clearance log. Seven
> Cloud Run services, Agent Engine, a Postgres ledger — and a research API that can call
> *back* into our own ledger, mid-task, over MCP. The loop runs both ways."
>
> "Ouroboros. Research that feeds itself."

End card: logo and wordmark.

---

## Honest gaps — do not stage these on camera

- **The webhook tail has never fired against a real signed production webhook.** The
  signing secret here is a placeholder (`docs/SECURITY.md`, `docs/BLOCKERS.md`). Narrate
  the loop over real events already in the feed.
- **There is no run-progress UI.** The backend writes real progress to Firestore
  (`_projector.run_progress`); no frontend code reads it. Run CLEAR shows a toast and
  nothing more.
- **Reality Drift reads 0%** until a monitor catches a real change. The dashboard already
  explains that in plain language on screen. That is an honest state, not a broken one.

---

## Numbers you can safely say out loud

All measured, all in `docs/COST.md`:

| Claim | Real figure |
|---|---|
| Cost per legal claim (CLEAR) | **$0.024** |
| Cost per factual claim (TRUE CUT) | **$0.053** |
| Full CLEAR + TRUE CUT pass, one script | **~$2.30** |
| Claims in the demo ledger | **82** |
| Active Parallel Monitors | **96** |
| Deployed Cloud Run services | **7** |

---

## After recording

Two takes, edit to ≤3:00, burn in captions, upload public to YouTube, verify it plays
logged out. Paste the URL into `README.md`'s hero line and the Devpost form.
