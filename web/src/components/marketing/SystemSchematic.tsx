import { useEffect, useRef, useState } from "react"

// The hero's centerpiece: an authored schematic of the system that is actually
// deployed, not an illustration of an idea. Every node here is a real running
// thing (a Cloud Run service, a database, a Parallel API), and the wires are the
// real call paths. Hovering a subsystem lights only its own nodes and wires, so
// the machine can be read one part at a time instead of all at once.
//
// The motion is load-bearing rather than decorative: wires draw themselves once on
// entry (the system assembling), and packets ride the main path continuously
// afterwards (the loop never stopping, which is the entire product thesis). Both
// are suppressed under prefers-reduced-motion.

type GroupKey = "ingest" | "ledger" | "agents" | "parallel" | "loop"

interface Node {
  id: string
  group: GroupKey
  x: number
  y: number
  w: number
  label: string
  /** Rendered in mono beneath the label -- these are real identifiers. */
  sub?: string
}

const H = 38

const NODES: Node[] = [
  // 1 — ingest
  { id: "gcs", group: "ingest", x: 16, y: 78, w: 148, label: "Cloud Storage", sub: "intake" },
  { id: "eventarc", group: "ingest", x: 16, y: 146, w: 148, label: "Eventarc" },
  { id: "ingest", group: "ingest", x: 16, y: 214, w: 148, label: "ingest", sub: "Cloud Run" },
  { id: "gemini", group: "ingest", x: 16, y: 282, w: 148, label: "Gemini", sub: "doc + video" },
  { id: "armor", group: "ingest", x: 16, y: 350, w: 148, label: "Model Armor" },

  // 2 — ledger
  { id: "sql", group: "ledger", x: 224, y: 214, w: 150, label: "Cloud SQL", sub: "claim ledger" },
  { id: "toolbox", group: "ledger", x: 224, y: 282, w: 150, label: "MCP Toolbox" },
  { id: "firestore", group: "ledger", x: 224, y: 146, w: 150, label: "Firestore", sub: "live views" },

  // 3 — agents
  { id: "coord", group: "agents", x: 436, y: 78, w: 158, label: "Coordinator", sub: "ADK" },
  { id: "clear", group: "agents", x: 436, y: 146, w: 158, label: "CLEAR", sub: "4 specialists" },
  { id: "truecut", group: "agents", x: 436, y: 214, w: 158, label: "TRUE CUT" },
  { id: "risk", group: "agents", x: 436, y: 282, w: 158, label: "RiskAssessor" },
  { id: "reporter", group: "agents", x: 436, y: 350, w: 158, label: "Reporter" },

  // 4 — parallel
  { id: "search", group: "parallel", x: 660, y: 146, w: 150, label: "Search" },
  { id: "task", group: "parallel", x: 660, y: 214, w: 150, label: "Task", sub: "+ Basis" },
  { id: "memory", group: "parallel", x: 660, y: 282, w: 150, label: "Memory" },
  { id: "monitor", group: "parallel", x: 660, y: 350, w: 150, label: "Monitor" },

  // 5 — loop
  { id: "webhook", group: "loop", x: 660, y: 434, w: 150, label: "webhook-receiver" },
  { id: "reverify", group: "loop", x: 436, y: 434, w: 158, label: "reverify-worker" },
]

const BY_ID = Object.fromEntries(NODES.map((n) => [n.id, n]))

/** Right edge / left edge / centre helpers, so wires attach to real geometry. */
const rightOf = (id: string) => ({ x: BY_ID[id].x + BY_ID[id].w, y: BY_ID[id].y + H / 2 })
const leftOf = (id: string) => ({ x: BY_ID[id].x, y: BY_ID[id].y + H / 2 })
const bottomOf = (id: string) => ({ x: BY_ID[id].x + BY_ID[id].w / 2, y: BY_ID[id].y + H })
const topOf = (id: string) => ({ x: BY_ID[id].x + BY_ID[id].w / 2, y: BY_ID[id].y })

/** Orthogonal-ish connector with a soft mid bend -- reads as a circuit trace
 *  rather than a hand-drawn arc, matching the instrument-panel register. */
