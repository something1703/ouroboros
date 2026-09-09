import { useState } from "react"
import { Plus } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { listProjects } from "@/api/client"
import { NewProjectDialog } from "@/components/NewProjectDialog"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { Project } from "@/api/types"

// Release date carries real urgency (it drives monitor cadence everywhere else in
// this product), so the list ranks by it instead of sitting in an unordered tile
// grid -- projects with a known date soonest first, undated projects last.
function sortByUrgency(projects: Project[]): Project[] {
  return [...projects].sort((a, b) => {
    if (!a.release_date && !b.release_date) return a.title.localeCompare(b.title)
    if (!a.release_date) return 1
    if (!b.release_date) return -1
    return a.release_date.localeCompare(b.release_date)
  })
}

export function ProjectsPage() {
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const {
    data: projects,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  })

  return (
    <div className="p-6">
      {/* The action lives in the page header rather than only in the empty state --
          it used to disappear entirely as soon as you had one project. Suppressed
          while the list is empty, where the empty state's own CTA says it better
          and three competing "New project" buttons would just be noise. */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-3xl text-foreground">Projects</h1>
        {projects && projects.length > 0 && (
          <Button size="sm" variant="outline" onClick={() => setCreating(true)}>
            <Plus className="size-4" />
            New project
          </Button>
        )}
      </div>

      {isLoading && (
        <div className="space-y-0 border-t border-border">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="border-b border-border py-4">
              <Skeleton className="h-5 w-48" />
            </div>
          ))}
        </div>
      )}

      {isError && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-destructive">Couldn't load your projects.</p>
          <Button size="sm" variant="outline" onClick={() => void refetch()}>
            Try again
          </Button>
        </div>
      )}

      {!isLoading && !isError && projects?.length === 0 && (
        <div className="flex flex-col items-start gap-4 border-t border-border pt-6">
          <div className="max-w-[56ch] space-y-1.5">
            <p className="text-base font-medium text-foreground">No projects yet</p>
            <p className="text-sm leading-relaxed text-muted-foreground">
              A project holds one production: its script and cut, every claim Ouroboros
              extracts from them, and the monitors that keep watching those claims after
              they're verified. Create one to start.
            </p>
          </div>
          <Button size="sm" onClick={() => setCreating(true)}>
            <Plus className="size-4" />
            New project
          </Button>
        </div>
      )}

      {!isLoading && !isError && projects && projects.length > 0 && (
        <ul className="border-t border-border">
          {sortByUrgency(projects).map((project) => (
            <li key={project.project_id} className="border-b border-border">
              <Link
                to={`/app/projects/${project.project_id}`}
                className="flex items-baseline justify-between gap-6 py-4 transition-colors hover:bg-accent/40 focus-visible:bg-accent/40"
              >
                <div className="min-w-0">
                  <p className="truncate text-base font-medium text-foreground">{project.title}</p>
                  <p className="mt-0.5 text-sm text-muted-foreground">{project.studio_id}</p>
                </div>
                {project.release_date && (
                  <span className="shrink-0 font-mono text-sm text-muted-foreground">
                    {project.release_date}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}

      <NewProjectDialog
        open={creating}
        onOpenChange={setCreating}
        existingIds={projects?.map((p) => p.project_id) ?? []}
        onCreated={(projectId) => {
          setCreating(false)
          navigate(`/app/projects/${projectId}`)
        }}
      />
    </div>
  )
}
