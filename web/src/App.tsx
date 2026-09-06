import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Route, Routes } from "react-router-dom"
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

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
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