function wireH(fromId: string, toId: string): string {
  const a = rightOf(fromId)
  const b = leftOf(toId)
  const mid = (a.x + b.x) / 2
  return `M${a.x},${a.y} C${mid},${a.y} ${mid},${b.y} ${b.x},${b.y}`
}
function wireV(fromId: string, toId: string): string {
  const a = bottomOf(fromId)
  const b = topOf(toId)
  const mid = (a.y + b.y) / 2
  return `M${a.x},${a.y} C${a.x},${mid} ${b.x},${mid} ${b.x},${b.y}`
}

interface Wire {
  d: string
  group: GroupKey
  /** Carries the animated packets -- only the spine of the loop does. */
  spine?: boolean
}

const WIRES: Wire[] = [
  { d: wireV("gcs", "eventarc"), group: "ingest", spine: true },
  { d: wireV("eventarc", "ingest"), group: "ingest", spine: true },
  { d: wireV("ingest", "gemini"), group: "ingest" },
  { d: wireV("gemini", "armor"), group: "ingest" },
  { d: wireH("armor", "sql"), group: "ingest", spine: true },
  { d: wireH("ingest", "sql"), group: "ingest" },
  { d: wireV("firestore", "sql"), group: "ledger" },
  { d: wireV("sql", "toolbox"), group: "ledger" },
  { d: wireH("sql", "coord"), group: "agents", spine: true },
  { d: wireH("toolbox", "clear"), group: "ledger" },
  { d: wireV("coord", "clear"), group: "agents", spine: true },
  { d: wireV("clear", "truecut"), group: "agents" },
  { d: wireV("truecut", "risk"), group: "agents", spine: true },
  { d: wireV("risk", "reporter"), group: "agents", spine: true },
  { d: wireH("clear", "search"), group: "parallel", spine: true },
  { d: wireH("truecut", "task"), group: "parallel" },
  { d: wireV("search", "task"), group: "parallel" },
  { d: wireV("task", "memory"), group: "parallel" },
  { d: wireH("reporter", "monitor"), group: "parallel", spine: true },
  { d: wireV("monitor", "webhook"), group: "loop", spine: true },
  { d: wireH("webhook", "reverify"), group: "loop", spine: true },
  // the closing arc: re-verification re-enters the ledger, not ingest
  { d: `M${leftOf("reverify").x},${leftOf("reverify").y} C300,453 300,300 ${bottomOf("sql").x - 40},${bottomOf("toolbox").y + 22}`, group: "loop", spine: true },
  { d: `M${bottomOf("sql").x - 40},${bottomOf("toolbox").y + 22} C260,300 ${leftOf("sql").x - 20},280 ${leftOf("sql").x},${leftOf("sql").y + 6}`, group: "loop" },
  // Parallel calling back into our own ledger, mid-research
  { d: `M${leftOf("task").x},${leftOf("task").y + 8} C620,250 400,300 ${rightOf("toolbox").x},${rightOf("toolbox").y}`, group: "parallel" },
]

const GROUPS: { key: GroupKey; label: string; x: number; w: number }[] = [
  { key: "ingest", label: "Ingest", x: 8, w: 164 },
  { key: "ledger", label: "Ledger", x: 216, w: 166 },
  { key: "agents", label: "Agents", x: 428, w: 174 },
  { key: "parallel", label: "Parallel", x: 652, w: 166 },
]

