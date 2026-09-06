import { useState } from "react"
import { Menu, X } from "lucide-react"
import { Link, NavLink, Outlet } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const NAV_LINKS = [
  { to: "/how-it-works", label: "How it works" },
  { to: "/docs", label: "Docs" },
  { to: "/resources", label: "Resources" },
]

export function MarketingShell() {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      {/*
        A slim, fixed-height bar (h-14, down from an organic ~4.5rem py-4 shell)
        reads as engineered rather than assembled -- the height doesn't float with
        whatever the logo's line-height happens to be. Nav items get a pill
        hover/active background (bg-accent) rather than only a color shift: DESIGN.md
        reserves the brand accent for one signal per view, and this header already
        spends that signal on "Open dashboard" -- so the active route is neutral, not
        orange, exactly per the ring/button/nav/focus-ring "pick one" rule.
      */}
      <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-sm">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <Link
            to="/"
            className="flex items-center gap-2 tracking-tight"
            onClick={() => setMenuOpen(false)}
          >
            <img src="/logo.svg" alt="" className="h-6 w-6" />
            <span className="font-display text-[1.05rem] leading-none">Ouroboros</span>
          </Link>

          <nav className="hidden items-center gap-1 md:flex">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  cn(
                    "rounded-full px-3.5 py-1.5 text-[0.9rem] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                    isActive && "bg-accent text-foreground",
                  )
                }
              >
                {link.label}
              </NavLink>
            ))}
            <Button asChild size="sm" className="ml-3">
              <Link to="/app">Open dashboard</Link>
            </Button>
          </nav>

          <button
            type="button"
            className="rounded-full p-1.5 text-foreground hover:bg-accent md:hidden"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen((v) => !v)}
          >
            {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>

        {menuOpen && (
          <nav className="flex flex-col gap-1 border-t border-border px-4 py-3 md:hidden">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "rounded-lg px-3 py-2.5 text-[0.95rem] font-medium text-muted-foreground hover:bg-accent hover:text-foreground",
                    isActive && "bg-accent text-foreground",
                  )
                }
              >
                {link.label}
              </NavLink>
            ))}
            <Link
              to="/app"
              onClick={() => setMenuOpen(false)}
              className="mt-1 rounded-lg bg-primary px-3 py-2.5 text-center text-[0.95rem] font-medium text-primary-foreground"
            >
              Open dashboard
            </Link>
          </nav>
        )}
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-10 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <img src="/logo.svg" alt="" className="h-5 w-5" />
            <span>Ouroboros — research that feeds itself.</span>
          </div>
          <nav className="flex flex-wrap gap-4">
            <Link to="/how-it-works" className="hover:text-foreground">
              How it works
            </Link>
            <Link to="/docs" className="hover:text-foreground">
              Docs
            </Link>
            <Link to="/resources" className="hover:text-foreground">
              Resources
            </Link>
            <a
              href="https://github.com/something1703/ouroboros"
              target="_blank"
              rel="noreferrer"
              className="hover:text-foreground"
            >
              GitHub
            </a>
          </nav>
        </div>
      </footer>
    </div>
  )
}
