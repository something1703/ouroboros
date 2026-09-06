import { ArrowUpRight } from "lucide-react"
import { Link } from "react-router-dom"

interface Resource {
  title: string
  description: string
  href: string
  external?: boolean
}

const RESOURCE_GROUPS: { heading: string; items: Resource[] }[] = [
  {
    heading: "The product",
    items: [
      {
        title: "How it works",
        description: "The five real stages of the loop, ingest through re-verification.",
        href: "/how-it-works",
      },
      {
        title: "Docs",
        description: "Architecture, data model, and the real Parallel integration.",
        href: "/docs",
      },
      {
        title: "Open the dashboard",
        description: "Sign in and see it work on a real project.",
        href: "/app",
      },
    ],
  },
  {
    heading: "The code",
    items: [
      {
        title: "GitHub repository",
        description: "All source, infrastructure, and run instructions — public.",
        href: "https://github.com/something1703/ouroboros",
        external: true,
      },
      {
        title: "License",
        description: "Apache-2.0.",
        href: "https://github.com/something1703/ouroboros/blob/main/LICENSE",
        external: true,
      },
    ],
  },
]

export function ResourcesPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="font-display text-4xl text-foreground">Resources</h1>
      <p className="mt-2 text-muted-foreground">Everything real about this project, in one place.</p>

      <div className="mt-10 space-y-10">
        {RESOURCE_GROUPS.map((group) => (
          <div key={group.heading}>
            <h2 className="text-sm font-medium text-muted-foreground">{group.heading}</h2>
            <ul className="mt-3 space-y-2">
              {group.items.map((item) => {
                const content = (
                  <>
                    <div>
                      <p className="font-display text-lg text-foreground">{item.title}</p>
                      <p className="mt-0.5 text-sm text-muted-foreground">{item.description}</p>
                    </div>
                    <ArrowUpRight className="size-4 shrink-0 text-muted-foreground" />
                  </>
                )
                return (
                  <li key={item.title}>
                    {item.external ? (
                      <a
                        href={item.href}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center justify-between gap-3 rounded-lg border border-border px-5 py-4 transition-colors hover:border-primary hover:bg-accent"
                      >
                        {content}
                      </a>
                    ) : (
                      <Link
                        to={item.href}
                        className="flex items-center justify-between gap-3 rounded-lg border border-border px-5 py-4 transition-colors hover:border-primary hover:bg-accent"
                      >
                        {content}
                      </Link>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </div>

      <p className="mt-10 border-t border-border pt-6 text-sm text-muted-foreground">
        Built for <em className="text-foreground">Agentic Cinema: The Blockbuster Hackathon</em> —
        Parallel track, on Google Cloud's Gemini Enterprise Agent Platform and Parallel Web
        Systems.
      </p>
    </div>
  )
}
