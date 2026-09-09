import { useState } from "react"
import { Plus } from "lucide-react"
import { NavLink, useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { listProjects } from "@/api/client"
import { useAuth } from "@/auth/AuthProvider"
import { NewProjectDialog } from "@/components/NewProjectDialog"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { ViewableRole } from "@/api/types"

const VIEW_AS_OPTIONS: { value: ViewableRole | "judge"; label: string }[] = [
  { value: "judge", label: "Full access" },
  { value: "legal", label: "Legal" },
  { value: "editorial", label: "Editorial" },
  { value: "producer", label: "Producer" },
]

export function LeftNav({ onNavigate }: { onNavigate?: () => void }) {
  const { user, signOut, viewAsRole, setViewAsRole } = useAuth()
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const {
    data: projects,
    isLoading,
    isError,
  } = useQuery({
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
          {isError && (
            <p className="px-3 py-2 text-sm text-destructive">Couldn't load your projects.</p>
          )}
          {!isLoading && !isError && projects?.length === 0 && (
            <p className="px-3 py-2 text-sm leading-relaxed text-sidebar-foreground/70">
              No projects yet. Create one below to start extracting and verifying claims.
            </p>
          )}
          {projects?.map((project) => (
            <NavLink
              key={project.project_id}
              to={`/app/projects/${project.project_id}`}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  "block truncate rounded-md px-3 py-1.5 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent",
                  isActive && "bg-sidebar-accent font-medium",
                )
              }
            >
              {project.title}
            </NavLink>
          ))}
        </div>

        {/* Creation lives in a dialog, not inline here: the form needs seven labelled
            fields with real explanations, which a 16rem rail cannot hold legibly. */}
        <div className="mt-1">
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="flex w-full items-center gap-1.5 rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
          >
            <Plus className="size-4" />
            New project
          </button>
        </div>
      </nav>

      <NewProjectDialog
        open={creating}
        onOpenChange={setCreating}
        existingIds={projects?.map((p) => p.project_id) ?? []}
        onCreated={(projectId) => {
          setCreating(false)
          navigate(`/app/projects/${projectId}`)
          onNavigate?.()
        }}
      />

      <div className="border-t border-sidebar-border px-4 py-3">
        <div className="mb-2 flex items-center gap-2">
          <Avatar className="size-7">
            <AvatarFallback className="text-xs">
              {user.email.slice(0, 2).toUpperCase()}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-sidebar-foreground">{user.email}</p>
            {!user.is_judge && (
              <p className="text-sm text-muted-foreground capitalize">{user.role}</p>
            )}
          </div>
        </div>
        {user.is_judge && (
          <div className="mb-2">
            <p className="mb-1 text-sm text-muted-foreground">Viewing as</p>
            <Select
              value={viewAsRole ?? "judge"}
              onValueChange={(v) => setViewAsRole(v === "judge" ? null : (v as ViewableRole))}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {VIEW_AS_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        <Button variant="ghost" size="sm" className="w-full justify-start" onClick={signOut}>
          Sign out
        </Button>
      </div>
    </aside>
  )
}
