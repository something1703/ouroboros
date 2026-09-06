import { ArrowRight } from "lucide-react"
import { Link } from "react-router-dom"
import { DOCS } from "@/content/docs"

// A hairline-divided list rather than a grid of equal cards: the six pages have a
// deliberate reading order (why, then how, then what it costs and what is broken),
// and identical cards would flatten that into six interchangeable tiles.

export function DocsIndexPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-16 lg:py-24">
      <h1 className="font-display text-4xl text-foreground sm:text-5xl">Docs</h1>
      <p className="mt-4 max-w-[58ch] text-lg leading-relaxed text-foreground/90">
        How we framed the problem, how the system is built, what it measurably does, and where it
        falls short. Written from this project's own decision log and evidence files — the numbers
        are the measured ones, and the failures are in here too.
      </p>

      <ol className="mt-14 border-t border-border">
        {DOCS.map((doc) => (
          <li key={doc.slug}>
            <Link
              to={`/docs/${doc.slug}`}
              className="group -mx-4 grid gap-x-8 gap-y-2 rounded-lg border-b border-border px-4 py-6 transition-colors hover:bg-accent/50 sm:grid-cols-[1fr_5rem_1.5rem] sm:items-center"
            >
              <div className="min-w-0">
                <span className="font-display text-2xl text-foreground">{doc.title}</span>
                <p className="mt-1.5 max-w-[62ch] text-[0.975rem] leading-relaxed text-muted-foreground">
                  {doc.summary}
                </p>
              </div>
              <span className="font-mono text-sm text-muted-foreground sm:text-right">
                {doc.readingTime}
              </span>
              <ArrowRight
                aria-hidden
                className="hidden size-4 shrink-0 -translate-x-1 text-muted-foreground opacity-0 transition-all duration-200 group-hover:translate-x-0 group-hover:text-foreground group-hover:opacity-100 sm:block sm:justify-self-end"
              />
            </Link>
          </li>
        ))}
      </ol>
    </div>
  )
}
