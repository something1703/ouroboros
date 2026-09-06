import { Badge } from "@/components/ui/badge"
import type { Cadence, MetricsResponse } from "@/api/types"

// Reality Drift is the page's one hero instrument (direction contract:
// .impeccable/surfaces/web-src-pages-projectdetailpage-tsx.md) -- a thick-stroke ring
// at true scale, echoing the logo mark's own nearly-closed circular stroke, not a
// small topbar gauge competing for attention with everything else.
function DriftRing({ value }: { value: number }) {
  const radius = 88
  const circumference = 2 * Math.PI * radius
  const pct = Math.max(0, Math.min(1, value))
  const dash = circumference * pct

  return (
    <div className="relative flex size-56 shrink-0 items-center justify-center">
      <svg viewBox="0 0 220 220" className="size-56 -rotate-90">
        <circle cx="110" cy="110" r={radius} fill="none" stroke="var(--border)" strokeWidth="26" />
        <circle
          cx="110"
          cy="110"
          r={radius}
          fill="none"
          stroke="var(--brand)"
          strokeWidth="26"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
          className="transition-[stroke-dasharray] duration-700 ease-out"
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="font-mono text-5xl font-medium text-foreground">
          {Math.round(pct * 100)}%
        </span>
        <span className="mt-1 text-[0.65rem] tracking-[0.2em] text-muted-foreground uppercase">
          Reality Drift
        </span>
      </div>
    </div>
  )
}

function cadenceLabel(cadence: Cadence): string {
  return { "1h": "hourly", "1d": "daily", "1w": "weekly" }[cadence]
}

function Instrument({ label, value }: { label: string; value: string }) {
  return (
    <div className="px-5 text-center first:pl-0 last:pr-0">
      <p className="font-mono text-lg text-foreground">{value}</p>
      <p className="mt-0.5 text-[0.7rem] tracking-wide text-muted-foreground uppercase">{label}</p>
    </div>
  )
}

export function DriftHero({ title, metrics }: { title: string; metrics: MetricsResponse }) {
  const spend = metrics.spend_usd != null ? `$${metrics.spend_usd.toFixed(2)}` : "$0.00"
  const daysLabel = metrics.days_to_release >= 999 ? "—" : `${metrics.days_to_release}d`
  const drift7d = metrics.drift_7d != null ? `${Math.round(metrics.drift_7d * 100)}%` : "—"

  return (
    <header className="flex flex-col items-center gap-6 border-b border-border bg-card px-6 py-10">
      <h1 className="font-display text-2xl text-foreground">{title}</h1>
      <DriftRing value={metrics.reality_drift ?? 0} />
      <div className="flex items-center divide-x divide-border">
        <Instrument label="7-day" value={drift7d} />
        <Instrument label="Spend" value={spend} />
        <Instrument label="To release" value={daysLabel} />
        <div className="px-5 text-center last:pr-0">
          <Badge
            variant="outline"
            className="font-mono uppercase"
            title="Monitor cadence — the coil"
          >
            {metrics.current_cadence} · {cadenceLabel(metrics.current_cadence)}
          </Badge>
        </div>
      </div>
    </header>
  )
}
