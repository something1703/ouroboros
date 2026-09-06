import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { getPublicShowcaseMetrics } from "@/api/client"
import { CoilSpiral } from "@/components/marketing/CoilSpiral"
import { Button } from "@/components/ui/button"

interface Stage {
  label: string
  title: string
  body: string
}

const STAGES: Stage[] = [
  {
    label: "01 — Ingest",
    title: "Script and cut come in.",
    body: "A script upload, a cut upload, or both, land in Cloud Storage and trigger ingest automatically. Gemini reads the whole thing — every page, every frame — and pulls out every claim that could become a liability: a branded product on a shelf, a real person's name, a historical date, a needle-drop.",
  },
  {
    label: "02 — Triage",
    title: "Legal or factual, decided instantly.",
    body: "Every claim splits into one of two heads: CLEAR handles legal exposure — trademarks, real people, real places. TRUE CUT handles factual exposure — dates, statistics, events. Before either head does any real work, Ouroboros checks its own ledger: has a near-identical claim already been cleared on a past production?",
  },
  {
    label: "03 — Verify",
    title: "Real evidence, not a guess.",
    body: "Parallel's Search and Task APIs go find out what's actually true right now — who owns the mark, what the record actually says, whether the claim holds up under scrutiny — and every field comes back with citations and a confidence score attached, not a bare verdict.",
  },
  {
    label: "04 — Monitor",
    title: "It doesn't stop watching.",
    body: "A Parallel Monitor attaches to every verified claim and keeps checking it against the live world, on a cadence that tightens as release gets closer — weekly, then daily, then hourly. Most tools check once. This one keeps checking.",
  },
  {
    label: "05 — Re-verify",
    title: "Drift, caught before release.",
    body: "The moment something changes — a lawsuit, a correction, a new fact on the record — a webhook fires, the claim is re-verified, and risk is recalculated. The loop closes back into stage three. Reality Drift is the one number that says how much has changed since anyone last looked.",
  },
]

// IntersectionObserver's intersectionRatio compares visible area to each element's
// OWN total area -- unreliable here since these stage sections are taller than the
// viewport (a fully-centered tall section can still show a low ratio). Proximity to
// a fixed reference line is robust regardless of section height.
function useActiveStage(count: number): [number, (el: HTMLElement | null, i: number) => void] {
  const [active, setActive] = useState(0)
  const elements = useRef<(HTMLElement | null)[]>(Array.from({ length: count }, () => null))

  useEffect(() => {
    let ticking = false
    function evaluate() {
      ticking = false
      const targetY = window.innerHeight * 0.4
      let bestIndex = 0
      let bestDistance = Infinity
      elements.current.forEach((el, i) => {
        if (!el) return
        const distance = Math.abs(el.getBoundingClientRect().top - targetY)
        if (distance < bestDistance) {
          bestDistance = distance
          bestIndex = i
        }
      })
      setActive(bestIndex)
    }
    function onScroll() {
      if (ticking) return
      ticking = true
      requestAnimationFrame(evaluate)
    }
    evaluate()
    window.addEventListener("scroll", onScroll, { passive: true })
    window.addEventListener("resize", onScroll)
    return () => {
      window.removeEventListener("scroll", onScroll)
      window.removeEventListener("resize", onScroll)
    }
  }, [])

  const register = (el: HTMLElement | null, i: number) => {
    elements.current[i] = el
  }

  return [active, register]
}

function LiveProof() {
  const { data, isLoading } = useQuery({
    queryKey: ["public-showcase-metrics"],
    queryFn: getPublicShowcaseMetrics,
  })

  const cadenceWord = data ? { "1h": "hour", "1d": "day", "1w": "week" }[data.current_cadence] : null
  const driftText =
    isLoading || data?.reality_drift == null ? "—" : `${Math.round(data.reality_drift * 100)}%`

  return (
    <section className="border-y border-border bg-card px-6 py-20">
      <div className="mx-auto max-w-2xl text-center">
        <p className="font-display text-2xl text-foreground sm:text-3xl">
          Right now, on the live demo project, Reality Drift sits at{" "}
          <span className="font-mono text-primary">{driftText}</span>
          {cadenceWord ? ` — checked every ${cadenceWord}.` : "."}
        </p>
        <p className="mx-auto mt-4 max-w-md text-sm text-muted-foreground">
          Not a screenshot. That number comes from the same API the dashboard reads,
          on the same project that's been running the whole time.
        </p>
      </div>
    </section>
  )
}

export function LandingPage() {
  const [activeStage, registerStage] = useActiveStage(STAGES.length)
  const turns = 1 + (activeStage / (STAGES.length - 1)) * 3

  return (
    <div>
      <section className="flex min-h-[90vh] flex-col items-center justify-center gap-8 px-6 py-20 text-center">
        <div className="relative flex items-center justify-center">
          <CoilSpiral turns={1} size={340} strokeWidth={5} />
        </div>
        <div className="max-w-2xl space-y-4">
          <h1 className="font-display text-5xl text-foreground sm:text-6xl">
            Research that feeds itself.
          </h1>
          <p className="text-lg text-muted-foreground">
            Ouroboros keeps checking your script and your cut against the live world —
            long after everyone else stopped looking.
          </p>
        </div>
        <p className="text-xs text-muted-foreground">Scroll to see how the loop works ↓</p>
      </section>

      <section className="relative mx-auto max-w-5xl px-6 py-10">
        <div className="grid gap-16 md:grid-cols-[minmax(0,1fr)_340px]">
          <div className="py-20">
            {/* No per-stage "active" text treatment -- an earlier version dimmed
                inactive stages' opacity, which pushed already-muted body text well
                under WCAG AA contrast (found live via Lighthouse), and a border-left
                accent was the next instinct but that's an explicit craft-floor ban.
                The coil alone carries progress; every stage's prose stays uniformly
                legible whether it's the one currently in view or not. */}
            {STAGES.map((stage, i) => (
              <div
                key={stage.label}
                ref={(el) => registerStage(el, i)}
                className="flex min-h-[85vh] flex-col justify-center space-y-3"
              >
                <h2 className="font-display text-3xl text-foreground">{stage.title}</h2>
                <p className="max-w-md text-muted-foreground">{stage.body}</p>
              </div>
            ))}
          </div>

          <div className="sticky top-24 hidden h-fit items-center justify-center md:flex">
            <CoilSpiral turns={turns} size={300} strokeWidth={4} />
          </div>
        </div>
      </section>

      <LiveProof />

      <section className="px-6 py-24 text-center">
        <h2 className="font-display text-3xl text-foreground">
          One loop. Every claim. Until release.
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-muted-foreground">
          Built on Gemini, Parallel's Search/Task/Monitor APIs, and Google Cloud —
          the real system, not a demo shell.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button asChild size="lg">
            <Link to="/app">Open the dashboard</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link to="/docs">Read the docs</Link>
          </Button>
        </div>
      </section>
    </div>
  )
}
