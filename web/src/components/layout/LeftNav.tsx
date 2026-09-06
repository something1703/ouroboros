import { useState } from "react"
import { Plus } from "lucide-react"
import { NavLink, useNavigate } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { createProject, listProjects } from "@/api/client"
import { useAuth } from "@/auth/AuthProvider"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

function slugify(title: string): string {
  return title
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
}

function NewProjectForm({ onDone }: { onDone: (projectId: string) => void }) {
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

  return (
    <form
      className="space-y-2 px-2 pb-3"
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
        <p className="text-xs text-destructive">
          {mutation.error instanceof Error ? mutation.error.message : "Couldn't create project"}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={mutation.isPending}>
          Create
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => onDone("")}>
          Cancel
        </Button>
      </div>
    </form>
  )
}

export function LeftNav({ onNavigate }: { onNavigate?: () => void }) {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  })

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex items-center gap-2 px-4 py-4">
        <img src="/logo.svg" alt="" className="h-7 w-7" />
        <span className="font-display text-lg text-sidebar-foreground">Ouroboros</span>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-4">
        <div className="space-y-0.5">
          {isLoading &&
            Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="mx-2 my-1 h-7 rounded-md" />
            ))}
          {!isLoading && projects?.length === 0 && !creating && (
            <p className="px-3 py-2 text-xs text-sidebar-foreground/60">No projects yet.</p>
          )}
          {projects?.map((project) => (
            <NavLink
              key={project.project_id}
              to={`/app/projects/${project.project_id}`}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "block truncate rounded-md px-3 py-1.5 text-sm text-sidebar-foreground/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground",
                  isActive && "bg-sidebar-accent font-medium text-sidebar-foreground",
                )
              }
            >
              {project.title}
            </NavLink>
          ))}
        </div>

        <div className="mt-1">
          {creating ? (
            <NewProjectForm
              onDone={(projectId) => {
                setCreating(false)
                if (projectId) {
                  navigate(`/app/projects/${projectId}`)
                  onNavigate?.()
                }
              }}
            />
          ) : (
            <button
              type="button"
              onClick={() => setCreating(true)}
              className="flex w-full items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-sidebar-foreground/60 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
            >
              <Plus className="size-4" />
              New project
            </button>
          )}
        </div>
      </nav>

      <div className="border-t border-sidebar-border px-4 py-3">
        <div className="mb-2 flex items-center gap-2">
          <Avatar className="size-7">
            <AvatarFallback className="font-mono text-[0.65rem]">
              {user.email.slice(0, 2).toUpperCase()}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs text-sidebar-foreground">{user.email}</p>
            <p className="text-[0.7rem] text-sidebar-foreground/60 capitalize">{user.role}</p>
          </div>
        </div>
        <Button variant="ghost" size="sm" className="w-full justify-start" onClick={signOut}>
          Sign out
        </Button>
      </div>
    </aside>
  )
}
