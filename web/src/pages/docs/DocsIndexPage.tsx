import { Link } from "react-router-dom"
import { DOCS } from "@/content/docs"

export function DocsIndexPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="font-display text-4xl text-foreground">Docs</h1>
      <p className="mt-2 text-muted-foreground">
        The real architecture, data model, and Parallel integration — written for
        this site, faithful to the system actually running.
      </p>

      <ul className="mt-10 space-y-1">
        {DOCS.map((doc) => (
          <li key={doc.slug}>
            <Link
              to={`/docs/${doc.slug}`}
              className="block rounded-lg border border-border px-5 py-4 transition-colors hover:border-primary hover:bg-accent"
            >
              <p className="font-display text-lg text-foreground">{doc.title}</p>
              <p className="mt-1 text-sm text-muted-foreground">{doc.summary}</p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
