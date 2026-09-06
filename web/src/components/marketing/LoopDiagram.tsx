// The master architecture diagram. One authored SVG, used twice: as the landing
// page's scroll instrument (activeStage tracks the reader) and as the docs'
// architecture figure (activeStage undefined -> every stage lit).
//
// It replaces an earlier decorative Archimedean spiral. The spiral was an open
// curve that never closed, which quietly contradicted the product's own name and
// carried no information; this shape is a real closed circuit whose geometry is
// load-bearing. Most importantly the return path is a chord across the ring, not
// another step around it: ingest and triage happen once per asset, but
// verify -> watch -> drift -> verify is the cycle that actually repeats until
// release. Drawing that as a full lap would have been a prettier circle and a
// false diagram.

// The viewBox is wide rather than square because the radial labels, not the ring,
// set the bounding box: the two right-hand stages anchor outward from the ring and
// need room for a full machinery line without the type having to shrink.
const CX = 430
const CY = 265
const R = 165

export interface LoopStage {
  key: string
  name: string
  /** One line of the real machinery. Rendered in mono: these are identifiers. */
  machinery: string
}

export const LOOP_STAGES: LoopStage[] = [
  { key: "ingest", name: "Ingest", machinery: "GCS → Eventarc → ingest" },
  { key: "triage", name: "Triage", machinery: "ClaimTriage · Memory" },
  { key: "verify", name: "Verify", machinery: "CLEAR / TRUE CUT · Task" },
  { key: "watch", name: "Watch", machinery: "Reporter · Monitor" },
  { key: "drift", name: "Drift", machinery: "webhook → reverify" },
]

// Top, then clockwise. Five nodes at 72° spacing puts a label in each of the
// directions a label can actually be anchored cleanly.
const ANGLES = [-90, -18, 54, 126, 198]
const GAP = 10 // degrees of clear air either side of a node, so arcs never touch dots

const rad = (deg: number) => (deg * Math.PI) / 180
const at = (deg: number, radius: number) => ({
  x: CX + radius * Math.cos(rad(deg)),
  y: CY + radius * Math.sin(rad(deg)),
})

function arcBetween(fromDeg: number, toDeg: number): string {
  const a = at(fromDeg + GAP, R)
  const b = at(toDeg - GAP, R)
  return `M${a.x.toFixed(1)},${a.y.toFixed(1)} A${R},${R} 0 0 1 ${b.x.toFixed(1)},${b.y.toFixed(1)}`
}

/** Arrowhead sitting on the ring at `deg`, pointing along the clockwise tangent. */
function tangentArrow(deg: number): string {
  const p = at(deg, R)
  const t = rad(deg + 90) // clockwise tangent
  const fx = Math.cos(t)
  const fy = Math.sin(t)
  const size = 7
  const tip = { x: p.x + fx * size, y: p.y + fy * size }
  const l = { x: p.x - fx * size * 0.5 - -fy * size * 0.62, y: p.y - fy * size * 0.5 - fx * size * 0.62 }
  const r = { x: p.x - fx * size * 0.5 + -fy * size * 0.62, y: p.y - fy * size * 0.5 + fx * size * 0.62 }
  return `M${tip.x.toFixed(1)},${tip.y.toFixed(1)} L${l.x.toFixed(1)},${l.y.toFixed(1)} L${r.x.toFixed(1)},${r.y.toFixed(1)} Z`
}

// The chord: drift (198°) back into verify (54°), bowed below centre so it clears
// the middle of the ring and reads as a deliberate shortcut rather than a diameter.
const CHORD_FROM = at(198 + 26, R - 6)
const CHORD_TO = at(54 - 20, R - 6)
const CHORD = `M${CHORD_FROM.x.toFixed(1)},${CHORD_FROM.y.toFixed(1)} Q${CX - 4},${CY + 112} ${CHORD_TO.x.toFixed(1)},${CHORD_TO.y.toFixed(1)}`

function anchorFor(deg: number): "start" | "middle" | "end" {
  const c = Math.cos(rad(deg))
  if (c > 0.3) return "start"
  if (c < -0.3) return "end"
  return "middle"
}

