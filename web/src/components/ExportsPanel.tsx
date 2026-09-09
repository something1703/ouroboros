// PHASE_08.md §8.5: E&O evidence pack, fact-check report, and clearance-log exports.
// Visible to every role, including producer -- exports are read-only, the one thing
// producer's otherwise mostly-locked-out role can always trigger.
import { Download } from "lucide-react"
import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import {
  exportClearanceLog,
  exportEoPack,
  exportFactcheckReport,
} from "@/api/client"
import { Button } from "@/components/ui/button"

type ExportKind = "eo-pack" | "factcheck-report" | "clearance-sheet"

// Each row previously read as a flat bank of buttons with an unlabelled pile of
// status lines below it -- nothing tied a given "ready" link back to which export
// it belonged to except position, and nobody was told what any of the three
// files actually contain before generating one. Paired label + description +
// action per row fixes both at once.
const EXPORTS: { kind: ExportKind; label: string; description: string }[] = [
  {
    kind: "eo-pack",
    label: "E&O Evidence Pack",
    description:
      "PDF for an insurer or legal review: every legal claim with its full evidence trail — citations, confidence, and risk rationale per field.",
  },
  {
    kind: "factcheck-report",
    label: "Fact-Check Report",
    description:
      "PDF, timecode-ordered: every factual claim's verdict and corrected wording, for narration or on-screen text accuracy.",
  },
  {
    kind: "clearance-sheet",
    label: "Clearance Log",
    description:
      "CSV, one row per legal claim: rights holder, contact, status, and risk — opens in Sheets or Excel for a production coordinator to work from.",
  },
]

const EXPORT_FN: Record<ExportKind, (projectId: string) => Promise<{ url: string }>> = {
  "eo-pack": exportEoPack,
  "factcheck-report": exportFactcheckReport,
  "clearance-sheet": exportClearanceLog,
}

export function ExportsPanel({ projectId }: { projectId: string }) {
  const [links, setLinks] = useState<Partial<Record<ExportKind, string>>>({})
  const [errors, setErrors] = useState<Partial<Record<ExportKind, string>>>({})
  const [pending, setPending] = useState<ExportKind | null>(null)

  const mutation = useMutation({
    mutationFn: (kind: ExportKind) => EXPORT_FN[kind](projectId),
    onMutate: (kind: ExportKind) => {
      setPending(kind)
      setErrors((prev) => ({ ...prev, [kind]: undefined }))
      setLinks((prev) => ({ ...prev, [kind]: undefined }))
    },
    onSuccess: (res, kind) => {
      setLinks((prev) => ({ ...prev, [kind]: res.url }))
      setPending(null)
    },
    onError: (err, kind) => {
      setErrors((prev) => ({
        ...prev,
        [kind]: err instanceof Error ? err.message : "Couldn't generate this export.",
      }))
      setPending(null)
    },
  })

  return (
    <section className="border-t border-border pt-4">
      <h2 className="text-base font-medium text-foreground">Exports</h2>
      <ul className="mt-3 divide-y divide-border">
        {EXPORTS.map(({ kind, label, description }) => {
          const url = links[kind]
          const error = errors[kind]
          const isPending = pending === kind
          return (
            <li key={kind} className="flex flex-wrap items-center justify-between gap-3 py-3">
              <div className="min-w-0 max-w-[52ch] pr-4">
                <p className="text-sm font-medium text-foreground">{label}</p>
                <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
                {error && <p className="mt-1 text-sm text-destructive">{error}</p>}
              </div>

              {/* A real button in every state, never a bare hyperlink -- "ready"
                  is still an action (open the file), not a citation. */}
              {url ? (
                <Button asChild size="sm" variant="secondary">
                  <a href={url} target="_blank" rel="noreferrer">
                    <Download aria-hidden />
                    Open
                  </a>
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={isPending}
                  onClick={() => mutation.mutate(kind)}
                >
                  {isPending ? "Generating…" : error ? "Try again" : "Generate"}
                </Button>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
