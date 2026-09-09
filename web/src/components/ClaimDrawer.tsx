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

// Signal Red stays reserved for blocking/high, per DESIGN.md's naming of the rule.
// Medium risk is a hairline-toned dot, not the brand accent -- the accent is
// rationed to one signal per view, and a worklist can show a dozen mediums in one
// glance.
function riskDotColor(level: RiskLevel | null): string {
  if (level === "blocking" || level === "high") return "var(--destructive)"
  return "var(--muted-foreground)"
}

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

function Section({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <section className="border-t border-border pt-4">
      <h3 className="text-sm font-medium text-foreground">{label}</h3>
      <div className="mt-2 text-sm text-foreground/90">{children}</div>
    </section>
  )
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
      className="space-y-2.5"
      onSubmit={(e) => {
        e.preventDefault()
        if (!status && !riskLevel) return
        if (!note.trim()) return
        mutation.mutate()
      }}
    >
      <p className="text-sm text-muted-foreground">Applies to this {claimKind} claim only.</p>
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
        <p className="text-sm text-destructive">
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
  const {
    data: detail,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["claim", claimId],
    queryFn: () => getClaimDetail(projectId, claimId!),
    enabled: claimId != null,
  })
  const { index: citationIndex, ordered: citations, latest } = useCitationIndex(detail)

  const canOverride =
    detail != null &&
    (user.role === "judge" ||
      (user.role === "legal" && detail.claim.kind === "legal") ||
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

        {isError && (
          <div className="flex h-full flex-col items-start justify-center gap-3 p-6">
            <SheetTitle className="sr-only">Couldn't load this claim</SheetTitle>
            <p className="text-sm text-foreground">Couldn't load this claim.</p>
            <Button size="sm" variant="outline" onClick={() => void refetch()}>
              Try again
            </Button>
          </div>
        )}

        {detail && (
          <>
            <SheetHeader>
              <SheetTitle>{detail.claim.entity_text}</SheetTitle>
              <SheetDescription>{detail.claim.claim_text}</SheetDescription>
            </SheetHeader>

            <div className="space-y-4 overflow-y-auto px-4 pb-6">
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
                  <Badge variant="outline" className="gap-1.5 capitalize">
                    <span
                      className="size-1.5 rounded-full"
                      style={{ backgroundColor: riskDotColor(detail.risk.level) }}
                      aria-hidden
                    />
                    {detail.risk.level}
                  </Badge>
                )}
                {detail.monitor_status && (
                  <Badge variant="outline" className="capitalize">
                    Monitor {detail.monitor_status}
                  </Badge>
                )}
              </div>

              {detail.claim.jurisdictions.length > 0 && (
                <Section label="Jurisdictions">
                  <div className="flex flex-wrap gap-1">
                    {detail.claim.jurisdictions.map((j) => (
                      <Badge key={j} variant="outline" className="font-mono">
                        {j}
                      </Badge>
                    ))}
                  </div>
                </Section>
              )}

              {detail.claim.prior_production_note && (
                <Section label="Prior production">
                  <p>{detail.claim.prior_production_note}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Surfaced from the studio's own ledger via Parallel Memory.
                  </p>
                </Section>
              )}

              {latest && (
                <Section
                  label={`Evidence — cycle ${latest.cycle}, ${latest.overall_confidence} confidence`}
                >
                  <ul className="space-y-3">
                    {latest.basis.map((basis) => (
                      <li key={basis.field}>
                        <p className="text-sm text-foreground">
                          <span className="font-medium capitalize">{fieldLabel(basis.field)}</span>{" "}
                          <span className="text-muted-foreground">({basis.confidence})</span>
                        </p>
                        <p className="mt-0.5 text-foreground/90">
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
                </Section>
              )}

              {citations.length > 0 && (
                <Section label="Citations">
                  <ol className="space-y-1">
                    {citations.map((c, i) => (
                      <li key={c.url} className="truncate">
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
                </Section>
              )}

              {detail.history.length > 0 && (
                <Section label="Verification history">
                  <ul className="space-y-1.5">
                    {detail.history.map((event) => (
                      <li key={event.event_id} className="text-muted-foreground">
                        <span className="font-mono">
                          {new Date(event.at).toLocaleString(undefined, {
                            dateStyle: "short",
                            timeStyle: "short",
                          })}
                        </span>{" "}
                        — {event.actor}: {event.from_status ?? "—"} → {event.to_status}
                        {event.note && <span className="italic"> ({event.note})</span>}
                      </li>
                    ))}
                  </ul>
                </Section>
              )}

              {canOverride && (
                <Section label="Human override">
                  <OverrideForm
                    projectId={projectId}
                    claimId={detail.claim.claim_id}
                    claimKind={detail.claim.kind}
                    onDone={onClose}
                  />
                </Section>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
