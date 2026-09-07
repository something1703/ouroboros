// Written for this site, from the project's own record: docs/DECISIONS.md,
// docs/evidence/*, docs/COST.md, docs/BLOCKERS.md, and the code the numbers come
// from. Every figure here is one that was actually measured, and every one that
// wasn't is labelled as an estimate or a target where it appears. The failures are
// in here for the same reason the successes are — a docs page that only contains
// things that worked is a brochure.

export type Block =
  | { kind: "lede"; text: string }
  | { kind: "p"; text: string }
  | { kind: "h"; text: string }
  | { kind: "figure"; id: "loop" | "cadence" | "system"; caption?: string }
  | { kind: "tree"; caption?: string; lines: { depth: number; name: string; note?: string }[] }
  /** A decision, in the shape decisions are actually made: what we took, what we
   *  turned down, and the reason — not a feature bullet. */
  | { kind: "choice"; took: string; over: string; because: string }
  /** Something that broke in production, and what it changed. */
  | { kind: "found"; heading: string; symptom: string; chased: string; actual: string; lesson: string }
  | { kind: "measures"; caption?: string; rows: { label: string; value: string; note?: string }[] }
  | { kind: "limits"; heading: string; items: string[] }

export interface DocEntry {
  slug: string
  title: string
  summary: string
  /** Shown on the index so a reader can pick the one they want in one pass. */
  readingTime: string
  blocks: Block[]
}

