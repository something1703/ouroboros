import { useEffect, useState } from "react"
import { Link, Navigate, useParams } from "react-router-dom"
import { CadenceDial } from "@/components/marketing/CadenceDial"
import { LoopDiagram, LoopTrack } from "@/components/marketing/LoopDiagram"
import { DOCS, getDocBySlug, type Block } from "@/content/docs"
import { cn } from "@/lib/utils"

/** Stable id for a heading, so the contents rail can link to it. */
const slugify = (text: string) =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")

function Figure({ block }: { block: Extract<Block, { kind: "figure" }> }) {
  return (
    <figure className="my-12">
      {block.id === "loop" ? (
        <>
          <LoopDiagram className="hidden w-full md:block" />
          <div className="md:hidden">
            <LoopTrack />
          </div>
        </>
      ) : (
        <CadenceDial />
      )}
      {block.caption ? (
        <figcaption className="mt-4 max-w-[62ch] text-sm text-muted-foreground">
          {block.caption}
        </figcaption>
      ) : null}
    </figure>
  )
}

function Tree({ block }: { block: Extract<Block, { kind: "tree" }> }) {
  return (
    <figure className="my-10 border-y border-border py-6">
      <ul className="space-y-1.5">
        {block.lines.map((line, i) => (
          <li
            key={`${i}-${line.name}`}
            className="flex flex-wrap items-baseline gap-x-3 text-sm"
            style={{ paddingLeft: `${line.depth * 1.4}rem` }}
          >
            <span className={line.depth <= 1 ? "text-foreground" : "text-foreground/85"}>
              {line.name}
            </span>
            {line.note ? (
              <span className="text-xs text-muted-foreground">{line.note}</span>
            ) : null}
          </li>
        ))}
      </ul>
      {block.caption ? (
        <figcaption className="mt-5 max-w-[62ch] text-sm text-muted-foreground">
          {block.caption}
        </figcaption>
      ) : null}
    </figure>
  )
}