export function LoopDiagram({
  activeStage,
  className,
}: {
  /** Index of the stage to spotlight. Undefined lights every stage equally. */
  activeStage?: number
  className?: string
}) {
  const lit = (i: number) => activeStage === undefined || activeStage === i

  return (
    <svg
      viewBox="0 0 860 560"
      className={className}
      role="img"
      aria-label="The Ouroboros loop: ingest, triage, verify, watch, drift — and back into verify."
    >
      {/* the track everything sits on */}
      <circle cx={CX} cy={CY} r={R} fill="none" stroke="var(--border)" strokeWidth={1.5} />

      {/* arcs between consecutive stages; the one arriving at the active stage lights up */}
      {ANGLES.map((deg, i) => {
        const next = ANGLES[(i + 1) % ANGLES.length]
        const to = next < deg ? next + 360 : next
        const arrivesAt = (i + 1) % ANGLES.length
        return (
          <g key={`arc-${i}`}>
            <path
              d={arcBetween(deg, to)}
              fill="none"
              strokeWidth={lit(arrivesAt) ? 3 : 1.5}
              stroke={lit(arrivesAt) ? "var(--brand)" : "var(--border)"}
              style={{ transition: "stroke 420ms ease-out, stroke-width 420ms ease-out" }}
            />
            <path
              d={tangentArrow(to - GAP - 3)}
              fill={lit(arrivesAt) ? "var(--brand)" : "var(--border)"}
              style={{ transition: "fill 420ms ease-out" }}
            />
          </g>
        )
      })}

      {/* the return chord: drift re-enters at verify, not at ingest */}
      <path
        d={CHORD}
        fill="none"
        stroke="var(--brand)"
        strokeWidth={1.5}
        strokeDasharray="5 6"
        opacity={0.85}
      />
      <path d={tangentArrow(54 - 20)} fill="var(--brand)" opacity={0.85} />
      {/* Knocked out of the dashes behind it with a background-coloured stroke,
          rather than nudged clear of them — the label belongs on the chord. */}
      <text
        x={432}
        y={CY + 43}
        textAnchor="middle"
        className="fill-muted-foreground font-sans"
        fontSize={17}
        stroke="var(--background)"
        strokeWidth={8}
        paintOrder="stroke"
      >
        re-verified, not re-ingested
      </text>

      {/* stage markers and labels */}
      {ANGLES.map((deg, i) => {
        const stage = LOOP_STAGES[i]
        const node = at(deg, R)
        const label = at(deg, R + 34)
        const anchor = anchorFor(deg)
        const on = lit(i)
        return (
          <g key={stage.key} style={{ transition: "opacity 420ms ease-out" }}>
            <circle cx={node.x} cy={node.y} r={9} fill="var(--background)" />
            <circle
              cx={node.x}
              cy={node.y}
              r={on ? 7.5 : 5}
              fill={on ? "var(--brand)" : "var(--border)"}
              style={{ transition: "fill 420ms ease-out, r 420ms ease-out" }}
            />
            <text
              x={label.x}
              y={label.y}
              textAnchor={anchor}
              className="font-display"
              fill={on ? "var(--foreground)" : "var(--muted-foreground)"}
              fontSize={30}
              style={{ transition: "fill 420ms ease-out" }}
            >
              {stage.name}
            </text>
            <text
              x={label.x}
              y={label.y + 25}
              textAnchor={anchor}
              className="font-mono fill-muted-foreground"
              fontSize={17}
            >
              {stage.machinery}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

/**
 * The same five stages as a vertical track. Narrow viewports cannot carry a ring
 * with radial labels without either shrinking the type below readable size or
 * clipping the labels, so this is a different composition of the same content
 * rather than the ring scaled down.
 */
export function LoopTrack({ activeStage }: { activeStage?: number }) {
  const lit = (i: number) => activeStage === undefined || activeStage === i
  return (
    <ol className="relative space-y-7 pl-8">
      <span aria-hidden className="absolute top-2 bottom-6 left-[5px] w-px bg-border" />
      {LOOP_STAGES.map((stage, i) => (
        <li key={stage.key} className="relative">
          <span
            aria-hidden
            className="absolute top-[7px] -left-8 size-[11px] rounded-full transition-colors duration-500"
            style={{ background: lit(i) ? "var(--brand)" : "var(--border)" }}
          />
          <p
            className="font-display text-xl transition-colors duration-500"
            style={{ color: lit(i) ? "var(--foreground)" : "var(--muted-foreground)" }}
          >
            {stage.name}
          </p>
          <p className="mt-0.5 font-mono text-xs text-muted-foreground">{stage.machinery}</p>
        </li>
      ))}
      <li className="relative">
        <span
          aria-hidden
          className="absolute -top-4 -left-[30px] h-[calc(100%+1rem)] w-4 rounded-l-full border-y border-l border-dashed border-[var(--brand)] opacity-80"
        />
        <p className="text-sm text-muted-foreground">
          …and back into <span className="text-foreground">Verify</span> — re-verified, not
          re-ingested.
        </p>
      </li>
    </ol>
  )
}
