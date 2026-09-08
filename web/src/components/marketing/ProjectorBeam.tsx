import { useEffect, useRef, useState, type ReactNode } from "react"

// DESIGN.md's north star, made literal and interactive: "a dark theater... the
// ember-orange used like a projector's glow through the dark." The base layer is
// the machine drawn in hairline; a beam that follows the pointer paints whatever
// it falls across in ember. Moving the cursor is what reveals the architecture,
// so the effect is the explanation rather than an ornament on top of one.
//
// Before the pointer has moved (and on touch, where it never will) the beam
// drifts on a slow Lissajous path so the page is alive on arrival and the effect
// is not gated behind a mouse. Reduced-motion callers get the lit layer held
// still at the centre instead of a moving light.

export function ProjectorBeam({
  children,
  reveal,
  radius = 230,
  className,
}: {
  /** The dim base layer -- interactive, and the only copy in the a11y tree. */
  children: ReactNode
  /** The same content drawn in ember, masked to the beam. Inert. */
  reveal: ReactNode
  radius?: number
  className?: string
}) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [motionOK] = useState(() => !window.matchMedia("(prefers-reduced-motion: reduce)").matches)
  const driftingRef = useRef(true)

  useEffect(() => {
    const reduced = !motionOK
    const host = hostRef.current
    if (!host) return

    const set = (x: number, y: number) => {
      host.style.setProperty("--beam-x", `${x}px`)
      host.style.setProperty("--beam-y", `${y}px`)
    }

    // start centred, so there is never a frame with an unpositioned beam
    const rect0 = host.getBoundingClientRect()
    set(rect0.width / 2, rect0.height * 0.45)
    if (reduced) return

    let raf = 0
    const t0 = performance.now()
    const drift = (now: number) => {
      if (!driftingRef.current) return
      const rect = host.getBoundingClientRect()
      const t = (now - t0) / 1000
      // two incommensurate frequencies -- the path never visibly repeats
      const x = rect.width * (0.5 + 0.3 * Math.sin(t * 0.24))
      const y = rect.height * (0.45 + 0.26 * Math.sin(t * 0.37 + 1.1))
      set(x, y)
      raf = requestAnimationFrame(drift)
    }
    raf = requestAnimationFrame(drift)

    const onMove = (e: PointerEvent) => {
      driftingRef.current = false
      cancelAnimationFrame(raf)
      const rect = host.getBoundingClientRect()
      set(e.clientX - rect.left, e.clientY - rect.top)
    }
    const onLeave = () => {
      driftingRef.current = true
      raf = requestAnimationFrame(drift)
    }

    host.addEventListener("pointermove", onMove)
    host.addEventListener("pointerleave", onLeave)
    return () => {
      cancelAnimationFrame(raf)
      host.removeEventListener("pointermove", onMove)
      host.removeEventListener("pointerleave", onLeave)
    }
  }, [motionOK])

  const mask = `radial-gradient(circle ${radius}px at var(--beam-x, 50%) var(--beam-y, 45%), #000 0%, #000 34%, rgba(0,0,0,0.35) 58%, transparent 74%)`

  return (
    <div ref={hostRef} className={className} style={{ position: "relative" }}>
      {children}
      {/* the light spill: a specific effect (a projector's cone falling on the
          machine), not a decorative glow -- kept low enough that it never becomes
          a second accent field competing with the ember lines it reveals. */}
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          background: `radial-gradient(circle ${radius * 1.15}px at var(--beam-x, 50%) var(--beam-y, 45%), color-mix(in srgb, var(--brand) 13%, transparent) 0%, transparent 70%)`,
          transition: motionOK ? "none" : "background 200ms linear",
        }}
      />
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          pointerEvents: "none",
          WebkitMaskImage: mask,
          maskImage: mask,
        }}
      >
        {reveal}
      </div>
    </div>
  )
}
