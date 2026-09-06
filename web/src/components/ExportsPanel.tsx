// PHASE_08.md §8.5: E&O evidence pack, fact-check report, and clearance-log exports.
// Visible to every role, including producer -- exports are read-only, the one thing
// producer's otherwise mostly-locked-out role can always trigger.
import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import {
  exportClearanceSheet,
  exportEoPack,
  exportFactcheckReport,
} from "@/api/client"
import { Button } from "@/components/ui/button"

type ExportKind = "eo-pack" | "factcheck-report" | "clearance-sheet"

const EXPORTS: { kind: ExportKind; label: string }[] = [
  { kind: "eo-pack", label: "E&O Evidence Pack" },
  { kind: "factcheck-report", label: "Fact-Check Report" },
  { kind: "clearance-sheet", label: "Clearance Log (Sheet)" },
]

const EXPORT_FN: Record<ExportKind, (projectId: string) => Promise<{ url: string }>> = {
  "eo-pack": exportEoPack,
  "factcheck-report": exportFactcheckReport,
  "clearance-sheet": exportClearanceSheet,
}

export function ExportsPanel({ projectId }: { projectId: string }) {
  const [links, setLinks] = useState<Partial<Record<ExportKind, string>>>({})
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<ExportKind | null>(null)

  const mutation = useMutation({
    mutationFn: (kind: ExportKind) => EXPORT_FN[kind](projectId),
    onMutate: (kind: ExportKind) => {
      setPending(kind)
      setError(null)
    },
    onSuccess: (res, kind) => {
      setLinks((prev) => ({ ...prev, [kind]: res.url }))
      setPending(null)
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Export failed")
      setPending(null)
    },
  })

  return (
    <section className="space-y-3 rounded-md border border-border p-4">
      <h2 className="text-sm font-medium text-foreground">Exports</h2>
      <div className="flex flex-wrap gap-2">
        {EXPORTS.map(({ kind, label }) => (
          <Button
            key={kind}
            size="sm"
            variant="outline"
            disabled={pending === kind}
            onClick={() => mutation.mutate(kind)}
          >
            {pending === kind ? "Generating…" : label}
          </Button>
        ))}
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
      {Object.values(links).some(Boolean) && (
        <ul className="space-y-1">
          {EXPORTS.filter(({ kind }) => links[kind]).map(({ kind, label }) => (
            <li key={kind} className="text-sm">
              <a
                href={links[kind]}
                target="_blank"
                rel="noreferrer"
                className="text-brand underline underline-offset-2"
              >
                {label} ready — open
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
