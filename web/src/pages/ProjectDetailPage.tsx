import { useMemo, useState } from "react"
import { useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { getMetrics, getProject, listAssets, startRun, triggerAllMonitors } from "@/api/client"
import { useAuth } from "@/auth/AuthProvider"
import { TopBar } from "@/components/layout/TopBar"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import type { RunMode } from "@/api/types"

export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  if (!projectId) return null
  return <ProjectDetail projectId={projectId} />
}

function CountTiles({ title, counts }: { title: string; counts: Record<string, number> }) {
  const entries = Object.entries(counts)
  return (
    <div>
      <h2 className="mb-2 text-sm font-medium text-muted-foreground">{title}</h2>
      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing yet.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {entries.map(([key, count]) => (
            <Card key={key}>
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-normal text-muted-foreground capitalize">
                  {key}
                </CardTitle>
              </CardHeader>
              <CardContent className="font-mono text-2xl">{count}</CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
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
    },
    onError: (err) => setActionMessage(err instanceof Error ? err.message : "Trigger failed"),
  })

  if (projectQuery.isLoading || metricsQuery.isLoading) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-16 w-full" />
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
    <div>
      {metrics && <TopBar title={project.title} metrics={metrics} />}

      <div className="space-y-6 p-6">
        <CountTiles title="By status" counts={metrics?.counts_by_status ?? {}} />
        <CountTiles title="By risk" counts={metrics?.counts_by_risk ?? {}} />

        <Card>
          <CardHeader>
            <CardTitle>Quick actions</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-2">
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
            {actionMessage && (
              <p className="w-full text-xs text-muted-foreground">{actionMessage}</p>
            )}
          </CardContent>
        </Card>

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
    </div>
  )
}