/** A decision, shown as what was taken against what was refused. */
function Choice({ block }: { block: Extract<Block, { kind: "choice" }> }) {
  const rows: [string, string, boolean][] = [
    ["We chose", block.took, true],
    ["Over", block.over, false],
    ["Because", block.because, true],
  ]
  return (
    <div className="my-8 border-t border-border pt-5">
      <dl className="space-y-3">
        {rows.map(([term, text, strong]) => (
          <div key={term} className="grid gap-x-6 gap-y-1 sm:grid-cols-[6rem_1fr]">
            <dt className="text-sm text-muted-foreground">{term}</dt>
            <dd
              className={
                strong
                  ? "max-w-[62ch] text-[0.975rem] text-foreground"
                  : "max-w-[62ch] text-[0.975rem] text-muted-foreground line-through decoration-border"
              }
            >
              {text}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

/** A production failure, in the order it was actually understood. */
function Found({ block }: { block: Extract<Block, { kind: "found" }> }) {
  const rows: [string, string][] = [
    ["Symptom", block.symptom],
    ["We chased", block.chased],
    ["It was", block.actual],
    ["Which means", block.lesson],
  ]
  return (
    <div className="my-10 border-y border-border py-6">
      <p className="font-display text-xl text-foreground">{block.heading}</p>
      <dl className="mt-4 space-y-3">
        {rows.map(([term, text]) => (
          <div key={term} className="grid gap-x-6 gap-y-1 sm:grid-cols-[7rem_1fr]">
            <dt className="text-sm text-muted-foreground">{term}</dt>
            <dd className="max-w-[62ch] text-[0.975rem] text-foreground/90">{text}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

function Measures({ block }: { block: Extract<Block, { kind: "measures" }> }) {
  return (
    <figure className="my-10">
      <dl className="border-t border-border">
        {block.rows.map((row) => (
          <div
            key={row.label}
            className="flex items-baseline justify-between gap-x-8 border-b border-border py-4"
          >
            <div className="min-w-0">
              <dt className="text-[0.975rem] text-foreground">{row.label}</dt>
              {row.note ? (
                <p className="mt-1 max-w-[52ch] text-sm leading-relaxed text-muted-foreground">
                  {row.note}
                </p>
              ) : null}
            </div>
            <dd className="shrink-0 font-mono text-[1.0625rem] text-[var(--brand)] tabular-nums">
              {row.value}
            </dd>
          </div>
        ))}
      </dl>
      {block.caption ? (
        <figcaption className="mt-4 max-w-[62ch] text-sm text-muted-foreground">
          {block.caption}
        </figcaption>
      ) : null}
    </figure>
  )
}

function Limits({ block }: { block: Extract<Block, { kind: "limits" }> }) {
  return (
    <div className="my-10 border-y border-border py-6">
      <p className="font-display text-xl text-foreground">{block.heading}</p>
      <ul className="mt-4 space-y-3">
        {block.items.map((item) => (
          <li key={item} className="flex max-w-[68ch] gap-3 text-[0.975rem] text-foreground/90">
            <span aria-hidden className="mt-2.5 size-1.5 shrink-0 rounded-full bg-border" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function renderBlock(block: Block, i: number) {
  switch (block.kind) {
    case "lede":
      return (
        <p key={i} className="max-w-[58ch] text-xl leading-relaxed text-foreground sm:text-[1.4rem]">
          {block.text}
        </p>
      )
    case "p":
      return (
        <p key={i} className="max-w-[68ch] text-[1.0625rem] leading-[1.72] text-foreground/90">
          {block.text}
        </p>
      )
    case "h":
      return (
        <h2
          key={i}
          id={slugify(block.text)}
          className="scroll-mt-20 pt-10 font-display text-[1.75rem] text-foreground"
        >
          {block.text}
        </h2>
      )
    case "figure":
      return <Figure key={i} block={block} />
    case "tree":
      return <Tree key={i} block={block} />
    case "choice":
      return <Choice key={i} block={block} />
    case "found":
      return <Found key={i} block={block} />
    case "measures":
      return <Measures key={i} block={block} />
    case "limits":
      return <Limits key={i} block={block} />
  }
}

/** Highlights the contents rail's current section as the reader scrolls past it --
 * the difference between a link list and an actual reading aid. Picks the last
 * heading whose top has scrolled up past a fixed reading line, the same
 * closest-crossed-heading approach LandingPage.tsx's useActiveStage already uses --
 * an IntersectionObserver band was tried first and went stale mid-scroll whenever a
 * long section (a figure, a tree diagram) pushed both its own heading and the next
 * one outside a narrow band at once, since then nothing was left intersecting to
 * report. Tracking position directly always has an answer. */
function useActiveHeading(slugs: string[]): string | null {
  const [active, setActive] = useState<string | null>(null)
  const slugsKey = slugs.join("|")

  useEffect(() => {
    const ids = slugsKey ? slugsKey.split("|") : []
    const elements = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el != null)
    if (elements.length === 0) return

    const READING_LINE_PX = 96 // just under the sticky header

    let ticking = false
    function evaluate() {
      ticking = false
      let current = elements[0]?.id ?? null
      for (const el of elements) {
        if (el.getBoundingClientRect().top <= READING_LINE_PX) current = el.id
      }
      setActive(current)
    }
    function onScroll() {
      if (ticking) return
      ticking = true
      requestAnimationFrame(evaluate)
    }

    evaluate()
    window.addEventListener("scroll", onScroll, { passive: true })
    window.addEventListener("resize", onScroll)
    return () => {
      window.removeEventListener("scroll", onScroll)
      window.removeEventListener("resize", onScroll)
    }
  }, [slugsKey])

  return active
}

export function DocsArticlePage() {
  const { slug } = useParams()
  const doc = getDocBySlug(slug)

  // Hooks run unconditionally, before the "no such doc" early return below --
  // an empty array is a safe, inert input to useActiveHeading when there's no doc.
  const headings = doc
    ? doc.blocks.filter((b): b is Extract<Block, { kind: "h" }> => b.kind === "h")
    : []
  const activeHeading = useActiveHeading(headings.map((h) => slugify(h.text)))

  if (!doc) return <Navigate to="/docs" replace />

  const index = DOCS.findIndex((d) => d.slug === doc.slug)
  const next = DOCS[index + 1]

  return (
    <div className="mx-auto grid max-w-6xl gap-x-16 px-6 py-16 lg:grid-cols-[1fr_15rem] lg:py-24">
      <article className="min-w-0">
        <Link
          to="/docs"
          className="text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          ← All docs
        </Link>
        <h1 className="mt-6 font-display text-4xl text-foreground sm:text-5xl">{doc.title}</h1>
        <p className="mt-3 max-w-[58ch] text-[1.0625rem] text-muted-foreground">{doc.summary}</p>

        <div className="mt-12 space-y-6">{doc.blocks.map(renderBlock)}</div>

        {next ? (
          <Link
            to={`/docs/${next.slug}`}
            className="mt-20 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-t border-border pt-6 transition-colors hover:text-foreground"
          >
            <span className="text-sm text-muted-foreground">Next</span>
            <span className="font-display text-2xl text-foreground">{next.title} →</span>
          </Link>
        ) : null}
      </article>

      {/* Contents rail: this is a Read surface and several of these pages are long.
          The current section highlights as the reader scrolls (useActiveHeading) --
          a real reading aid, not just a static jump-list. */}
      <nav aria-label="On this page" className="hidden lg:block">
        <div className="sticky top-20">
          <p className="text-sm text-muted-foreground">On this page</p>
          <ul className="mt-4 space-y-1 border-l border-border">
            {headings.map((h) => {
              const id = slugify(h.text)
              const isActive = activeHeading === id
              return (
                <li key={h.text}>
                  <a
                    href={`#${id}`}
                    className={cn(
                      "-ml-px block border-l py-1 pl-4 text-sm transition-colors",
                      isActive
                        ? "border-foreground font-medium text-foreground"
                        : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
                    )}
                  >
                    {h.text}
                  </a>
                </li>
              )
            })}
          </ul>
        </div>
      </nav>
    </div>
  )
}
