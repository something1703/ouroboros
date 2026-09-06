import { useId, useState } from "react"

// The one interactive figure on the site. It runs the real policy, not an
// illustration of it: the thresholds below are `config/parallel.py::frequency_for`
// verbatim (>60 days -> 1w, >7 -> 1d, else 1h), and the per-check price is the
// `monitor.base` SKU from `PRICE_TABLE_USD`, hard-coded there from Parallel's
// published pricing. Drag the release date and the arithmetic is the arithmetic
// the scheduler actually does every morning at 06:00 IST.

const PRICE_PER_CHECK_USD = 0.01

type Frequency = "1w" | "1d" | "1h"

function frequencyFor(daysToRelease: number): Frequency {
  if (daysToRelease > 60) return "1w"
  if (daysToRelease > 7) return "1d"
  return "1h"
}

const BANDS: { freq: Frequency; label: string; range: string; checksPerDay: number }[] = [
  { freq: "1w", label: "Weekly", range: "more than 60 days out", checksPerDay: 1 / 7 },
  { freq: "1d", label: "Daily", range: "8 to 60 days out", checksPerDay: 1 },
  { freq: "1h", label: "Hourly", range: "the last 7 days", checksPerDay: 24 },
]

const MAX_DAYS = 180

export function CadenceDial() {
  const [days, setDays] = useState(90)
  const sliderId = useId()
  const freq = frequencyFor(days)
  const band = BANDS.find((b) => b.freq === freq)!
  const perDay = band.checksPerDay * PRICE_PER_CHECK_USD

  // One tick per check in the next 24 hours — the coil tightening, drawn at true
  // scale rather than described. Weekly gets a single ghosted tick, because a
  // seventh of a check is not a thing you can draw honestly.
  const tickCount = freq === "1w" ? 1 : Math.round(band.checksPerDay)

  return (
    <figure className="my-12 border-y border-border py-8">
      <div className="flex flex-wrap items-baseline justify-between gap-x-8 gap-y-2">
        <label htmlFor={sliderId} className="text-sm text-foreground">
          Days until release
        </label>
        <p className="font-mono text-sm text-muted-foreground">
          <span className="text-foreground">{days === MAX_DAYS ? "180+" : days}</span> days →{" "}
          <span className="text-[var(--brand)]">{freq}</span> → {tickCount === 1 && freq === "1w" ? "0.14" : tickCount}{" "}
          checks/day → ${perDay.toFixed(3)}/day per claim
        </p>
      </div>

      <input
        id={sliderId}
        type="range"
        min={0}
        max={MAX_DAYS}
        value={MAX_DAYS - days}
        onChange={(e) => setDays(MAX_DAYS - Number(e.target.value))}
        className="mt-5 w-full accent-[var(--brand)]"
        aria-describedby={`${sliderId}-desc`}
      />
      <p id={`${sliderId}-desc`} className="sr-only">
        Drag toward the right to move the release date closer. The monitoring cadence tightens from
        weekly to daily to hourly.
      </p>

      <div className="mt-6 grid gap-px overflow-hidden rounded-md bg-border sm:grid-cols-3">
        {BANDS.map((b) => {
          const on = b.freq === freq
          return (
            <div
              key={b.freq}
              className="bg-background px-4 py-3 transition-colors duration-300"
              style={on ? { background: "color-mix(in srgb, var(--brand) 12%, var(--background))" } : undefined}
            >
              <p
                className="text-sm transition-colors duration-300"
                style={{ color: on ? "var(--brand)" : "var(--muted-foreground)" }}
              >
                {b.label}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">{b.range}</p>
            </div>
          )
        })}
      </div>

      <div className="mt-6 flex h-12 items-end gap-[3px]" aria-hidden>
        {Array.from({ length: tickCount }, (_, i) => (
          <span
            key={i}
            className="flex-1 rounded-full transition-all duration-500"
            style={{
              background: "var(--brand)",
              height: freq === "1h" ? "100%" : freq === "1d" ? "58%" : "26%",
              opacity: freq === "1w" ? 0.4 : 1,
              maxWidth: tickCount === 1 ? "64px" : undefined,
            }}
          />
        ))}
      </div>

      <figcaption className="mt-5 text-sm text-muted-foreground">
        A claim on a film 90 days out is checked once a day for about a cent. The same claim in
        release week is checked every hour, and costs about a quarter a day. Nothing about the claim
        changed — only how much it would cost to be wrong about it.
      </figcaption>
    </figure>
  )
}
