// PHASE_08.md §8.4: a chat drawer on the project page for grounded Q&A over the claim
// ledger, the studio's private corpus, and live web search (services/dashboard_api's
// POST /projects/{id}/ask, synchronous -- unlike /runs's polled run_id).
import { useEffect, useState } from "react"
import { useMutation } from "@tanstack/react-query"
import ReactMarkdown from "react-markdown"
import type { Components } from "react-markdown"
import { askOuroboros } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"

const GUARDRAIL_LINE = "Evidence, not legal advice."

// Real, not a guess: the last two live /ask calls in production took 73s and 113s
// (checked via Cloud Logging httpRequest.latency) -- this is a synchronous call all
// the way down to the agent (Vertex AI Search + the claim ledger + a live Parallel
// search), not a quick lookup. A bare spinner with no time expectation reads as
// broken well before a minute is up.
const WAIT_MESSAGES: { afterSeconds: number; text: string }[] = [
  { afterSeconds: 0, text: "Reading the claim ledger and studio precedent…" },
  { afterSeconds: 15, text: "Searching the live web through Parallel…" },
  { afterSeconds: 40, text: "Still researching — grounded answers can take up to two minutes." },
  { afterSeconds: 80, text: "Almost there — writing up the answer with citations." },
]

function useElapsedSeconds(active: boolean): number {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    if (!active) {
      setSeconds(0)
      return
    }
    const start = Date.now()
    const interval = setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => clearInterval(interval)
  }, [active])
  return seconds
}

function waitMessageFor(seconds: number): string {
  let message = WAIT_MESSAGES[0].text
  for (const entry of WAIT_MESSAGES) {
    if (seconds >= entry.afterSeconds) message = entry.text
  }
  return message
}

const EXAMPLE_PROMPTS = [
  "Can we show a Pepsi sign in the Mumbai scene?",
  "What did we decide about Bohemian Rhapsody last year?",
]

interface Turn {
  question: string
  answer: string
  error?: string
}

// agents/ouroboros/prompts/ask_ouroboros.md's own output schema always ends the
// answer with this exact line -- stripped out here and rendered as a fixed caption
// instead of trusting it to stay visually distinct inside arbitrary markdown.
function stripGuardrail(answer: string): string {
  const trimmed = answer.trimEnd()
  return trimmed.endsWith(GUARDRAIL_LINE)
    ? trimmed.slice(0, trimmed.length - GUARDRAIL_LINE.length).trimEnd()
    : trimmed
}

// Answers are LLM-authored markdown (headers, bold, citation lists) -- no Tailwind
// typography plugin in this project, so each element maps to the same utility-class
// vocabulary the rest of the app already uses (text-foreground, text-muted-foreground,
// border-border) rather than pulling in a whole prose stylesheet for one drawer.
const MARKDOWN_COMPONENTS: Components = {
  h1: (props) => <p className="mt-3 text-sm font-semibold text-foreground first:mt-0" {...props} />,
  h2: (props) => <p className="mt-3 text-sm font-semibold text-foreground first:mt-0" {...props} />,
  h3: (props) => <p className="mt-3 text-sm font-semibold text-foreground first:mt-0" {...props} />,
  p: (props) => <p className="mt-2 text-sm leading-relaxed text-foreground first:mt-0" {...props} />,
  strong: (props) => <strong className="font-semibold text-foreground" {...props} />,
  em: (props) => <em className="text-muted-foreground" {...props} />,
  ul: (props) => <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-foreground" {...props} />,
  ol: (props) => <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-foreground" {...props} />,
  li: (props) => <li className="text-sm text-foreground" {...props} />,
  blockquote: (props) => (
    <blockquote
      className="mt-2 border-l border-border pl-3 text-sm text-muted-foreground italic"
      {...props}
    />
  ),
  a: (props) => (
    <a
      className="text-foreground underline decoration-border underline-offset-2 hover:decoration-foreground"
      target="_blank"
      rel="noreferrer"
      {...props}
    />
  ),
  code: (props) => (
    <code className="rounded bg-accent px-1 py-0.5 font-mono text-xs text-foreground" {...props} />
  ),
  hr: () => <hr className="my-3 border-border" />,
}

export function AskDrawer({
  projectId,
  open,
  onClose,
}: {
  projectId: string
  open: boolean
  onClose: () => void
}) {
  const [question, setQuestion] = useState("")
  const [turns, setTurns] = useState<Turn[]>([])

  const askMutation = useMutation({
    mutationFn: (q: string) => askOuroboros(projectId, { question: q }),
    onSuccess: (res, q) => setTurns((prev) => [...prev, { question: q, answer: res.answer }]),
    onError: (err, q) =>
      setTurns((prev) => [
        ...prev,
        {
          question: q,
          answer: "",
          error: err instanceof Error ? err.message : "Something went wrong",
        },
      ]),
  })

  function ask(raw: string) {
    const trimmed = raw.trim()
    if (!trimmed || askMutation.isPending) return
    setQuestion("")
    askMutation.mutate(trimmed)
  }

  const waitSeconds = useElapsedSeconds(askMutation.isPending)

  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent side="right" className="flex w-full flex-col sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Ask Ouroboros</SheetTitle>
          <SheetDescription>
            Grounded answers from the claim ledger, studio precedent, and live web search.
          </SheetDescription>
        </SheetHeader>

        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 pb-4">
          {turns.length === 0 && !askMutation.isPending && (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">Try asking:</p>
              {EXAMPLE_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => ask(prompt)}
                  className="block w-full rounded-md border border-border px-3 py-2 text-left text-sm text-foreground transition-colors hover:bg-accent"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}

          {turns.map((turn, i) => (
            <div key={i} className="space-y-2 border-t border-border pt-4 first:border-0 first:pt-0">
              <p className="text-sm font-medium text-foreground">{turn.question}</p>
              {turn.error ? (
                <p className="text-sm text-destructive">{turn.error}</p>
              ) : (
                <div>
                  <ReactMarkdown components={MARKDOWN_COMPONENTS}>
                    {stripGuardrail(turn.answer)}
                  </ReactMarkdown>
                  <p className="mt-2 text-sm text-muted-foreground italic">{GUARDRAIL_LINE}</p>
                </div>
              )}
            </div>
          ))}

          {askMutation.isPending && (
            <div className="space-y-3 border-t border-border pt-4 first:border-0 first:pt-0">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm text-muted-foreground">{waitMessageFor(waitSeconds)}</p>
                <span className="shrink-0 font-mono text-xs text-muted-foreground">
                  {waitSeconds}s
                </span>
              </div>
              <Skeleton className="h-16 w-full" />
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 border-t border-border p-4">
          <Input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") ask(question)
            }}
            placeholder="Ask about a claim, precedent, or risk..."
            disabled={askMutation.isPending}
          />
          <Button size="sm" onClick={() => ask(question)} disabled={askMutation.isPending}>
            Ask
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
