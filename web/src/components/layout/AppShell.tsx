import { useState } from "react"
import { Menu } from "lucide-react"
import { Outlet } from "react-router-dom"
import { LeftNav } from "./LeftNav"

export function AppShell() {
  const [navOpen, setNavOpen] = useState(false)

  return (
    <div className="flex h-screen bg-background text-foreground">
      <div className="hidden md:block">
        <LeftNav />
      </div>

      {navOpen && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <LeftNav onNavigate={() => setNavOpen(false)} />
          <button
            type="button"
            aria-label="Close navigation"
            className="flex-1 bg-black/50"
            onClick={() => setNavOpen(false)}
          />
        </div>
      )}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-border px-4 py-3 md:hidden">
          <button
            type="button"
            aria-label="Open navigation"
            className="rounded-md p-1.5 text-foreground hover:bg-muted"
            onClick={() => setNavOpen(true)}
          >
            <Menu className="size-5" />
          </button>
          <img src="/logo.svg" alt="" className="h-5 w-5" />
          <span className="font-display text-sm text-foreground">Ouroboros</span>
        </div>
        <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
