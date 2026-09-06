import { useEffect, useMemo, useRef, useState } from "react"
import { useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  getMetrics,
  getProject,
  listAssets,
  listClaims,
  startRun,
  triggerAllMonitors,
} from "@/api/client"
import { useAuth } from "@/auth/AuthProvider"
import { DriftHero } from "@/components/layout/TopBar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import type { ClaimWithRisk, RiskLevel, RunMode } from "@/api/types"

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  if (!projectId) return null
  return <ProjectDetail projectId={projectId} />
}

// Worst-to-best, matching packages/claims/enums.py::RISK_LEVEL_ORDER; an unassessed
// claim (no Risk row yet) ranks last, not first -- it isn't known to be risky.
const RISK_RANK: Record<RiskLevel | "unassessed", number> = {
  blocking: 0,
  high: 1,
  medium: 2,
  low: 3,
  none: 4,
  unassessed: 5,
}

function riskDotColor(level: RiskLevel | null): string {
  if (level === "blocking" || level === "high") return "var(--destructive)"
  if (level === "medium") return "var(--brand)"
  return "var(--muted-foreground)"
}

function riskLabel(level: RiskLevel | null): string {
  return level == null ? "Unassessed" : level[0].toUpperCase() + level.slice(1)
}

// The direction contract's fused split-flap-concourse grammar: a claim whose status
// or risk_level differs from the previous fetch flips in place, then settles. Rows
// carry a top-to-bottom stagger (matching row display order, not fetch order) so
// several simultaneous changes cascade down the list rather than flashing at once --
// the one authored motion moment for this page, not scattered per-hover effects.
function useChangedClaims(claims: ClaimWithRisk[] | undefined): Set<string> {
  const previous = useRef<Map<string, string>>(new Map())
  const [changed, setChanged] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!claims) return
    const next = new Set<string>()
    for (const claim of claims) {
      const fingerprint = `${claim.status}:${claim.risk_level}`
      const before = previous.current.get(claim.claim_id)
      if (before !== undefined && before !== fingerprint) next.add(claim.claim_id)
    }
    previous.current = new Map(claims.map((c) => [c.claim_id, `${c.status}:${c.risk_level}`]))
    if (next.size > 0) {
      setChanged(next)
      const timeout = setTimeout(() => setChanged(new Set()), 900 + next.size * 90)
      return () => clearTimeout(timeout)
    }
  }, [claims])

  return changed
}

function ClaimRow({
  claim,
  staggerIndex,
}: {
  claim: ClaimWithRisk
  staggerIndex: number | null
}) {
  return (
    <li
      className="flex items-start gap-3 border-b border-border py-3 last:border-0"
      style={
        staggerIndex != null
          ? {
              animation: "claim-row-flip 0.5s cubic-bezier(0.2, 0.8, 0.2, 1)",
              animationDelay: `${staggerIndex * 90}ms`,
              animationFillMode: "backwards",
              transformOrigin: "top",
            }
          : undefined
      }
    >
      <span
        className="mt-2 size-2 shrink-0 rounded-full"
        style={{ backgroundColor: riskDotColor(claim.risk_level) }}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">{claim.entity_text}</p>
        <p className="truncate text-xs text-muted-foreground">{claim.claim_text}</p>
      </div>
      <span className="shrink-0 text-xs text-muted-foreground capitalize">
        {riskLabel(claim.risk_level)}
      </span>
      <span className="shrink-0 text-xs text-muted-foreground capitalize">{claim.status}</span>
    </li>
  )
}

