import { Link } from "react-router-dom"
import { CoilSpiral } from "@/components/marketing/CoilSpiral"
import { Button } from "@/components/ui/button"

interface Stage {
  label: string
  title: string
  body: string
  stack: string
}

const STAGES: Stage[] = [
  {
    label: "01 — Ingest",
    title: "Script and cut come in.",
    body: "A script (PDF) and a cut (video) upload to Cloud Storage, either through the dashboard or directly. That upload triggers ingest through Eventarc, and a Cloud Run service reads the file with Gemini's document and video understanding — every page of the script, every frame of the cut — extracting claims: a branded product, a real person's name, a historical date, a needle-drop, a location.",
    stack: "Cloud Storage → Eventarc → Cloud Run → Gemini (document + video understanding)",
  },
  {
    label: "02 — Triage",
    title: "Legal or factual, decided instantly.",
    body: "Every extracted claim is classified into one of two heads. CLEAR handles legal exposure — trademarks, real people, real places, music rights. TRUE CUT handles factual exposure — dates, statistics, named events. Before either head runs a real verification pass, a triage agent checks the studio's own ledger for a near-identical claim already resolved on a past production — the same rights holder, the same brand, the same city — so the same question never gets answered from scratch twice.",
    stack: "ADK agents on Vertex Agent Engine · Postgres ledger (`get_prior_decisions`)",
  },
  {
    label: "03 — Verify",
    title: "Real evidence, not a guess.",
    body: "For a claim that needs real research, Parallel's Search API and Task API go find out what's actually true: who owns a mark, what the public record says, whether a historical claim holds up. Every field in the result — not just an overall verdict — comes back with its own citations and confidence score, and low-confidence results escalate automatically to a stronger processor.",
    stack: "Parallel Search API, Task API (core/pro processors), Basis (per-field citations + confidence)",
  },
  {
    label: "04 — Monitor",
    title: "It doesn't stop watching.",
    body: "Once a claim is verified, a Parallel Monitor attaches to it and keeps checking it against the live web on its own schedule. That schedule tightens automatically as the release date approaches — weekly at first, then daily, then hourly in the final week — the coil winding tighter exactly when the cost of missing a change is highest.",
    stack: "Parallel Monitor API · Cloud Scheduler tightens cadence daily as release nears",
  },
  {
    label: "05 — Re-verify",
    title: "Drift, caught before release.",
    body: "When a Monitor detects a real change, it fires a webhook. That webhook lands on Pub/Sub, a Cloud Run worker re-verifies the claim, recalculates its risk, and updates the project's Reality Drift — a single number weighted by how much of the project's risk picture actually changed recently. The loop closes back into verification, and the project keeps re-checking itself all the way to release — and, deliberately, past it.",
    stack: "Webhook → Pub/Sub → Cloud Run reverify worker → Firestore/Postgres ledger",
  },
]

export function HowItWorksPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <div className="mb-16 flex flex-col items-center gap-6 text-center">
        <CoilSpiral turns={2.5} size={220} strokeWidth={4} />
        <h1 className="font-display text-4xl text-foreground">How Ouroboros works</h1>
        <p className="max-w-xl text-muted-foreground">
          Five real stages, running on a real deployed system — Gemini, Parallel, and
          Google Cloud, not a demo shell.
        </p>
      </div>

      <div className="space-y-16">
        {STAGES.map((stage) => (
          <div key={stage.label} className="space-y-2 border-t border-border pt-8">
            <h2 className="font-display text-2xl text-foreground">{stage.title}</h2>
            <p className="max-w-2xl text-muted-foreground">{stage.body}</p>
            <p className="font-mono text-xs text-muted-foreground">{stage.stack}</p>
          </div>
        ))}
      </div>

      <div className="mt-20 flex flex-col items-center gap-4 border-t border-border pt-12 text-center">
        <h2 className="font-display text-2xl text-foreground">Want the technical detail?</h2>
        <div className="flex flex-wrap justify-center gap-3">
          <Button asChild>
            <Link to="/docs">Read the docs</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/app">Open the dashboard</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
