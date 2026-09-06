import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { getPublicShowcaseMetrics } from "@/api/client"
import { LOOP_STAGES, LoopDiagram, LoopTrack } from "@/components/marketing/LoopDiagram"
import { Button } from "@/components/ui/button"

// Each stage carries a measured fact, not just a description. The earlier version
// of this page gave every stage 85vh of scroll to hold one short paragraph, which
// left roughly four fifths of the page as empty ground; the fix was to put
// something in the space rather than to keep the space and animate it.
const STAGE_DETAIL: { body: string; proof: string }[] = [
  {
    body: "A script or a cut lands in Cloud Storage and ingest fires on its own. Gemini reads every page and every frame and pulls out the assertions a lawyer would have to stand behind: a branded product on a shelf, a real person's name, a historical date, a needle-drop.",
    proof: "17 of 17 claims recovered from a real English script; 6 of 7 from a Hindi one.",
  },
  {
    body: "Each claim goes to one of two heads. CLEAR takes legal exposure — trademarks, real people, real places. TRUE CUT takes factual exposure — dates, statistics, events. First, though, both ask the studio's own ledger whether this exact question was already answered on a past production.",
    proof: "A prior-production hit is resolved from memory instead of researched again.",
  },
  {
    body: "Parallel's Search and Task APIs go and find out what is true right now. What comes back is never a bare verdict: it is a record with per-field reasoning, citations carrying the date they were retrieved, and a confidence score that is the minimum across fields rather than the average.",
    proof: "92% accuracy on legal claims, 88% on factual, over a hand-authored 50-claim set.",
  },
  {
    body: "Every verified claim gets a Parallel Monitor pointed at the live world. The checking cadence is a function of one variable — days until release — recomputed every morning, tightening from weekly to daily to hourly as delivery approaches.",
    proof: "$0.024 per legal claim to verify; $0.24 a day to keep watching one in release week.",
  },
  {
    body: "When something actually moves — a suit is filed, a record is corrected — a webhook fires and the claim is re-verified against the new world. Risk is rescored and Reality Drift moves. Note where the arrow returns to: verification, not ingest. The script has not changed. Only the world has.",
    proof: "Parallel only calls when it detects a real change, so a quiet monitor is a true claim.",
  },
]

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

function LiveReading() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["public-showcase-metrics"],
    queryFn: getPublicShowcaseMetrics,
  })

  const cadenceWord = data ? { "1h": "hour", "1d": "day", "1w": "week" }[data.current_cadence] : null

  let value = "—"
  if (!isLoading && !isError && data?.reality_drift != null) {
    value = `${Math.round(data.reality_drift * 100)}%`
  }

  return (
    <div className="mt-14 border-t border-border pt-6">
      <p className="max-w-[56ch] text-[0.975rem] leading-relaxed text-muted-foreground">
        Reality Drift on the live demo project reads{" "}
        <span className="font-mono text-foreground tabular-nums">{value}</span>
        {cadenceWord ? `, checked every ${cadenceWord}` : ""}. Read from the same endpoint the
        dashboard reads, when you loaded this page.{" "}
        {value === "0%"
          ? "It is zero because no monitor has yet caught a real change — not because nothing is running."
          : ""}
      </p>
    </div>
  )
}

