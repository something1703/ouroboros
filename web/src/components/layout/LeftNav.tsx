import { NavLink } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { listProjects } from "@/api/client"
import { useAuth } from "@/auth/AuthProvider"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

export function LeftNav() {
  const { user, signOut } = useAuth()
  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  })

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex items-center gap-2 px-4 py-4">
        <img src="/logo.svg" alt="" className="h-7 w-7" />
        <span className="font-display text-lg text-sidebar-foreground">Ouroboros</span>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
        {isLoading &&
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="mx-2 my-1 h-7 rounded-md" />
          ))}
        {!isLoading && projects?.length === 0 && (
          <p className="px-3 py-2 text-xs text-sidebar-foreground/60">No projects yet.</p>
        )}
        {projects?.map((project) => (
          <NavLink
            key={project.project_id}
            to={`/projects/${project.project_id}`}
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
