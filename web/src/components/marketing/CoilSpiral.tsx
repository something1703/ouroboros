// The landing page's signature instrument: a single continuous SVG path, always
// sampled at the same point count regardless of `turns`, so the browser can smoothly
// interpolate the `d` attribute between states (a differently-shaped path with the
// same command sequence animates; a structurally different one just snaps). More
// turns packed into the same radius reads as the coil winding tighter -- the loop
// literalized as PRODUCT.md's positioning describes it, not just illustrated.
const SAMPLE_POINTS = 240

function buildSpiralPath(turns: number, size: number, strokeWidth: number): string {
  const cx = size / 2
  const cy = size / 2
  const maxRadius = size / 2 - strokeWidth * 2
  const minRadius = size * 0.04
  let d = ""
  for (let i = 0; i <= SAMPLE_POINTS; i++) {
    const t = i / SAMPLE_POINTS
    const angle = t * turns * 2 * Math.PI - Math.PI / 2
    const radius = maxRadius - (maxRadius - minRadius) * t
    const x = cx + radius * Math.cos(angle)
    const y = cy + radius * Math.sin(angle)
    d += `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)} `
  }
  return d
}

export function CoilSpiral({
  turns,
  size = 400,
  strokeWidth = 4,
  className,
}: {
  turns: number
  size?: number
  strokeWidth?: number
  className?: string
}) {
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      style={{ width: size, height: size }}
      aria-hidden
    >
      <path
        d={buildSpiralPath(turns, size, strokeWidth)}
        fill="none"
        stroke="var(--brand)"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        style={{ transition: "d 700ms cubic-bezier(0.4, 0, 0.2, 1)" }}
      />
    </svg>
  )
}
