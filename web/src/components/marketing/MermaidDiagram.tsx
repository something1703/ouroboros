import { useEffect, useId, useRef, useState } from "react"
import mermaid from "mermaid"

// The real, planning-time system diagram -- imported directly from the repo root
// (?raw, a Vite build-time string import) so this is the same file README.md
// embeds natively via GitHub's own mermaid rendering, not a hand-copied string
// that could drift from it. One source of truth, two renderers.
import architectureSource from "../../../../ouroboros_architecture.mermaid?raw"

let initialized = false
function ensureInitialized() {
  if (initialized) return
  initialized = true
  // themeVariables only sets the neutral chrome (background, default node fill,
  // line color, cluster background) -- the diagram's own seven classDefs (gcp /
  // parallel / loop / stretch) already carry its real color-coding and are left
  // alone, so the diagram means the same thing here as it does on GitHub.
  mermaid.initialize({
    startOnLoad: false,
    theme: "base",
    fontFamily: "IBM Plex Sans, ui-sans-serif, system-ui, sans-serif",
    themeVariables: {
      background: "#15120f",
      primaryColor: "#1f1b17",
      primaryBorderColor: "#332c24",
      primaryTextColor: "#ede7dd",
      lineColor: "#9c9186",
      secondaryColor: "#1f1b17",
      tertiaryColor: "#1f1b17",
      clusterBkg: "#1a1613",
      clusterBorder: "#332c24",
      edgeLabelBackground: "#15120f",
      fontSize: "15px",
    },
  })
}

/** The full seven-subsystem system diagram, client-rendered from the same source
 * GitHub renders in README.md. Wide by nature (a left-right flowchart with 40+
 * nodes) -- scrolls horizontally inside its own frame rather than shrinking to
 * illegibility, per this project's own rule for wide diagrams and tables. */
export function MermaidDiagram() {
  const id = useId().replace(/[:]/g, "")
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ensureInitialized()
    mermaid
      .render(`mermaid-${id}`, architectureSource)
      .then(({ svg }) => {
        if (!cancelled && containerRef.current) containerRef.current.innerHTML = svg
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Diagram failed to render.")
      })
    return () => {
      cancelled = true
    }
  }, [id])

  if (error) {
    return (
      <p className="rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
        Diagram failed to render ({error}) —{" "}
        <a
          href="https://github.com/something1703/ouroboros/blob/main/ouroboros_architecture.mermaid"
          target="_blank"
          rel="noreferrer"
          className="text-[var(--brand)] underline underline-offset-2"
        >
          view the source on GitHub
        </a>
        .
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border bg-card p-4 sm:p-6">
      <div ref={containerRef} className="[&_svg]:h-auto [&_svg]:min-w-[860px]" />
    </div>
  )
}
