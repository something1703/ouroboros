// Mirrors services/dashboard_api/main.py's real Pydantic response models. Kept as
// plain types (not generated), matching the exact field names/optionality confirmed
// against the live backend this same session built.

export interface Project {
  project_id: string
  studio_id: string
  title: string
  release_date: string | null // ISO date
  shooting_countries: string[]
  distribution_territories: string[]
  budget_cap_usd: number
  created_at: string // ISO datetime
}

export type Role = "legal" | "editorial" | "producer"

export interface UserContext {
  email: string
  role: Role
}

export type Cadence = "1h" | "1d" | "1w"

export interface MetricsResponse {
  reality_drift: number | null
  drift_7d: number | null
  last_change_at: string | null
  spend_usd: number | null
  counts_by_status: Record<string, number>
  counts_by_risk: Record<string, number>
  days_to_release: number
  current_cadence: Cadence
}

// Real shape is `list[dict[str, object]]` server-side (Projector.list_events reads
// raw Firestore docs) -- `at` is the one field every event is guaranteed to have,
// since `next_before` is threaded from it.
export interface EventEntry {
  at: string
  [key: string]: unknown
}

export interface EventsFeedResponse {
  events: EventEntry[]
  next_before: string | null
}

export type RunMode = "clear" | "truecut" | "ask"

export interface StartRunRequest {
  asset_id: string
  mode?: RunMode
}

export interface StartRunResponse {
  run_id: string
}

export interface TriggerAllResponse {
  total: number
  triggered: number
  errors: { monitor_id: string; error: string }[]
}

export interface Asset {
  asset_id: string
  project_id: string
  kind: "script" | "cut"
  gcs_uri: string
  ingested_at: string | null
}
