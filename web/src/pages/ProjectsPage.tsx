import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createProject, listProjects } from "@/api/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import type { Project } from "@/api/types"

function slugify(title: string): string {
  return title
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
}

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

function NewProjectInline({ onDone }: { onDone: (projectId: string) => void }) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState("")
  const [projectId, setProjectId] = useState("")
  const [studioId, setStudioId] = useState("studio-1")
  const [idTouched, setIdTouched] = useState(false)
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: (project) => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] })
      onDone(project.project_id)
    },
  })

  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        New project
      </Button>
    )
  }

  return (
    <form
      className="max-w-sm space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        if (!title.trim() || !projectId.trim() || !studioId.trim()) return
        mutation.mutate({ project_id: projectId.trim(), studio_id: studioId.trim(), title: title.trim() })
      }}
    >
      <Input
        autoFocus
        placeholder="Project title"
        value={title}
        onChange={(e) => {
          setTitle(e.target.value)
          if (!idTouched) setProjectId(slugify(e.target.value))
        }}
      />
      <Input
        placeholder="project-id"
        value={projectId}
        onChange={(e) => {
          setIdTouched(true)
          setProjectId(e.target.value)
        }}
        className="font-mono"
      />
      <Input placeholder="studio-id" value={studioId} onChange={(e) => setStudioId(e.target.value)} />
      {mutation.isError && (
        <p className="text-sm text-destructive">
          {mutation.error instanceof Error ? mutation.error.message : "Couldn't create project"}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" disabled={mutation.isPending}>
          Create
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

export function ProjectsPage() {
  const navigate = useNavigate()
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
      <h1 className="mb-6 font-display text-3xl text-foreground">Projects</h1>

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
        <div className="flex flex-col items-start gap-4">
          <p className="text-sm text-muted-foreground">No projects yet.</p>
          <NewProjectInline onDone={(id) => id && navigate(`/app/projects/${id}`)} />
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
    </div>
  )
}