export const DOCS: DocEntry[] = [
  // ---------------------------------------------------------------- approach --
  {
    slug: "approach",
    title: "How we approached it",
    summary:
      "The reframe the whole system rests on, the three things we turned down, and why the answer had to be a loop.",
    readingTime: "6 min",
    blocks: [
      {
        kind: "lede",
        text: "Clearance is not hard because the research is hard. It is hard because the research goes stale. A clearance memo is true on the day it is written and quietly less true every day after, and nobody finds out which parts rotted until somebody is standing in a colour suite six days from delivery.",
      },
      {
        kind: "p",
        text: "So we did not try to build a better researcher. We tried to build research that does not stop. Everything below follows from that one decision, including the parts of it that turned out to be expensive.",
      },

      { kind: "h", text: "The reframe: a film is a set of claims" },
      {
        kind: "p",
        text: "A screenplay is not prose to a clearance lawyer. It is a list of assertions about the real world that someone will eventually have to stand behind: this brand can appear on this shelf, this song can play under this scene, this named person can be depicted this way, this building can be shot from this angle. A rough cut adds a second kind: this event happened on this date, this figure is correct, this archival footage is what the lower third says it is.",
      },
      {
        kind: "p",
        text: "Once you write it down that way the shape of the system falls out. A claim is a row. A row has a status. A row can be verified, and re-verified, and can go stale — and staleness becomes a thing you can measure instead of a thing you worry about. Everything downstream is bookkeeping on that one abstraction.",
      },
      {
        kind: "p",
        text: "The split into two heads comes from the same place. Legal exposure and factual exposure fail differently: a legal claim is wrong when someone else owns something, and the fix is to replace the asset. A factual claim is wrong when the record says otherwise, and the fix is to change the cut or the caption. They need different sources, different escalation rules, and different people reading the output — so CLEAR and TRUE CUT are separate agent trees over the same ledger, not one agent with a mode flag.",
      },

      { kind: "h", text: "Three things we turned down" },
      {
        kind: "choice",
        took: "A standing loop that re-checks every verified claim until release.",
        over: "A one-shot clearance report generated on demand.",
        because:
          "A report is a photograph of a moving thing. The interesting failure in clearance is never 'we did not look' — it is 'we looked in March'. A report cannot tell you which of its own findings have since changed, and that is the only question anyone actually has in the last month of post.",
      },
      {
        kind: "choice",
        took: "Structured verification with per-field evidence and citations.",
        over: "A chat interface over a corpus of legal documents.",
        because:
          "Clearance output has to survive being read by someone adversarial. 'Ask the assistant' produces an answer with no schema, no provenance, and no way to diff today's answer against last week's. We needed something a monitor could compare against itself, which means it had to be a record, not a reply.",
      },
      {
        kind: "choice",
        took: "Automatic escalation, with a human override that is always recorded.",
        over: "A human-in-the-loop queue where every claim waits for approval.",
        because:
          "A feature script produces claims in the dozens. Gating all of them on a reviewer just moves the bottleneck and guarantees the loop stops running the moment anyone goes home. The system decides on its own and writes down why; the override exists, requires a note, and lands in the audit trail permanently.",
      },

      { kind: "h", text: "What the loop actually looks like" },
      {
        kind: "figure",
        id: "loop",
        caption:
          "The return path is a chord, not another lap. Ingest and triage happen once per asset. Verify, watch, and drift are what repeat — for every verified claim, until the release date.",
      },

      { kind: "h", text: "The idea that cost the most to learn" },
      {
        kind: "p",
        text: "The first version passed work between agents the obvious way: each stage wrote its results into shared session state and the next stage read them. That is what the framework encourages and it is what our own agent spec said to do.",
      },
      {
        kind: "p",
        text: "It was wrong, and it took six other bug fixes before we could see it. A run that died partway through left claims stranded in an intermediate status — no longer pending, not yet verified, and invisible to every future run, because the next run's triage stage only looked at what the current session had put in front of it. Every retrigger landed on the identical numbers no matter what we fixed.",
      },
      {
        kind: "p",
        text: "The fix was to delete the contract. Now every stage discovers its own work by querying the ledger for the status it operates on, and session state carries nothing that matters. The system became resumable by removing a feature rather than adding one, and a crashed run stopped being a data-loss event and became a pause.",
      },
      {
        kind: "p",
        text: "That is the single most load-bearing idea in the codebase: in a multi-agent system, resumability is a property of where work is discovered, not where it is stored.",
      },
    ],
  },

  // ------------------------------------------------------------ architecture --
  {
    slug: "architecture",
    title: "Architecture",
    summary: "The services, the ledger, and the two loops — including the one that runs backwards.",
    readingTime: "8 min",
    blocks: [
      {
        kind: "lede",
        text: "Seven Cloud Run services, one Postgres ledger, one agent runtime, and a research API that can call back into us. Everything below is deployed and running; where something is built but unproven, it says so.",
      },
      {
        kind: "figure",
        id: "loop",
        caption: "The five stages, and where the cycle re-enters.",
      },

      { kind: "h", text: "Ingest" },
      {
        kind: "p",
        text: "A script or a cut lands in Cloud Storage. Eventarc fires on object finalisation and invokes the ingest service. Gemini reads a script page by page and a cut frame by frame, transcribing dialogue as it goes, and returns structured claims — each one carrying its exact source, so a legal claim points at a page and a scene and a video claim points at a timestamp and a channel (dialogue, on-screen text, or visual).",
      },
      {
        kind: "p",
        text: "Every piece of extracted text goes through Model Armor before it reaches a model context, and again for every web excerpt fetched later in the loop. Asset and claim IDs are content-derived hashes, so re-uploading the same file is a no-op rather than a duplicate.",
      },
      {
        kind: "measures",
        caption: "Extraction, measured on real assets.",
        rows: [
          { label: "English script recall", value: "17 / 17", note: "100%, against a 90% target; none of the 4 fictional distractors extracted" },
          { label: "Hindi script recall", value: "6 / 7", note: "85.7%, against an 80% target; missed a location named only in spoken narration" },
          { label: "Video recall", value: "3 / 6", note: "50%, against an 85% target — below bar, documented rather than tuned away" },
          { label: "Cost per script extraction", value: "$0.00101", note: "one real Gemini call, 3,751 in / 2,442 out, 27 claims" },
        ],
      },

      { kind: "h", text: "Orchestration" },
      {
        kind: "p",
        text: "A coordinator routes each asset to one of two heads. Both are Agent Development Kit trees running on Vertex AI Agent Engine. Triage runs first in each and checks the studio's own ledger for a near-identical claim already resolved on a past production, so the same question is not re-answered from scratch.",
      },
      {
        kind: "tree",
        caption:
          "Four legal specialists fan out in parallel, two at a time each. There is no QuoteAgent — the quote category exists in the schema and is deliberately unserviced.",
        lines: [
          { depth: 0, name: "OuroborosCoordinator", note: "routes by mode, never researches" },
          { depth: 1, name: "CLEAR", note: "legal exposure" },
          { depth: 2, name: "ClaimTriage" },
          { depth: 2, name: "ClearFanOut", note: "parallel" },
          { depth: 3, name: "MusicAgent", note: "entity search" },
          { depth: 3, name: "BrandAgent", note: "extract" },
          { depth: 3, name: "PersonAgent", note: "entity search" },
          { depth: 3, name: "LocationArtAgent", note: "extract" },
          { depth: 2, name: "RiskAssessor" },
          { depth: 2, name: "Reporter", note: "creates the monitors" },
          { depth: 1, name: "TRUE CUT", note: "factual exposure" },
          { depth: 2, name: "ClaimTriage" },
          { depth: 2, name: "FactAgent", note: "responses first, task on escalation" },
          { depth: 2, name: "ArchiveAgent", note: "search → extract → task" },
          { depth: 2, name: "RiskAssessor" },
          { depth: 2, name: "Reporter" },
          { depth: 1, name: "AskOuroboros", note: "grounded Q&A over the ledger and the studio corpus" },
        ],
      },

      { kind: "h", text: "The ledger, and why agents cannot reach it" },
      {
        kind: "p",
        text: "Cloud SQL Postgres is the system of record: projects, assets, claims, evidence, verification history, monitors, risk, cost events. Firestore holds denormalised views the dashboard reads live. BigQuery mirrors the ledger for analytics.",
      },
      {
        kind: "p",
        text: "No agent talks to that database. Every read and write from agent code goes through an MCP Toolbox service, and that is not a layering preference — it is the only thing that works. Agent Engine's managed runtime has no network path to Cloud SQL's private IP at all, which we established after three consecutive, plausible, entirely wasted fixes.",
      },
      {
        kind: "found",
        heading: "The connection-pool bug that was never a connection-pool bug",
        symptom:
          "A verification pass failed 46 of 62 claims with connection timeouts. Then 102. Then 155 and climbing.",
        chased:
          "Raised the application pool from 15 to 30. Still failed. Reversed it — dropped concurrency from 5 to 2 and the pool back to 10, reasoning the shared micro instance only allows 25 connections. Still failed. Raised max_connections to 100 on the instance itself. Still failed.",
        actual:
          "Querying pg_stat_activity during a live run showed about twelve connections total, all of them Toolbox's own, all idle, all having already finished their query. The client was never reaching the server. There was no route.",
        lesson:
          "A timeout and a missing network path look identical from the application's side, and every local test hid it because none of them exercised more than four claims. Three defensible fixes in a row can all be wrong about the same symptom.",
      },

      { kind: "h", text: "Two agents, one project, two real invoices" },
      {
        kind: "p",
        text: "Agent Engine runs up to two instances. Both can pick up a run for the same project, and both did: each read the ledger, each saw no monitor existed yet, and each created a real, separate, billable Parallel Monitor. A duplicate check found 92 monitor rows across 28 distinct claims. Forty-five were cancelled by hand.",
      },
      {
        kind: "p",
        text: "An existence check could not have prevented this and neither could a database uniqueness constraint, because every real API call mints a genuinely unique monitor ID — there is nothing to conflict on. The fix is a Postgres advisory lock keyed on the project, taken for the duration of the run. Concurrency control had to live outside the data, because the data was correct.",
      },

      { kind: "h", text: "The loop that runs backwards" },
      {
        kind: "p",
        text: "Parallel Task runs can call back into our ledger while they are researching. A bearer-gated, rate-limited proxy exposes exactly three read-only tools — get a claim, list claims, get prior decisions — and nothing else. A research task working on a brand claim can therefore ask what this studio decided about that brand on a previous production, mid-run, without ever holding a Google credential.",
      },
      {
        kind: "p",
        text: "This is verified end-to-end from a job with no VPC connector, which is the point: the path in is deliberately narrow enough to hand to an external system.",
      },

      { kind: "h", text: "The whole system, one diagram" },
      {
        kind: "p",
        text: "This is the planning-time architecture diagram, the same one the repository's README embeds — every service, every Google Cloud and Parallel API, and how they actually connect. Solid nodes are built and live; the dashed ones (Lyria remediation, a fictional-brand mockup, Gemini Live, and agent-to-agent handoff) were Phase 10 stretch goals that were never attempted, kept on the diagram rather than deleted so the gap between planned and shipped stays visible rather than quietly edited away.",
      },
      { kind: "figure", id: "system" },
    ],
  },

  // -------------------------------------------------------------- evidence ---
  {
    slug: "evidence",
    title: "What counts as evidence",
    summary:
      "Per-field basis over verdicts, why confidence is a minimum and not an average, and the one number the dashboard leads with.",
    readingTime: "5 min",
    blocks: [
      {
        kind: "lede",
        text: "A verdict is not evidence. The unit this system produces is a record with its reasoning attached, per field, with citations and retrieval dates — because the whole point is that someone will read it later and need to know whether to believe it.",
      },

      { kind: "h", text: "Basis, not answers" },
      {
        kind: "p",
        text: "Each verification cycle writes one evidence record, and each record is a set of per-field results. Every field carries its own reasoning, its own citations with the date they were retrieved, and its own confidence. There is no single free-text answer anywhere in the schema.",
      },
      {
        kind: "p",
        text: "A claim's overall confidence is the minimum across its required fields, not the average. This matters more than it sounds like it should: averaging lets three well-sourced fields hide one that nobody could substantiate, which is exactly the field that ends up mattering. Taking the minimum means a claim is only as trustworthy as its weakest supported part, which is how a lawyer would read it anyway.",
      },

      { kind: "h", text: "Numbers we do not compute with a model" },
      {
        kind: "p",
        text: "Report fields that are pure aggregation are overwritten in code after the model's turn finishes. We did not start there. A risk breakdown came back as an empty object despite an explicit instruction that it was a literal count, and a monitors-created count came back as two in a run where both monitor creations had failed with a 422 — the model was counting attempts as successes.",
      },
      {
        kind: "p",
        text: "After the fix, the model's own printed output still said the wrong thing, which is how we know the override is what fixed it rather than the prompt. Anything with no judgment in it is arithmetic, and arithmetic is not a language task.",
      },

      { kind: "h", text: "How well it actually does" },
      {
        kind: "measures",
        caption:
          "A hand-authored golden set of 50 claims — 25 legal, 25 factual, across 14 jurisdictions, 5 of them not in English. Run live against the real pipeline.",
        rows: [
          { label: "Legal accuracy", value: "92%", note: "23 of 25; bar was 85%" },
          { label: "Factual accuracy", value: "88%", note: "22 of 25; bar was 85%" },
          { label: "High-confidence precision (legal)", value: "94%", note: "bar was 90%" },
          { label: "High-confidence precision (factual)", value: "88%", note: "below the 90% bar" },
          { label: "Cost per legal claim", value: "$0.024", note: "$0.600 for the set" },
          { label: "Cost per factual claim", value: "$0.053", note: "$1.350 for the set" },
          { label: "Errors", value: "0", note: "in both domains, after a real bug was fixed — see below" },
        ],
      },
      {
        kind: "p",
        text: "One honest caveat, and it is a real one: a second run of the same set on the same day gave 88% legal and 96% factual. Which domain clears the bar flips between runs. We are reporting a measurement with a sample size of two, and three of the five misses look on inspection like imprecision in our own golden labels rather than system errors — which is itself an unverified claim, and a human spot-check is still open.",
      },
      {
        kind: "found",
        heading: "A 60% accuracy score that was pure infrastructure",
        symptom:
          "The first golden run scored legal at 60%, with 10 of 25 claims failing on a missing API key.",
        chased: "Nothing — the failures were all in the first concurrent burst, which was the tell.",
        actual:
          "The secret lookup is cached, and the first wave of concurrent threads all raced to populate that cache at once. A concurrent error from Secret Manager was being mapped onto a generic not-found, so the log said the secret did not exist when it did.",
        lesson:
          "Priming the cache before any concurrency starts moved the score to its real value: 92%, not 60%. An accuracy number measured through a broken harness is not a low score, it is not a score.",
      },

      { kind: "h", text: "Reality Drift" },
      {
        kind: "p",
        text: "One project-wide number: the fraction of claims whose latest verification changed something versus the previous cycle, weighted by risk, so a blocking claim that moved counts far more than a low-risk claim that did not. It answers the only question that matters in the last month — how much of this picture has moved since anyone looked.",
      },
      {
        kind: "limits",
        heading: "Where this is honestly incomplete",
        items: [
          "Reality Drift on the live demo project is currently 0.0. The formula is real and the code path is real, but no monitor cycle has yet detected and processed a material change, so there is no measured non-zero value to show. The number on the landing page is read live from the same API the dashboard reads; it says zero because it is zero.",
          "The full loop has never completed end to end. Real monitor deliveries were captured and correctly rejected, because the webhook signing secret in production is still a documented placeholder — so the tail of the loop past detection is built and unit-tested but unproven in production.",
          "Archival and identity claims fall through the risk pre-scorer without a branch for their output shape, so their risk defaults to low regardless of what was found.",
          "Slack notification is wired and tested but has never fired on a real event.",
        ],
      },
    ],
  },

  // -------------------------------------------------------------- parallel ---
  {
    slug: "parallel",
    title: "Using Parallel",
    summary: "Which API for which question, why the cadence tightens, and what a quiet monitor means.",
    readingTime: "5 min",
    blocks: [
      {
        kind: "lede",
        text: "Four of Parallel's APIs do different jobs here, and the interesting engineering is in choosing between them cheaply rather than in calling any one of them.",
      },

      { kind: "h", text: "Search, Task, Responses, Memory" },
      {
        kind: "p",
        text: "Search is the default first pass — a handful of good sources settles most questions, and it is the cheapest thing on the price list. Task is for claims that need real research: it returns per-field basis output, which is the shape our evidence records already have, so nothing is lost in translation. Responses handles quick factual lookups. Memory, scoped per studio, is what lets triage recognise a claim this studio has already resolved.",
      },
      {
        kind: "p",
        text: "Escalation from the fast processor to the expensive one is deliberately narrow: only when confidence comes back low and the claim is high priority. Both conditions, not either. Everything else stays cheap, which is the only reason a full pass on a feature script costs what it does.",
      },
      {
        kind: "measures",
        caption: "Real spend, from the project's own cost ledger.",
        rows: [
          { label: "Full CLEAR pass, 62 claims", value: "$1.54", note: "bar was under $8" },
          { label: "Estimated cost per script", value: "~$2.30", note: "part-estimated: real per-unit rates, assumed claim mix; target was $7" },
          { label: "Cumulative project spend to date", value: "$2.27", note: "against a $10 hard cap enforced per project" },
          { label: "Monitored claim, release week", value: "$0.24/day", note: "24 hourly checks at the monitor base rate" },
        ],
      },

      { kind: "h", text: "The cadence tightens as release approaches" },
      {
        kind: "p",
        text: "Every verified claim gets a monitor. How often it is checked is a function of one variable — days until release — recomputed every morning by a scheduled job that also reconciles each monitor's webhook URL. Drag the release date and watch what the scheduler does:",
      },
      { kind: "figure", id: "cadence" },
      {
        kind: "p",
        text: "Parallel only sends a webhook when it detects an actual material change, not on every scheduled check. This is worth internalising when reading the dashboard: a quiet monitor is a claim that is still true. It is not a monitor that stopped working.",
      },

      {
        kind: "found",
        heading: "Ten monitors on famous entities, twenty-five minutes, zero events",
        symptom:
          "We triggered monitors on claims about Obama, Tesla, Apple, Coca-Cola — and nothing came back at all.",
        chased: "Whether the monitors were configured correctly. They were.",
        actual:
          "Every demo claim was a fact about a fictional film's own content — 'a photo of this person hangs on the wall in scene 14'. That has no real-world development to detect, ever. The claims were unfalsifiable by construction.",
        lesson:
          "Replacing them with a claim whose underlying fact genuinely moves produced two real deliveries within two minutes of each trigger, identified as externally originated by user agent and source IP rather than by trusting the payload. A monitoring system can be perfectly wired and still detect nothing.",
      },

      {
        kind: "found",
        heading: "A silent misdirection nothing reported",
        symptom: "None. Nothing failed, no alert fired, no log line appeared.",
        chased: "Nothing — this was found by reading a deployment step while building something else.",
        actual:
          "The public base URL resolved to the dashboard API, which has no webhook routes at all; those live on a separate receiver service. Every monitor ever created, across every phase, carried a callback URL that would 404 the instant Parallel tried to deliver to it.",
        lesson:
          "Fixed at the source and made self-healing: the daily job now reconciles every existing monitor's webhook URL unconditionally, so the fleet repairs itself rather than requiring a migration. A bug with no symptom needs a mechanism, not a patch.",
      },
    ],
  },

  // ------------------------------------------------------------- found live --
  {
    slug: "found-live",
    title: "What broke",
    summary:
      "Five failures that changed the design, including a safety filter that blocked everything and six endpoints that were open to the internet.",
    readingTime: "6 min",
    blocks: [
      {
        kind: "lede",
        text: "This project has a policy of verifying against real deployed services rather than mocks, and the reason is on this page. None of the following was found by a test suite. All of it was found by running the thing.",
      },

      {
        kind: "found",
        heading: "The safety filter was blocking one hundred percent of traffic",
        symptom: "Adversarial text was correctly blocked. So was the clean control text.",
        chased: "Initially nothing — a blocked jailbreak looks like success.",
        actual:
          "The filter results object carries one entry per configured filter, whether or not it matched. Our code treated the presence of a key as a match. With a single filter configured that happens to behave correctly; the moment the template had two, every call was hard-blocked regardless of content.",
        lesson:
          "A safety system that fails closed is invisible until you test what is supposed to pass. Now covered by offline tests built from real protocol objects, plus live tests against the deployed template.",
      },

      {
        kind: "found",
        heading: "Six endpoints with no authentication at all",
        symptom: "None. Everything worked.",
        chased:
          "Not chased — noticed while redesigning an unrelated page, then deliberately swept for others of the same class.",
        actual:
          "Routes written when the platform's own IAM was the only gate stayed as they were when the service was later made publicly reachable for browser sign-in. Uploading arbitrary files as a project's script, and reading any project's claims, assets, video timeline and playback URLs, required zero credentials on the live public service. One of them started a real, billed agent run.",
        lesson:
          "Changing the outer auth layer silently reclassifies every route written under the old assumption. There was no code change to review, because nothing changed — which is precisely why nothing caught it.",
      },

      {
        kind: "found",
        heading: "A service that had never emitted a single trace",
        symptom:
          "Cloud Trace returned nothing for the dashboard API after hours of heavy real traffic.",
        chased: "Whether tracing was configured. It was, identically to three services that worked.",
        actual:
          "Cloud Run freezes container CPU between requests, so the background span exporter never gets scheduled. The three working services each handle one message and flush explicitly at the end. The dashboard API has many endpoints and flushed in none of them — it had never exported a trace in the project's entire history.",
        lesson:
          "One HTTP middleware, covering every route, rather than an edit per handler. A real four-span trace appeared on the next request. The lesson about frozen CPU was already written down in our own tracing module's docstring; the service that needed it was the one that never read it.",
      },

      {
        kind: "found",
        heading: "Continuous integration had been failing for six phases",
        symptom: "A green-looking repository. Nobody was reading the runs.",
        chased: "Nothing, for far too long.",
        actual:
          "Three separate faults stacked. Tests had failed on every push since phase two, because tracing configuration resolved credentials at import time and the test job deliberately has none. Deploy had failed since phase six on a log-streaming permission check — while the builds themselves succeeded, so every deployment all session had quietly been done by hand. And when the pipeline finally reached infrastructure apply for the first time ever, four more latent permission gaps surfaced at once, from modules written phases earlier.",
        lesson:
          "The fix for the middle one needed no new permissions at all — just writing build logs somewhere the service account already owned. Broken CI does not announce itself; it just stops being consulted.",
      },

      {
        kind: "found",
        heading: "The test suite deleted the evaluation data",
        symptom:
          "A claim verified minutes earlier came back empty when the evaluation script went looking for it.",
        chased: "Whether the verification had actually written. It had.",
        actual:
          "The offline test fixtures truncate every table after each test, by design. The offline suite and the live evaluation scripts point at the same local database. An unrelated test run wiped hours of golden-set evidence.",
        lesson:
          "Not a code bug — a data lifecycle collision, and the kind that only exists once two things that were each individually correct start sharing an environment.",
      },

      { kind: "h", text: "Two we have not solved" },
      {
        kind: "p",
        text: "Five legal claims have never advanced past triage, across four consecutive real runs including one after a fix that should have addressed it. The specialist that owns them demonstrably works — twenty-three other claims in the same category have real evidence. The stuck rows are structurally unremarkable and produce no failure log line at any run's timestamp. The only thing unique about all five is that they are the only legal claims ever produced by video ingest rather than script ingest. We do not know why.",
      },
      {
        kind: "p",
        text: "Separately, triage once assigned a priority its own unambiguous rubric maps to a different value — a plain instruction-following miss on a straightforward case. Priority assignment has no deterministic backstop, so a miss there silently changes escalation behaviour with nothing to catch it. Both are written up in full in the repository rather than closed.",
      },
    ],
  },

  // ------------------------------------------------------------- running it --
  {
    slug: "running-it",
    title: "Running it",
    summary: "What is deployed, what it costs, how it is secured, and what is not finished.",
    readingTime: "4 min",
    blocks: [
      {
        kind: "lede",
        text: "Everything here is deployed and reachable. The gaps are at the bottom of the page, stated plainly, because a system that monitors claims for staleness should not be dishonest about its own.",
      },

      { kind: "h", text: "What runs" },
      {
        kind: "p",
        text: "Seven Cloud Run services: ingest, the MCP Toolbox over Postgres, a narrow public proxy exposing three read-only tools to Parallel, the dashboard API, the webhook receiver, the re-verification worker, and a smoke service. Agent trees run on Vertex AI Agent Engine. Infrastructure is Terraform, applied through CI. Cloud SQL is the system of record, Firestore serves the dashboard's live views, BigQuery mirrors the ledger, and Secret Manager holds every credential.",
      },
      {
        kind: "p",
        text: "Every service exposes its health route at /status rather than the conventional /healthz — because the lowercase literal /healthz returned the platform's own frontend 404 above the container, while the same path with different casing or a trailing space reached the application normally, reproducibly, on unrelated services. We could not find an infrastructure explanation and renamed everywhere rather than patching one service, since external monitoring would otherwise have polled a 404 forever.",
      },

      { kind: "h", text: "Cost" },
      {
        kind: "measures",
        rows: [
          { label: "Cloud infrastructure", value: "~$28–30/mo", note: "estimate: published-price arithmetic against real resource configs, not an invoice" },
          { label: "Always-on dashboard API", value: "~$19/mo", note: "the single largest line; everything else scales to zero" },
          { label: "Per-project research cap", value: "$10", note: "hard-enforced; spend is attributed back to the claim that spent it" },
        ],
      },

      { kind: "h", text: "Security posture" },
      {
        kind: "p",
        text: "Model Armor screens extracted text, fetched web excerpts, and agent task output. The block threshold was widened after a red-team pass showed nine of ten crafted payloads passing at the original setting; the wider threshold catches five more. The remaining four are genuinely not detected — the filter returns clean, with no categories flagged — and they are enumerated by index in the test suite rather than removed from it, so the gap stays visible.",
      },
      {
        kind: "p",
        text: "Sign-in is Google Identity Services mapping an email to one of three roles. Every write endpoint enforces its role gate server-side. The research proxy that Parallel calls back through holds a bearer token and an allowlist of three read-only tools, never a cloud credential.",
      },

      {
        kind: "limits",
        heading: "Not finished, not pretending otherwise",
        items: [
          "The production webhook signing secret is a placeholder, so the re-verification tail of the loop is unproven against real deliveries.",
          "Development and demo are the same infrastructure — one project, one database, one agent runtime. 'Demo' is a row, not an environment.",
          "Remediation suggestions are generated and stored, but nothing consumes them yet.",
          "The analytics enrichment path that would call research from the warehouse was never registered; the view it would read exists and is unused.",
          "Video ingest is exercised on exactly one silent public-domain film, at 50% claim recall.",
          "Latency figures in this repository are single samples, not percentiles, and the evidence files say so where they appear.",
          "Alert policies are configured and applied but have not been observed firing — that needs sustained production traffic across each policy's evaluation window.",
        ],
      },
    ],
  },
]

export function getDocBySlug(slug: string | undefined): DocEntry | undefined {
  return DOCS.find((doc) => doc.slug === slug)
}
