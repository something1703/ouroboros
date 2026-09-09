import { useEffect } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom"
import { AuthProvider } from "@/auth/AuthProvider"
import { AppShell } from "@/components/layout/AppShell"
import { MarketingShell } from "@/components/marketing/MarketingShell"
import { DocsArticlePage } from "@/pages/docs/DocsArticlePage"
import { DocsIndexPage } from "@/pages/docs/DocsIndexPage"
import { HowItWorksPage } from "@/pages/marketing/HowItWorksPage"
import { LandingPage } from "@/pages/marketing/LandingPage"
import { ResourcesPage } from "@/pages/marketing/ResourcesPage"
import { ProjectDetailPage } from "@/pages/ProjectDetailPage"
import { ProjectsPage } from "@/pages/ProjectsPage"

const queryClient = new QueryClient()

// The browser only auto-restores scroll on back/forward, not on an in-app
// <Link> navigation -- without this, clicking from one docs article into
// another keeps whatever scroll offset the previous page was left at, so the
// new page appears to "start from below."
function ScrollToTop() {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return null
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ScrollToTop />
        <Routes>
          <Route element={<MarketingShell />}>
            <Route path="/" element={<LandingPage />} />
            <Route path="/how-it-works" element={<HowItWorksPage />} />
            <Route path="/resources" element={<ResourcesPage />} />
            <Route path="/docs" element={<DocsIndexPage />} />
            <Route path="/docs/:slug" element={<DocsArticlePage />} />
          </Route>

          <Route
            path="/app"
            element={
              <AuthProvider>
                <AppShell />
              </AuthProvider>
            }
          >
            <Route index element={<ProjectsPage />} />
            <Route path="projects/:projectId" element={<ProjectDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
