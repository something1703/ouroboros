import { Badge } from "@/components/ui/badge"
import type { Cadence, MetricsResponse } from "@/api/types"

// A thick-stroke ring gauge echoing the logo mark's own visual language (a nearly-
// closed circular stroke) rather than a generic progress bar.
function DriftGauge({ value }: { value: number }) {
  const radius = 20
  const circumference = 2 * Math.PI * radius
  const pct = Math.max(0, Math.min(1, value))
  const dash = circumference * pct

  return (
    <div className="relative flex size-12 shrink-0 items-center justify-center">
      <svg viewBox="0 0 48 48" className="size-12 -rotate-90">
        <circle
          cx="24"
          cy="24"
          r={radius}
          fill="none"
          stroke="var(--border)"
          strokeWidth="5"
        />
        <circle
          cx="24"
          cy="24"
          r={radius}
          fill="none"
          stroke="var(--brand)"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
        />
      </svg>
      <span className="absolute font-mono text-[0.65rem] text-foreground">
        {Math.round(pct * 100)}%
      </span>
    </div>
  )
}

function cadenceLabel(cadence: Cadence): string {
  return { "1h": "hourly", "1d": "daily", "1w": "weekly" }[cadence]
}

export function TopBar({ title, metrics }: { title: string; metrics: MetricsResponse }) {
  const spend =
    metrics.spend_usd != null
      ? `$${metrics.spend_usd.toFixed(2)}`
      : "$0.00"
  const daysLabel =
    metrics.days_to_release >= 999 ? "no release date" : `${metrics.days_to_release}d to release`

  return (
    <header className="flex items-center gap-6 border-b border-border bg-card px-6 py-4">
      <div className="min-w-0 flex-1">
        <h1 className="truncate font-display text-xl text-foreground">{title}</h1>
      </div>

      <div className="flex items-center gap-2">
        <DriftGauge value={metrics.reality_drift ?? 0} />
        <div className="leading-tight">
          <p className="text-xs text-muted-foreground">Reality Drift</p>
          {metrics.drift_7d != null && (
            <p className="font-mono text-[0.7rem] text-muted-foreground">
              {Math.round(metrics.drift_7d * 100)}% / 7d
            </p>
          )}
        </div>
      </div>

      <div className="hidden text-sm text-muted-foreground sm:block">
        <p className="font-mono">{spend}</p>
        <p className="text-xs">spend</p>
      </div>

      <div className="hidden text-sm text-muted-foreground md:block">
        <p>{daysLabel}</p>
      </div>

      <Badge variant="outline" className="font-mono uppercase" title="Monitor cadence — the coil">
        {metrics.current_cadence} · {cadenceLabel(metrics.current_cadence)}
      </Badge>
    </header>
  )
}
