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
  const [errors, setErrors] = useState<Partial<Record<ExportKind, string>>>({})
  const [pending, setPending] = useState<ExportKind | null>(null)

  const mutation = useMutation({
    mutationFn: (kind: ExportKind) => EXPORT_FN[kind](projectId),
    onMutate: (kind: ExportKind) => {
      setPending(kind)
      setErrors((prev) => ({ ...prev, [kind]: undefined }))
    },
    onSuccess: (res, kind) => {
      setLinks((prev) => ({ ...prev, [kind]: res.url }))
      setPending(null)
    },
    onError: (err, kind) => {
      setErrors((prev) => ({
        ...prev,
        [kind]: err instanceof Error ? err.message : "Export failed",
      }))
      setPending(null)
    },
  })

  return (
    <section className="border-t border-border pt-4">
      <h2 className="text-base font-medium text-foreground">Exports</h2>
      <div className="mt-3 flex flex-wrap gap-2">
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
      <ul className="mt-2 space-y-1">
        {EXPORTS.map(({ kind, label }) =>
          links[kind] ? (
            <li key={kind} className="text-sm">
              <a
                href={links[kind]}
                target="_blank"
                rel="noreferrer"
                className="text-primary underline underline-offset-2"
              >
                {label} ready — open
              </a>
            </li>
          ) : errors[kind] ? (
            <li key={kind} className="text-sm text-destructive">
              {label}: {errors[kind]}
            </li>
          ) : null,
        )}
      </ul>
    </section>
  )
}
