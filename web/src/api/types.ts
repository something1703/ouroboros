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

export interface CreateProjectRequest {
  project_id: string
  studio_id: string
  title: string
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

export type EventKind = "monitor_event" | "reverified" | "risk_changed"

// Real shape is `list[dict[str, object]]` server-side (Projector.list_events reads
// raw Firestore docs written by packages/ledger/projections.py::Projector.event) --
// `at` is the one field every event is guaranteed to have, since `next_before` is
// threaded from it; the rest mirror `event()`'s own doc shape but keep the index
// signature since a raw Firestore doc has no schema enforcement at this layer.
export interface EventEntry {
  at: string
  claim_id?: string
  kind?: EventKind
  summary?: string
  delta?: Record<string, Record<string, unknown>>
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

export type ClaimKind = "legal" | "factual"

export type ClaimCategory =
  | "music"
  | "brand"
  | "person"
  | "location"
  | "artwork"
  | "quote"
  | "event"
  | "statistic"
  | "attribution"
  | "archival"
  | "identity"

export type VerificationStatus =
  | "pending"
  | "triaged"
  | "verifying"
  | "verified"
  | "escalated"
  | "error"
  | "stale"

export type RiskLevel = "none" | "low" | "medium" | "high" | "blocking"

export interface ClaimWithRisk {
  claim_id: string
  project_id: string
  kind: ClaimKind
  category: ClaimCategory
  entity_text: string
  claim_text: string
  status: VerificationStatus
  risk_level: RiskLevel | null
}

// --- Claim drawer (8.3): GET /projects/{id}/claims/{claim_id} -------------------

export type Confidence = "high" | "medium" | "low" | "unknown"

export interface Citation {
  url: string
  excerpt: string | null
  retrieved_at: string
}

export interface FieldBasis {
  field: string
  citations: Citation[]
  reasoning: string
  confidence: Confidence
}

export type EvidenceMethod =
  | "search"
  | "task"
  | "responses"
  | "entity_search"
  | "extract"
  | "grounding"

export interface Evidence {
  evidence_id: string
  claim_id: string
  cycle: number
  method: EvidenceMethod
  parallel_run_id: string | null
  processor: string | null
  output: Record<string, unknown>
  basis: FieldBasis[]
  overall_confidence: Confidence
  cost_usd: number
  created_at: string
}

export interface Risk {
  claim_id: string
  evidence_id: string
  level: RiskLevel
  score: number
  rationale: string
  cost_band: string | null
  remediation_suggested: boolean
  remediation_kind: string
  territory_flags: Record<string, RiskLevel>
  assessed_at: string
}

export type Actor = "ingest" | "agent" | "monitor" | "reverify_worker" | "human"

export interface VerificationEvent {
  event_id: string
  claim_id: string
  at: string
  actor: Actor
  from_status: VerificationStatus | null
  to_status: VerificationStatus
  note: string
  ref: Record<string, unknown>
}

export interface SourceRef {
  asset_id: string
  page: number | null
  scene_number: string | null
  scene_heading: string | null
  t_start_ms: number | null
  t_end_ms: number | null
  channel: string | null
  excerpt: string
  occurrences: number
}

export interface Claim {
  claim_id: string
  project_id: string
  studio_id: string
  kind: ClaimKind
  category: ClaimCategory
  entity_text: string
  normalized_text: string
  claim_text: string
  language: string
  source: SourceRef
  jurisdictions: string[]
  priority: number
  status: VerificationStatus
  prior_production_note: string | null
  created_at: string
  updated_at: string
}

export interface ClaimDetail {
  claim: Claim
  evidence_history: Evidence[]
  risk: Risk | null
  history: VerificationEvent[]
  monitor_status: string | null
}

export interface HumanOverrideRequest {
  status?: VerificationStatus
  risk_level?: RiskLevel
  note: string
}

// --- Script/video timeline (8.3): GET /assets/{id}/timeline|segments|proxy -----

export interface Segment {
  t_start_ms: number
  t_end_ms: number
  speaker: string | null
  transcript: string
}

export interface TimelineClaim {
  claim_id: string
  kind: ClaimKind
  category: ClaimCategory
  claim_text: string
  page: number | null
  t_start_ms: number | null
  t_end_ms: number | null
  channel: string | null
  status: VerificationStatus
  verdict: string | null
  risk_level: RiskLevel | null
  top_citation: string | null
}

export interface TimelineResponse {
  asset_id: string
  duration_ms: number | null
  segments: Segment[]
  claims: TimelineClaim[]
}

export interface SegmentsResponse {
  asset_id: string
  segments: Segment[]
}

export interface PlaybackResponse {
  proxy_url: string | null
  poster_url: string | null
}

export interface FileUrlResponse {
  url: string
}
