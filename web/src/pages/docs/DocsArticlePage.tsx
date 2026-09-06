import { Link, Navigate, useParams } from "react-router-dom"
import { getDocBySlug } from "@/content/docs"

export function DocsArticlePage() {
  const { slug } = useParams<{ slug: string }>()
  const doc = getDocBySlug(slug)

  if (!doc) return <Navigate to="/docs" replace />

  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <Link to="/docs" className="text-sm text-muted-foreground hover:text-foreground">
        ← Docs
      </Link>
      <h1 className="mt-4 font-display text-4xl text-foreground">{doc.title}</h1>
      <p className="mt-2 text-muted-foreground">{doc.summary}</p>

      <div className="mt-10 space-y-10">
        {doc.sections.map((section) => (
          <section key={section.heading}>
            <h2 className="font-display text-xl text-foreground">{section.heading}</h2>
            <div className="mt-2 space-y-3 text-sm text-muted-foreground">
              {section.body.map((paragraph, i) => (
                <p key={i}>{paragraph}</p>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  )
}
