import type { Cadence, MetricsResponse } from "@/api/types"

// Reality Drift is the page's one hero instrument -- a thick-stroke ring at true
// scale, echoing the mark's own closed circular stroke, not a small topbar gauge.
//
// The hero reads left-to-right rather than stacked-and-centred: centred, it spent
// ~430px of height and left roughly two thirds of its own width empty, which
// pushed the ranked worklist (the actual point of the page) below the fold on a
// laptop. Same instrument, same scale, beside its numbers instead of above them.
function DriftRing({ value }: { value: number | null }) {
  const radius = 88
  const circumference = 2 * Math.PI * radius
  const known = value != null
  const pct = known ? Math.max(0, Math.min(1, value)) : 0
  const displayPct = Math.round(pct * 100)

  return (
    <div className="relative flex size-40 shrink-0 items-center justify-center sm:size-56">
      <svg viewBox="0 0 220 220" className="size-full -rotate-90" aria-hidden>
        <circle cx="110" cy="110" r={radius} fill="none" stroke="var(--border)" strokeWidth="26" />
        {/* Gated on the *displayed*, rounded percentage, not the raw value. Found
            live: a real project with a genuinely tiny (< 0.5%) but non-zero drift
            rendered "0%" as its label while a round-linecap arc that short — any
            arc shorter than its own stroke width -- painted as a solid dot at 12
            o'clock, exactly the misleading blob this guard exists to prevent. If
            it reads as 0% in text, it must read as 0% in the ring too. */}
        {known && displayPct > 0 ? (
          <circle
            cx="110"
            cy="110"
            r={radius}
            fill="none"
            stroke="var(--brand)"
            strokeWidth="26"
            strokeLinecap="round"
            strokeDasharray={`${circumference * pct} ${circumference}`}
            className="transition-[stroke-dasharray] duration-700 ease-out"
          />
        ) : null}
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="font-mono text-4xl font-medium text-foreground tabular-nums sm:text-5xl">
          {known ? `${displayPct}%` : "—"}
        </span>
        <span className="mt-1 text-sm text-muted-foreground">
          {known ? "Reality Drift" : "Not measured"}
        </span>
      </div>
    </div>
  )
}

const CADENCE_LABEL: Record<Cadence, string> = { "1h": "Hourly", "1d": "Daily", "1w": "Weekly" }

function Instrument({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-mono text-xl text-foreground tabular-nums">{value}</p>
      <p className="mt-0.5 text-sm text-muted-foreground">{label}</p>
    </div>
  )
}

export function DriftHero({ title, metrics }: { title: string; metrics: MetricsResponse }) {
  const spend = metrics.spend_usd != null ? `$${metrics.spend_usd.toFixed(2)}` : "$0.00"
  const daysLabel = metrics.days_to_release >= 999 ? "—" : `${metrics.days_to_release}d`
  const drift7d = metrics.drift_7d != null ? `${Math.round(metrics.drift_7d * 100)}%` : "—"

  // Matches DriftRing's own rounding exactly (Math.round(pct * 100)), not a strict
  // === 0 -- found live: a real project showed the ring at a genuinely-rendered
  // "0%" (a tiny non-zero value rounds down the same way) while this stricter
  // check silently failed to fire, leaving the one number that most needs
  // explaining without one. Whatever the ring displays as 0%, this explains.
  const driftZero =
    metrics.reality_drift != null && Math.round(Math.max(0, metrics.reality_drift) * 100) === 0

  return (
    <header className="border-b border-border bg-card px-6 py-6 sm:py-8">
      <div className="flex flex-wrap items-center gap-x-10 gap-y-6">
        <DriftRing value={metrics.reality_drift} />
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-2xl text-foreground sm:text-4xl">{title}</h1>
          {/* A single vertical stack of 4 instruments cost ~500px of mobile height
              on its own, before any tab content -- one claim was visible before the
              fold. 2-up on mobile, the original single row from sm and up. */}
          <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:mt-6 sm:flex sm:flex-wrap sm:items-baseline sm:gap-x-10 sm:gap-y-4">
            <Instrument label="Drift, 7 days" value={drift7d} />
            <Instrument label="Spend" value={spend} />
            <Instrument label="To release" value={daysLabel} />
            <div>
              {/* Mono carries the cadence code, which is a measurement. The word
                  describing it is body sans in title case, per the same rule. */}
              <p className="text-xl text-foreground">
                <span className="font-mono">{metrics.current_cadence}</span>{" "}
                <span className="text-muted-foreground">
                  {CADENCE_LABEL[metrics.current_cadence]}
                </span>
              </p>
              <p className="mt-0.5 text-sm text-muted-foreground">Monitor cadence</p>
            </div>
          </div>
        </div>
      </div>
      {/* A bare "0%" reads as broken to anyone who hasn't read the docs -- the one
          instrument on the page that must never look like it's lying about itself.
          Only shown for a genuinely zero, measured reading (not the "—" unmeasured
          state, which already says so via DriftRing itself). Full explanation from
          sm up; a one-line version on mobile, where every extra line here is a line
          the worklist -- this page's actual point -- loses on first paint. */}
      {driftZero && (
        <>
          <p className="mt-4 text-sm text-muted-foreground sm:hidden">
            No monitor has caught a real change yet — not because nothing is running.
          </p>
          <p className="mt-6 hidden max-w-[62ch] text-sm text-muted-foreground sm:block">
            Zero because no monitor has caught a real change yet on this project — not because
            nothing is running. Every verified claim has a Parallel Monitor watching it live; a
            quiet monitor is a claim that's still true.
          </p>
        </>
      )}
    </header>
  )
}
