// Real content, written for this site -- not copy-pasted from the internal
// engineering docs (ARCHITECTURE.md, DATA_MODEL.md, PARALLEL_INTEGRATION.md), but
// faithful to them. No invented capabilities, numbers, or claims.

export interface DocSection {
  heading: string
  body: string[]
}

export interface DocEntry {
  slug: string
  title: string
  summary: string
  sections: DocSection[]
}

export const DOCS: DocEntry[] = [
  {
    slug: "architecture",
    title: "Architecture overview",
    summary: "How ingest, verification, and monitoring fit together as one loop.",
    sections: [
      {
        heading: "The one-paragraph model",
        body: [
          "Ouroboros treats a film as a set of claims about the real world. A screenplay makes legal claims — this brand, this song, this real person, this location can be shown. A rough cut makes factual claims — this event happened, this figure is correct, this footage is what it says it is.",
          "Every claim is extracted by Gemini into a claim ledger, verified by ADK agents using Parallel's research APIs into an evidence record with citations and confidence, scored for risk, and then watched by Parallel Monitors so that any change in the world triggers re-verification. Outputs feed inputs — the loop is the product.",
        ],
      },
      {
        heading: "Ingest",
        body: [
          "A script or cut lands in Cloud Storage, which triggers Eventarc, which invokes a Cloud Run ingest service. Gemini's document understanding reads the script page by page; Gemini's video understanding reads the cut frame by frame and transcribes dialogue. Every extracted claim carries its exact source — a page and scene for a script claim, a timestamp and channel (dialogue, on-screen text, visual) for a video claim.",
          "Every piece of extracted text passes through Model Armor before it ever reaches a model context, and again for every web excerpt fetched later in the loop.",
        ],
      },
      {
        heading: "Orchestration",
        body: [
          "A coordinator agent routes each asset to one of two heads, both built on Google's Agent Development Kit and deployed on Vertex AI Agent Engine. CLEAR handles legal exposure: music, brand, person, location, artwork, quote. TRUE CUT handles factual exposure: events, statistics, attribution, archival provenance, identity claims.",
          "Before either head does real verification work, a triage step checks the studio's own claim ledger for a near-identical claim already resolved on a past production, so the same question is never re-answered from scratch.",
        ],
      },
      {
        heading: "The claim ledger",
        body: [
          "Cloud SQL (Postgres) is the system of record for projects, assets, claims, evidence, verification history, and monitors. Firestore holds denormalized live views the dashboard reads directly — per-project status, the event feed, and the Reality Drift metric. A nightly and streaming mirror into BigQuery supports analytics and enrichment.",
        ],
      },
      {
        heading: "Monitoring and re-verification",
        body: [
          "Every verified claim gets a Parallel Monitor, checking it against the live web on a cadence that tightens automatically as the release date approaches — weekly, then daily, then hourly. When a Monitor detects a real change, it fires a webhook; a Cloud Run worker re-verifies the claim, recalculates risk, and updates the project's Reality Drift score. The loop closes back into verification.",
        ],
      },
    ],
  },
  {
    slug: "data-model",
    title: "Data model",
    summary: "Claims, evidence, risk, and the audit trail that connects them.",
    sections: [
      {
        heading: "Claim",
        body: [
          "The core unit: an entity (a brand, a person, a date, an event) plus a one-sentence claim about it, plus exactly where it came from (a script page and scene, or a cut's timestamp and channel). Claims carry jurisdiction (which shooting or distribution territories they apply in), a priority, and a verification status that moves from pending through triaged, verifying, verified, escalated, or stale.",
        ],
      },
      {
        heading: "Evidence",
        body: [
          "One evidence record per verification cycle. Evidence is never a bare verdict — it's a set of per-field results (a Basis), each with its own reasoning, its own citations with retrieval dates, and its own confidence score. The claim's overall confidence is the minimum across its required fields, not an average — one weak field can't be hidden behind three strong ones.",
        ],
      },
      {
        heading: "Risk",
        body: [
          "A claim's current risk level (none, low, medium, high, or blocking) plus a numeric score, a rationale, and — where relevant — a suggested remediation (replace the brand, replace the music, reshoot, recut, or obtain a release). Risk history is kept separately from current risk, so a project can show both where it stands and how it got there.",
        ],
      },
      {
        heading: "Reality Drift",
        body: [
          "A single project-wide number: the fraction of claims whose latest verification cycle changed something versus the previous cycle, weighted by risk level (a blocking claim that changed counts far more than a none-risk claim that didn't). It answers one question — how much of this project's risk picture has moved lately — and it's the number the dashboard leads with.",
        ],
      },
      {
        heading: "Verification history",
        body: [
          "An append-only audit trail: every status change, every risk override, every automated re-verification, each with an actor (ingest, an agent, a monitor, the re-verify worker, or a human), a timestamp, and a note. A human override always requires a note and always shows up here, permanently.",
        ],
      },
    ],
  },
  {
    slug: "parallel-integration",
    title: "Parallel integration",
    summary: "Search, Task, and Monitor — how Ouroboros actually uses Parallel.",
    sections: [
      {
        heading: "Search API",
        body: [
          "Used for straightforward lookups where a handful of good sources settle the question — is this trademark active, does this event show up in the historical record. Fast, cheap, and the default first pass for most claims.",
        ],
      },
      {
        heading: "Task API",
        body: [
          "Used when a claim needs deeper research than a search pass can give — deliberately escalated when confidence comes back low, or used directly for categories that are usually contested (rights holders, disputed historical claims). Task runs return per-field Basis output: reasoning, citations, and confidence for each field independently, at either a core-fast or a pro processor tier depending on how much the claim is worth getting exactly right.",
        ],
      },
      {
        heading: "Monitor API",
        body: [
          "The mechanism behind the whole re-verification loop. A Monitor is created per verified claim and configured with a query and a checking frequency (1w / 1d / 1h) that Ouroboros tightens automatically as the project's release date approaches. Parallel only sends a webhook when it detects an actual material change — not on every scheduled check — so a quiet Monitor is a claim that's still true, not a Monitor that isn't working.",
        ],
      },
      {
        heading: "Cost discipline",
        body: [
          "Every Parallel call is metered against a per-project budget cap. Cheaper processors and Search are preferred by default; escalation to Task or a stronger processor happens only when confidence genuinely warrants the extra cost, and every dollar spent is attributed back to the claim that spent it.",
        ],
      },
    ],
  },
  {
    slug: "stack-and-deployment",
    title: "Stack & deployment",
    summary: "What actually runs, and where.",
    sections: [
      {
        heading: "Runtime",
        body: [
          "Every service — ingest, the dashboard API, the webhook receiver, the re-verify worker — runs on Cloud Run. Orchestration (the CLEAR and TRUE CUT agent heads) runs on Vertex AI Agent Engine. Infrastructure is defined in Terraform and deployed through a CI/CD pipeline that builds, tests, and applies on every merge.",
        ],
      },
      {
        heading: "Data stores",
        body: [
          "Cloud SQL (Postgres) is the system of record. Firestore serves the dashboard's live views. BigQuery mirrors the ledger for analytics. Secret Manager holds every credential — the Parallel API key, the webhook signing secret, database passwords — none of it in source control.",
        ],
      },
      {
        heading: "Auth",
        body: [
          "The dashboard uses Google Identity Services sign-in, mapping each signed-in email to one of three roles (legal, editorial, producer) via a small, explicit allowlist. Every write endpoint enforces its role gate server-side — never only in the UI.",
        ],
      },
      {
        heading: "The repo",
        body: [
          "The full source, infrastructure, and run instructions are public.",
        ],
      },
    ],
  },
]

export function getDocBySlug(slug: string | undefined): DocEntry | undefined {
  return DOCS.find((doc) => doc.slug === slug)
}
