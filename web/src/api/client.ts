// Typed fetch wrapper for services/dashboard_api. Talks to the real deployed API
// (VITE_API_BASE_URL) -- no mock layer, matching this project's own "verify against
// real deployed services" practice.
import type {
  AskRequest,
  AskResponse,
  Asset,
  ClaimDetail,
  ClaimWithRisk,
  CreateProjectRequest,
  EventsFeedResponse,
  ExportResponse,
  FileUrlResponse,
  HumanOverrideRequest,
  MetricsResponse,
  PlaybackResponse,
  Project,
  PublicShowcaseMetrics,
  SegmentsResponse,
  StartRunRequest,
  StartRunResponse,
  TimelineResponse,
  TriggerAllResponse,
  UserContext,
} from "./types"

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string

let authToken: string | null = null
let viewAsRole: string | null = null

// Set by AuthProvider after a successful GIS sign-in / on sign-out. Kept outside
// React state so plain functions below (not hooks) can attach the bearer token.
export function setAuthToken(token: string | null): void {
  authToken = token
}

// Set by AuthProvider when a judge picks a role from the "View as" switcher.
// `services/dashboard_api/auth.py::get_current_user` only honors this header for a
// DASHBOARD_DEMO_OPEN_ACCESS fallback identity -- a real legal/editorial/producer
// user sending it has no effect, so this is safe to always attach.
export function setViewAsRole(role: string | null): void {
  viewAsRole = role
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string>) }
  if (authToken) headers.Authorization = `Bearer ${authToken}`
  if (viewAsRole) headers["X-View-As-Role"] = viewAsRole
  if (init?.body) headers["Content-Type"] = "application/json"

  const res = await fetch(`${BASE_URL}${path}`, { ...init, headers })
  if (!res.ok) {
    const text = await res.text()
    // FastAPI's HTTPException body is `{"detail": "..."}` -- surface just that string
    // when present, since every 401/403 in this API carries a human-readable reason.
    let detail = text
    try {
      const parsed: unknown = JSON.parse(text)
      if (
        parsed &&
        typeof parsed === "object" &&
        "detail" in parsed &&
        typeof (parsed as { detail: unknown }).detail === "string"
      ) {
        detail = (parsed as { detail: string }).detail
      }
    } catch {
      // not JSON -- keep the raw text
    }
    throw new ApiError(res.status, detail || res.statusText)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export function getMe(): Promise<UserContext> {
  return request("/me")
}

// No auth required -- the public marketing site's "live proof" section.
export function getPublicShowcaseMetrics(): Promise<PublicShowcaseMetrics> {
  return request("/public/showcase-metrics")
}

export function listProjects(): Promise<Project[]> {
  return request("/projects")
}

export function getProject(projectId: string): Promise<Project> {
  return request(`/projects/${projectId}`)
}

export function createProject(body: CreateProjectRequest): Promise<Project> {
  return request("/projects", { method: "POST", body: JSON.stringify(body) })
}

export function getMetrics(projectId: string): Promise<MetricsResponse> {
  return request(`/projects/${projectId}/metrics`)
}

export function listAssets(projectId: string): Promise<Asset[]> {
  return request(`/projects/${projectId}/assets`)
}

export function listClaims(projectId: string): Promise<ClaimWithRisk[]> {
  return request(`/projects/${projectId}/claims`)
}

export function getClaimDetail(projectId: string, claimId: string): Promise<ClaimDetail> {
  return request(`/projects/${projectId}/claims/${claimId}`)
}

export function overrideClaim(
  projectId: string,
  claimId: string,
  body: HumanOverrideRequest,
): Promise<ClaimDetail> {
  return request(`/projects/${projectId}/claims/${claimId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  })
}

export function getAssetTimeline(assetId: string): Promise<TimelineResponse> {
  return request(`/assets/${assetId}/timeline`)
}

export function getAssetSegments(assetId: string): Promise<SegmentsResponse> {
  return request(`/assets/${assetId}/segments`)
}

export function getAssetProxy(assetId: string): Promise<PlaybackResponse> {
  return request(`/assets/${assetId}/proxy`)
}

export function getAssetFile(assetId: string): Promise<FileUrlResponse> {
  return request(`/assets/${assetId}/file`)
}

export function getEvents(projectId: string, before?: string): Promise<EventsFeedResponse> {
  const q = before ? `?before=${encodeURIComponent(before)}` : ""
  return request(`/projects/${projectId}/events${q}`)
}

export function startRun(projectId: string, body: StartRunRequest): Promise<StartRunResponse> {
  return request(`/projects/${projectId}/runs`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function triggerAllMonitors(projectId: string): Promise<TriggerAllResponse> {
  return request(`/projects/${projectId}/monitors/trigger-all`, { method: "POST" })
}

export function askOuroboros(projectId: string, body: AskRequest): Promise<AskResponse> {
  return request(`/projects/${projectId}/ask`, {
    method: "POST",
    body: JSON.stringify(body),
  })
}

export function exportEoPack(projectId: string): Promise<ExportResponse> {
  return request(`/projects/${projectId}/exports/eo-pack`, { method: "POST" })
}

export function exportFactcheckReport(projectId: string): Promise<ExportResponse> {
  return request(`/projects/${projectId}/exports/factcheck-report`, { method: "POST" })
}

export function exportClearanceSheet(projectId: string): Promise<ExportResponse> {
  return request(`/projects/${projectId}/exports/clearance-sheet`, { method: "POST" })
}
