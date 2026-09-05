import { Outlet } from "react-router-dom"
import { LeftNav } from "./LeftNav"

export function AppShell() {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <LeftNav />
      <main className="min-w-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