export function SystemSchematic({
  className,
  lit = false,
}: {
  className?: string
  /** The projector-beam reveal layer: same geometry, drawn entirely in ember and
   *  inert (no packets, no hover, no a11y role -- the base copy carries all that). */
  lit?: boolean
}) {
  const ref = useRef<SVGSVGElement>(null)
  const [drawn, setDrawn] = useState(false)
  const [hovered, setHovered] = useState<GroupKey | null>(null)
  const [motionOK] = useState(() => !window.matchMedia("(prefers-reduced-motion: reduce)").matches)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setDrawn(true)
          io.disconnect()
        }
      },
      { threshold: 0.15 },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  const dim = (group: GroupKey) => !lit && hovered !== null && hovered !== group
  const ink = (active: boolean) => (lit || active ? "var(--brand)" : "var(--border)")

  return (
    <svg
      ref={ref}
      viewBox="0 0 830 500"
      className={className}
      role={lit ? undefined : "img"}
      aria-hidden={lit || undefined}
      aria-label={
        lit
          ? undefined
          : "Schematic of the deployed system: ingest, the claim ledger, the agent trees, Parallel's research APIs, and the re-verification loop closing back into the ledger."
      }
      onMouseLeave={lit ? undefined : () => setHovered(null)}
    >
      <defs>
        {/* Node fill: one step above the page ground, per the tonal ladder. */}
        <clipPath id="schematic-clip">
          <rect x="0" y="0" width="830" height="500" />
        </clipPath>
      </defs>

      {/* subsystem frames */}
      {GROUPS.map((g) => (
        <g key={g.key} style={{ transition: "opacity 320ms ease-out" }} opacity={dim(g.key) ? 0.25 : 1}>
          <rect
            x={g.x}
            y={52}
            width={g.w}
            height={g.key === "agents" || g.key === "parallel" ? 344 : 344}
            rx={10}
            fill="none"
            stroke="var(--border)"
            strokeDasharray="2 5"
            opacity={hovered === g.key ? 0.9 : 0.45}
          />
          <text
            x={g.x + 4}
            y={42}
            className="font-sans"
            fontSize={13}
            fill={lit || hovered === g.key ? "var(--brand)" : "var(--muted-foreground)"}
            style={{ transition: "fill 320ms ease-out" }}
          >
            {g.label}
          </text>
        </g>
      ))}

      {/* wires */}
      <g fill="none" strokeLinecap="round">
        {WIRES.map((w, i) => (
          <path
            key={`w-${i}`}
            d={w.d}
            stroke={ink(hovered === w.group)}
            strokeWidth={hovered === w.group ? 1.6 : 1.2}
            opacity={dim(w.group) ? 0.2 : 1}
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={lit || drawn || !motionOK ? 0 : 1}
            style={{
              transition: `stroke-dashoffset 1100ms cubic-bezier(0.22,1,0.36,1) ${120 + i * 45}ms, stroke 320ms ease-out, opacity 320ms ease-out, stroke-width 320ms ease-out`,
            }}
          />
        ))}
      </g>

      {/* packets riding the loop spine -- the system is running, continuously */}
      {motionOK && drawn && !lit && (
        <g>
          {WIRES.filter((w) => w.spine).map((w, i) => (
            <circle key={`p-${i}`} r={2.6} fill="var(--brand)">
              <animateMotion
                dur="2.6s"
                begin={`${i * 0.34}s`}
                repeatCount="indefinite"
                path={w.d}
                keyPoints="0;1"
                keyTimes="0;1"
                calcMode="spline"
                keySplines="0.4 0 0.6 1"
              />
              <animate
                attributeName="opacity"
                values="0;1;1;0"
                keyTimes="0;0.15;0.8;1"
                dur="2.6s"
                begin={`${i * 0.34}s`}
                repeatCount="indefinite"
              />
            </circle>
          ))}
        </g>
      )}

      {/* nodes */}
      {NODES.map((n) => {
        const active = hovered === n.group
        return (
          <g
            key={n.id}
            opacity={dim(n.group) ? 0.28 : 1}
            style={{ transition: "opacity 320ms ease-out" }}
            onMouseEnter={lit ? undefined : () => setHovered(n.group)}
          >
            <rect
              x={n.x}
              y={n.y}
              width={n.w}
              height={H}
              rx={7}
              fill={lit ? "none" : "var(--card)"}
              stroke={ink(active)}
              strokeWidth={active ? 1.4 : 1}
              style={{ transition: "stroke 320ms ease-out, stroke-width 320ms ease-out" }}
            />
            <text
              x={n.x + 11}
              y={n.sub ? n.y + 16 : n.y + 23}
              className="font-sans"
              fontSize={12.5}
              fill={lit ? "var(--brand)" : "var(--foreground)"}
            >
              {n.label}
            </text>
            {n.sub ? (
              <text
                x={n.x + 11}
                y={n.y + 29}
                className="font-mono"
                fontSize={10.5}
                fill={lit ? "var(--brand)" : "var(--muted-foreground)"}
              >
                {n.sub}
              </text>
            ) : null}
          </g>
        )
      })}

      {/* the closing label on the return arc */}
      <text
        x={296}
        y={412}
        textAnchor="middle"
        className="font-sans"
        fontSize={11.5}
        fill={lit ? "var(--brand)" : "var(--muted-foreground)"}
        stroke="var(--background)"
        strokeWidth={7}
        paintOrder="stroke"
        opacity={dim("loop") ? 0.25 : 1}
        style={{ transition: "opacity 320ms ease-out" }}
      >
        re-verify → ledger
      </text>
    </svg>
  )
}
