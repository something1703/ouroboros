import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { listProjects } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export function ProjectsPage() {
  const { data: projects, isLoading, isError } = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  })

  return (
    <div className="p-6">
      <h1 className="mb-6 font-display text-2xl text-foreground">Projects</h1>

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-28 rounded-lg" />
          ))}
        </div>
      )}

      {isError && <p className="text-sm text-destructive">Couldn't load projects.</p>}

      {projects?.length === 0 && (
        <p className="text-sm text-muted-foreground">No projects yet.</p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects?.map((project) => (
          <Link key={project.project_id} to={`/projects/${project.project_id}`}>
            <Card className="transition-colors hover:border-primary">
              <CardHeader>
                <CardTitle className="font-display text-lg">{project.title}</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                <p>{project.studio_id}</p>
                {project.release_date && (
                  <p className="font-mono text-xs">{project.release_date}</p>
                )}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