function ProjectDetail({ projectId }: { projectId: string }) {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  })
  const metricsQuery = useQuery({
    queryKey: ["metrics", projectId],
    queryFn: () => getMetrics(projectId),
  })
  const assetsQuery = useQuery({
    queryKey: ["assets", projectId],
    queryFn: () => listAssets(projectId),
  })
  const claimsQuery = useQuery({
    queryKey: ["claims", projectId],
    queryFn: () => listClaims(projectId),
  })

  const rankedClaims = useMemo(() => {
    const claims = claimsQuery.data ?? []
    return [...claims].sort(
      (a, b) => RISK_RANK[a.risk_level ?? "unassessed"] - RISK_RANK[b.risk_level ?? "unassessed"],
    )
  }, [claimsQuery.data])

  const changedClaims = useChangedClaims(claimsQuery.data)
  const staggerIndexByClaimId = useMemo(() => {
    const indexed = new Map<string, number>()
    let i = 0
    for (const claim of rankedClaims) {
      if (changedClaims.has(claim.claim_id)) indexed.set(claim.claim_id, i++)
    }
    return indexed
  }, [rankedClaims, changedClaims])

  const latestCut = useMemo(() => {
    const cuts = (assetsQuery.data ?? []).filter((a) => a.kind === "cut")
    return cuts.sort((a, b) => (b.ingested_at ?? "").localeCompare(a.ingested_at ?? ""))[0]
  }, [assetsQuery.data])

  const canRun = user.role === "legal" || user.role === "editorial"

  const runMutation = useMutation({
    mutationFn: (mode: Extract<RunMode, "clear" | "truecut">) => {
      if (!latestCut) throw new Error("No cut asset uploaded for this project yet")
      return startRun(projectId, { asset_id: latestCut.asset_id, mode })
    },
    onSuccess: (res, mode) => {
      setActionMessage(`${mode === "clear" ? "CLEAR" : "TRUE CUT"} run started — run_id ${res.run_id}`)
    },
    onError: (err) => setActionMessage(err instanceof Error ? err.message : "Run failed to start"),
  })

  const triggerMutation = useMutation({
    mutationFn: () => triggerAllMonitors(projectId),
    onSuccess: (res) => {
      setActionMessage(`Triggered ${res.triggered}/${res.total} monitor(s)`)
      void queryClient.invalidateQueries({ queryKey: ["metrics", projectId] })
      void queryClient.invalidateQueries({ queryKey: ["claims", projectId] })
    },
    onError: (err) => setActionMessage(err instanceof Error ? err.message : "Trigger failed"),
  })

  if (projectQuery.isLoading || metricsQuery.isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (projectQuery.isError || !projectQuery.data) {
    return <p className="p-6 text-sm text-destructive">Couldn't load this project.</p>
  }

  const project = projectQuery.data
  const metrics = metricsQuery.data

  return (
    <div className="flex min-h-full flex-col">
      <style>{`
        @keyframes claim-row-flip {
          0% { background-color: color-mix(in oklch, var(--brand) 22%, transparent); transform: scaleY(0.92); }
          60% { background-color: color-mix(in oklch, var(--brand) 12%, transparent); transform: scaleY(1.01); }
          100% { background-color: transparent; transform: scaleY(1); }
        }
      `}</style>

      {metrics && <DriftHero title={project.title} metrics={metrics} />}

      <div className="flex-1 space-y-6 p-6 pb-28">
        <section>
          <div className="mb-2 flex items-baseline justify-between">
            <h2 className="text-sm font-medium text-foreground">Needs attention</h2>
            <span className="text-xs text-muted-foreground">{rankedClaims.length} claims</span>
          </div>
          {claimsQuery.isLoading && <Skeleton className="h-32 w-full" />}
          {!claimsQuery.isLoading && rankedClaims.length === 0 && (
            <p className="text-sm text-muted-foreground">No claims ingested yet.</p>
          )}
          {rankedClaims.length > 0 && (
            <ul>
              {rankedClaims.map((claim) => (
                <ClaimRow
                  key={claim.claim_id}
                  claim={claim}
                  staggerIndex={staggerIndexByClaimId.get(claim.claim_id) ?? null}
                />
              ))}
            </ul>
          )}
        </section>

        <Card>
          <CardHeader>
            <CardTitle>Ouroboros feed</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Live event feed — coming in Phase 8.3.
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="sticky bottom-0 flex flex-wrap items-center gap-2 border-t border-border bg-card px-6 py-4">
        {canRun ? (
          <>
            <Button
              size="sm"
              disabled={!latestCut || runMutation.isPending}
              onClick={() => runMutation.mutate("clear")}
            >
              Run CLEAR
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={!latestCut || runMutation.isPending}
              onClick={() => runMutation.mutate("truecut")}
            >
              Run TRUE CUT
            </Button>
            {!latestCut && (
              <span className="text-xs text-muted-foreground">
                Upload a cut before starting a run.
              </span>
            )}
          </>
        ) : (
          <span className="text-xs text-muted-foreground">
            Read-only for producer — legal or editorial can run verification passes.
          </span>
        )}
        <Button
          size="sm"
          variant="outline"
          disabled={triggerMutation.isPending}
          onClick={() => triggerMutation.mutate()}
        >
          Trigger monitors
        </Button>
        {actionMessage && <p className="w-full text-xs text-muted-foreground">{actionMessage}</p>}
      </div>
    </div>
  )
}