export function LandingPage() {
  const [activeStage, registerStage] = useActiveStage(LOOP_STAGES.length)

  return (
    <div>
      <section className="mx-auto max-w-6xl px-6 pt-20 pb-24 lg:pt-32">
        <h1 className="max-w-[16ch] font-display text-[clamp(2.75rem,7vw,5.5rem)] leading-[1.02] text-foreground">
          Research that feeds itself.
        </h1>
        <p className="mt-8 max-w-[54ch] text-xl leading-relaxed text-foreground/90">
          A clearance memo is true the day it is written and quietly less true every day after.
          Ouroboros keeps re-checking a film's claims against the live world — and tightens how
          often it looks as the release date closes in.
        </p>
        <div className="mt-10 flex flex-wrap items-center gap-3">
          <Button asChild size="lg">
            <Link to="/app">Open the dashboard</Link>
          </Button>
          <Button asChild size="lg" variant="outline">
            <Link to="/docs/approach">How we approached it</Link>
          </Button>
        </div>
        <LiveReading />
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-12">
        <div className="grid gap-x-10 md:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
          <div>
            {LOOP_STAGES.map((stage, i) => (
              <div
                key={stage.key}
                ref={(el) => registerStage(el, i)}
                className="flex min-h-[56vh] flex-col justify-center py-10"
              >
                <h2 className="font-display text-[2rem] leading-tight text-foreground">
                  {stage.name}
                </h2>
                <p className="mt-4 text-[1.0625rem] leading-[1.72] text-foreground/90">
                  {STAGE_DETAIL[i].body}
                </p>
                <p className="mt-5 border-t border-border pt-4 text-sm text-muted-foreground">
                  {STAGE_DETAIL[i].proof}
                </p>
              </div>
            ))}
          </div>

          {/* The diagram is the page's instrument: it tracks the reader and it is
              also the real architecture figure, reused verbatim in the docs. */}
          <div className="sticky top-24 hidden h-fit items-center md:flex">
            <LoopDiagram activeStage={activeStage} className="w-full" />
          </div>
        </div>

        <div className="mt-6 md:hidden">
          <LoopTrack activeStage={activeStage} />
        </div>
      </section>

      <section className="border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-20 lg:py-28">
          <h2 className="max-w-[20ch] font-display text-[clamp(2rem,4vw,3rem)] leading-tight text-foreground">
            Everything below was measured, not projected.
          </h2>
          <dl className="mt-12 border-t border-border">
            {[
              ["Legal claim accuracy", "92%", "23 of 25 on a hand-authored golden set; bar was 85%"],
              ["Factual claim accuracy", "88%", "22 of 25, across 14 jurisdictions and 3 languages"],
              ["Cost to verify a legal claim", "$0.024", "a full 62-claim CLEAR pass came to $1.54"],
              ["Full script, end to end", "~$2.30", "part-estimated — real rates, assumed claim mix"],
              ["Claims carrying real evidence", "96.8%", "60 of 62 on the demo project; bar was 95%"],
            ].map(([label, value, note]) => (
              <div
                key={label}
                className="flex items-baseline justify-between gap-x-8 border-b border-border py-5"
              >
                <div className="min-w-0">
                  <dt className="text-[1.0625rem] text-foreground">{label}</dt>
                  <p className="mt-1 max-w-[52ch] text-sm leading-relaxed text-muted-foreground">
                    {note}
                  </p>
                </div>
                <dd className="shrink-0 font-mono text-xl text-[var(--brand)] tabular-nums">
                  {value}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-8 max-w-[62ch] text-sm leading-relaxed text-muted-foreground">
            A second run of the same set on the same day scored 88% legal and 96% factual — which
            domain clears the bar flips between runs. Two of the six services have known open bugs,
            and the re-verification tail of the loop has never run against a real signed webhook.
            All of it is written down in the docs.
          </p>
        </div>
      </section>

      <section className="border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-20 lg:py-28">
          <h2 className="max-w-[18ch] font-display text-[clamp(2rem,4vw,3rem)] leading-tight text-foreground">
            One loop. Every claim. Until release.
          </h2>
          <p className="mt-6 max-w-[56ch] text-[1.0625rem] leading-relaxed text-foreground/90">
            Built on Gemini, the Agent Development Kit, Parallel's Search, Task and Monitor APIs, and
            Google Cloud. The source, the infrastructure, the evidence files and the decision log are
            all public.
          </p>
          <div className="mt-10 flex flex-wrap items-center gap-3">
            <Button asChild size="lg">
              <Link to="/app">Open the dashboard</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link to="/docs">Read the docs</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}
