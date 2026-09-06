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

  return (
    <div className="relative flex size-40 shrink-0 items-center justify-center sm:size-56">
      <svg viewBox="0 0 220 220" className="size-full -rotate-90" aria-hidden>
        <circle cx="110" cy="110" r={radius} fill="none" stroke="var(--border)" strokeWidth="26" />
        {/* Only drawn when there is a non-zero arc to draw. A zero-length dash with
            a round linecap renders as a full-width dot, so a project at 0% drift
            was displaying roughly 4% of a ring — the one number that must not lie. */}
        {known && pct > 0 ? (
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
          {known ? `${Math.round(pct * 100)}%` : "—"}
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

  return (
    <header className="flex flex-wrap items-center gap-x-10 gap-y-6 border-b border-border bg-card px-6 py-8">
      <DriftRing value={metrics.reality_drift} />
      <div className="min-w-0 flex-1">
        <h1 className="font-display text-3xl text-foreground sm:text-4xl">{title}</h1>
        <div className="mt-6 flex flex-wrap items-baseline gap-x-10 gap-y-4">
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
    </header>
  )
}
