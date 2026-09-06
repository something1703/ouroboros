import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { getClaimDetail, overrideClaim } from "@/api/client"
import { useAuth } from "@/auth/AuthProvider"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import type { Citation, ClaimDetail, RiskLevel, VerificationStatus } from "@/api/types"

const RISK_OPTIONS: RiskLevel[] = ["none", "low", "medium", "high", "blocking"]
const STATUS_OPTIONS: VerificationStatus[] = [
  "pending",
  "triaged",
  "verifying",
  "verified",
  "escalated",
  "error",
  "stale",
]

function fieldLabel(field: string): string {
  return field.replace(/_/g, " ")
}

function riskDotColor(level: RiskLevel | null): string {
  if (level === "blocking" || level === "high") return "var(--destructive)"
  if (level === "medium") return "var(--brand)"
  return "var(--muted-foreground)"
}

// Numbers every citation across the latest evidence's field basis once, so "[n]"
// stays consistent between the field list and the citation list below it.
function useCitationIndex(detail: ClaimDetail | undefined) {
  return useMemo(() => {
    const latest = detail?.evidence_history.at(-1)
    const index = new Map<string, number>()
    const ordered: Citation[] = []
    for (const basis of latest?.basis ?? []) {
      for (const citation of basis.citations) {
        if (!index.has(citation.url)) {
          index.set(citation.url, ordered.length + 1)
          ordered.push(citation)
        }
      }
    }
    return { index, ordered, latest }
  }, [detail])
}

function OverrideForm({
  projectId,
  claimId,
  claimKind,
  onDone,
}: {
  projectId: string
  claimId: string
  claimKind: string
  onDone: () => void
}) {
  const [status, setStatus] = useState<VerificationStatus | "">("")
  const [riskLevel, setRiskLevel] = useState<RiskLevel | "">("")
  const [note, setNote] = useState("")
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () =>
      overrideClaim(projectId, claimId, {
        ...(status ? { status } : {}),
        ...(riskLevel ? { risk_level: riskLevel } : {}),
        note,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["claim", claimId] })
      void queryClient.invalidateQueries({ queryKey: ["claims", projectId] })
      onDone()
    },
  })

  return (
    <form
      className="space-y-2 border-t border-border pt-3"
      onSubmit={(e) => {
        e.preventDefault()
        if (!status && !riskLevel) return
        if (!note.trim()) return
        mutation.mutate()
      }}
    >
      <p className="text-xs font-medium text-foreground">Human override ({claimKind})</p>
      <div className="flex gap-2">
        <Select value={status} onValueChange={(v) => setStatus(v as VerificationStatus)}>
          <SelectTrigger className="flex-1">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={riskLevel} onValueChange={(v) => setRiskLevel(v as RiskLevel)}>
          <SelectTrigger className="flex-1">
            <SelectValue placeholder="Risk level" />
          </SelectTrigger>
          <SelectContent>
            {RISK_OPTIONS.map((r) => (
              <SelectItem key={r} value={r}>
                {r}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <textarea
        required
        placeholder="Note (required)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        className="min-h-16 w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      />
      {mutation.isError && (
        <p className="text-xs text-destructive">
          {mutation.error instanceof Error ? mutation.error.message : "Override failed"}
        </p>
      )}
      <Button type="submit" size="sm" disabled={mutation.isPending}>
        Apply override
      </Button>
    </form>
  )
}

export function ClaimDrawer({
  projectId,
  claimId,
  onClose,
}: {
  projectId: string
  claimId: string | null
  onClose: () => void
}) {
  const { user } = useAuth()
  const { data: detail, isLoading } = useQuery({
    queryKey: ["claim", claimId],
    queryFn: () => getClaimDetail(projectId, claimId!),
    enabled: claimId != null,
  })
  const { index: citationIndex, ordered: citations, latest } = useCitationIndex(detail)

  const canOverride =
    detail != null &&
    ((user.role === "legal" && detail.claim.kind === "legal") ||
      (user.role === "editorial" && detail.claim.kind === "factual"))

  return (
    <Sheet open={claimId != null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-md">
        {isLoading && (
          <div className="space-y-3 p-4">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-32 w-full" />
          </div>
        )}

        {detail && (
          <>
            <SheetHeader>
              <SheetTitle>{detail.claim.entity_text}</SheetTitle>
              <SheetDescription>{detail.claim.claim_text}</SheetDescription>
            </SheetHeader>

            <div className="space-y-4 overflow-y-auto px-4 pb-4">
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge variant="outline" className="capitalize">
                  {detail.claim.kind}
                </Badge>
                <Badge variant="outline" className="capitalize">
                  {detail.claim.category}
                </Badge>
                <Badge variant="outline" className="capitalize">
                  {detail.claim.status}
                </Badge>
                {detail.risk && (
                  <Badge variant="outline" className="gap-1.5">
                    <span
                      className="size-1.5 rounded-full"
                      style={{ backgroundColor: riskDotColor(detail.risk.level) }}
                      aria-hidden
                    />
                    {detail.risk.level}
                  </Badge>
                )}
              </div>

              {detail.claim.jurisdictions.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">Jurisdictions</p>
                  <div className="flex flex-wrap gap-1">
                    {detail.claim.jurisdictions.map((j) => (
                      <Badge key={j} variant="secondary" className="font-mono uppercase">
                        {j}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {detail.monitor_status && (
                <p className="text-xs text-muted-foreground">
                  Monitor: <span className="font-mono">{detail.monitor_status}</span>
                </p>
              )}

              {detail.claim.prior_production_note && (
                <p className="rounded-lg border border-border bg-muted/40 p-2 text-xs text-muted-foreground">
                  Parallel consulted Ouroboros ledger: get_prior_decisions —{" "}
                  {detail.claim.prior_production_note}
                </p>
              )}

              {latest && (
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">
                    Evidence (cycle {latest.cycle}, {latest.overall_confidence} confidence)
                  </p>
                  <ul className="space-y-2">
                    {latest.basis.map((basis) => (
                      <li key={basis.field} className="text-xs">
                        <span className="font-medium text-foreground capitalize">
                          {fieldLabel(basis.field)}
                        </span>{" "}
                        <span className="text-muted-foreground capitalize">
                          ({basis.confidence})
                        </span>
                        <p className="text-muted-foreground">
                          {basis.reasoning}{" "}
                          {basis.citations.map((c) => (
                            <a
                              key={c.url}
                              href={c.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-primary hover:underline"
                            >
                              [{citationIndex.get(c.url)}]
                            </a>
                          ))}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {citations.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">Citations</p>
                  <ol className="space-y-1 text-xs">
                    {citations.map((c, i) => (
                      <li key={c.url}>
                        <a
                          href={c.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-primary hover:underline"
                        >
                          [{i + 1}] {c.url}
                        </a>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {detail.history.length > 0 && (
                <div>
                  <p className="mb-1 text-xs font-medium text-muted-foreground">
                    Verification history
                  </p>
                  <ul className="space-y-1.5">
                    {detail.history.map((event) => (
                      <li key={event.event_id} className="text-xs text-muted-foreground">
                        <span className="font-mono">{new Date(event.at).toLocaleString()}</span>{" "}
                        — {event.actor}: {event.from_status ?? "—"} → {event.to_status}
                        {event.note && <span className="italic"> ({event.note})</span>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {canOverride && (
                <OverrideForm
                  projectId={projectId}
                  claimId={detail.claim.claim_id}
                  claimKind={detail.claim.kind}
                  onDone={onClose}
                />
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
