import { Link } from "react-router-dom"
import { LoopDiagram, LoopTrack } from "@/components/marketing/LoopDiagram"
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
    <div className="mx-auto max-w-4xl px-6 py-16 lg:py-24">
      <h1 className="font-display text-4xl text-foreground sm:text-5xl">How Ouroboros works</h1>
      <p className="mt-4 max-w-[56ch] text-lg leading-relaxed text-foreground/90">
        Five stages on a real deployed system. Ingest and triage run once per asset; verify, watch
        and drift are the cycle that repeats until the film is delivered.
      </p>

      <figure className="my-14">
        <LoopDiagram className="hidden w-full md:block" />
        <div className="md:hidden">
          <LoopTrack />
        </div>
      </figure>

      <div>
        {STAGES.map((stage) => (
          <section key={stage.label} className="border-t border-border py-10">
            <h2 className="font-display text-[1.75rem] leading-tight text-foreground">
              {stage.title}
            </h2>
            <p className="mt-4 max-w-[68ch] text-[1.0625rem] leading-[1.72] text-foreground/90">
              {stage.body}
            </p>
            <p className="mt-5 max-w-[68ch] font-mono text-sm text-muted-foreground">
              {stage.stack}
            </p>
          </section>
        ))}
      </div>

      <div className="mt-14 border-t border-border pt-12">
        <h2 className="font-display text-[1.75rem] text-foreground">Want the technical detail?</h2>
        <p className="mt-3 max-w-[56ch] text-[1.0625rem] leading-relaxed text-muted-foreground">
          The docs cover how we framed the problem, what we turned down, what it measurably does,
          and what is still broken.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link to="/docs/approach">Read the docs</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link to="/app">Open the dashboard</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
