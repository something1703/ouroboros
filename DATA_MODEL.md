# DATA_MODEL.md — The spine of Ouroboros

Every agent, service and view builds against these types. Change them only with an Alembic migration and a `docs/DECISIONS.md` entry.

---

## 1. Core domain types (Pydantic v2, `packages/claims/models.py`)

### 1.1 Enumerations

```python
class ClaimKind(str, Enum):        # which head owns it
    LEGAL = "legal"                # CLEAR
    FACTUAL = "factual"            # TRUE CUT

class ClaimCategory(str, Enum):
    # legal
    MUSIC = "music"                # song, cue, lyric, recording
    BRAND = "brand"                # trademark, logo, product, packaging
    PERSON = "person"              # real person, likeness, name, biography
    LOCATION = "location"          # real venue, landmark, private property
    ARTWORK = "artwork"            # painting, photo, sculpture, poster
    QUOTE = "quote"                # text from book/film/speech
    # factual
    EVENT = "event"                # something happened at a time/place
    STATISTIC = "statistic"        # a number, rate, ranking
    ATTRIBUTION = "attribution"    # who said/did/made something
    ARCHIVAL = "archival"          # provenance of footage/photo/audio
    IDENTITY = "identity"          # this person/thing on screen is who/what we say

class VerificationStatus(str, Enum):
    PENDING = "pending"
    TRIAGED = "triaged"
    VERIFYING = "verifying"
    VERIFIED = "verified"          # evidence exists (any confidence)
    ESCALATED = "escalated"        # pro Task in flight
    ERROR = "error"
    STALE = "stale"                # monitor detected change; re-verification pending

class RiskLevel(str, Enum):
    NONE = "none"; LOW = "low"; MEDIUM = "medium"; HIGH = "high"; BLOCKING = "blocking"

class Confidence(str, Enum):       # mirrors Parallel Basis
    HIGH = "high"; MEDIUM = "medium"; LOW = "low"; UNKNOWN = "unknown"
```

### 1.2 Claim

```python
class SourceRef(BaseModel):
    asset_id: str
    # script
    page: int | None = None
    scene_number: str | None = None
    scene_heading: str | None = None
    # video
    t_start_ms: int | None = None
    t_end_ms: int | None = None
    channel: Literal["dialogue", "narration", "on_screen_text", "visual", "action_line"] | None = None
    excerpt: str                       # verbatim text (≤ 500 chars) that produced the claim

class Claim(BaseModel):
    claim_id: str                      # sha256(project_id|category|normalized_text|asset_id|page_or_t_start)[:24]
    project_id: str
    studio_id: str
    kind: ClaimKind
    category: ClaimCategory
    entity_text: str                   # canonical surface form, e.g. "Coca-Cola", "Bohemian Rhapsody"
    normalized_text: str               # lowercase, punctuation-stripped, for hashing/dedupe
    claim_text: str                    # one sentence, e.g. "A Coca-Cola can is visible on the table in Sc. 12"
    language: str                      # BCP-47 of the source text
    source: SourceRef
    jurisdictions: list[str]           # ISO alpha-2 codes; from project.distribution_territories
    priority: int                      # 1 (highest) – 5; set by ClaimTriage
    status: VerificationStatus = VerificationStatus.PENDING
    created_at: datetime
    updated_at: datetime
```

### 1.3 Evidence (one per verification cycle)

```python
class Citation(BaseModel):
    url: str
    excerpt: str | None = None
    retrieved_at: datetime

class FieldBasis(BaseModel):           # 1:1 with Parallel FieldBasis
    field: str
    citations: list[Citation]
    reasoning: str
    confidence: Confidence

class Evidence(BaseModel):
    evidence_id: str                   # ulid
    claim_id: str
    cycle: int                         # 1 = first verification, 2+ = re-verification
    method: Literal["search", "task", "responses", "entity_search", "extract", "grounding"]
    parallel_run_id: str | None        # trun_..., or response id
    previous_interaction_id: str | None
    processor: str | None              # core-fast, pro, medium...
    output: dict                       # the structured Task/Responses content (schema per category, §2)
    basis: list[FieldBasis]
    overall_confidence: Confidence     # min over required fields
    cost_usd: Decimal
    created_at: datetime
```

### 1.4 Risk (current, one per claim; history kept)

```python
class Risk(BaseModel):
    claim_id: str
    evidence_id: str
    level: RiskLevel
    score: float                       # 0..1
    rationale: str
    cost_band: Literal["none", "<1k", "1k-10k", "10k-100k", ">100k", "unknown"] | None
    remediation_suggested: bool
    remediation_kind: Literal["replace_brand", "replace_music", "reshoot", "recut", "obtain_release", "none"]
    territory_flags: dict[str, RiskLevel]   # per jurisdiction
    assessed_at: datetime
```

### 1.5 VerificationHistory (append-only audit)

```python
class VerificationEvent(BaseModel):
    event_id: str
    claim_id: str
    at: datetime
    actor: Literal["ingest", "agent", "monitor", "reverify_worker", "human"]
    from_status: VerificationStatus | None
    to_status: VerificationStatus
    note: str
    ref: dict                          # {"monitor_id":..., "event_id":..., "run_id":..., "user":...}
```

### 1.6 MonitorRecord

```python
class MonitorRecord(BaseModel):
    monitor_id: str                    # Parallel monitor id
    claim_id: str
    type: Literal["snapshot", "event_stream"]
    task_run_id: str | None            # for snapshot
    query: str | None                  # for event_stream
    frequency: Literal["1h", "1d", "1w"]
    status: Literal["active", "cancelled"]
    last_event_at: datetime | None
    created_at: datetime
```

## 2. Parallel Task output schemas (`packages/parallel_client/specs/`)

All schemas follow Parallel rules: root `object`, every property in `required`, `additionalProperties: false`, optional values expressed as `["string","null"]`, no `pattern/minLength/format`. Keep each spec ≤ 6k chars so spec + input stays well under 25k.

### 2.1 `legal_music.json`

```json
{
  "type": "object",
  "properties": {
    "work_title": {"type": "string", "description": "Canonical title of the musical work"},
    "is_public_domain": {"type": ["boolean","null"], "description": "True if composition AND recording are public domain in the given jurisdictions"},
    "composition_rights_holder": {"type": ["string","null"], "description": "Publisher / songwriter estate controlling the composition"},
    "master_rights_holder": {"type": ["string","null"], "description": "Label or owner of the specific recording, if a recording is implied"},
    "performing_rights_org": {"type": ["string","null"], "description": "PRO/CMO relevant to the jurisdictions, e.g. ASCAP, PRS, IPRS, JASRAC"},
    "licensing_contact_url": {"type": ["string","null"], "description": "Official sync-licensing page or contact"},
    "known_sync_restrictions": {"type": ["string","null"], "description": "Any documented refusal to license, artist restrictions, or notable disputes"},
    "typical_sync_cost_band": {"type": "string", "enum": ["<1k","1k-10k","10k-100k",">100k","unknown"], "description": "Order-of-magnitude sync fee for an indie feature"},
    "territory_notes": {"type": "string", "description": "Jurisdiction-specific notes for each requested territory"}
  },
  "required": ["work_title","is_public_domain","composition_rights_holder","master_rights_holder","performing_rights_org","licensing_contact_url","known_sync_restrictions","typical_sync_cost_band","territory_notes"],
  "additionalProperties": false
}
```

### 2.2 `legal_brand.json`
Fields: `brand_owner`, `trademark_registrations` (array of {jurisdiction, registration_number_or_null, status}), `brand_clearance_policy_url`, `known_litigiousness` (enum low/medium/high/unknown), `product_placement_contact_url`, `depiction_guidelines_summary`, `territory_notes`.

### 2.3 `legal_person.json`
Fields: `is_living`, `is_public_figure`, `estate_or_representation` (string|null), `right_of_publicity_notes` (per jurisdiction), `known_litigation_over_depiction`, `consent_recommended` (boolean), `territory_notes`.

### 2.4 `legal_location_artwork.json`
Fields: `owner_or_custodian`, `filming_permit_required` (boolean|null), `permit_authority_url`, `artwork_copyright_status` (enum protected/public_domain/unknown), `artwork_rights_holder`, `restrictions_summary`, `territory_notes`.

### 2.5 `factual_claim.json` (Task escalation and re-verification)

```json
{
  "type": "object",
  "properties": {
    "verdict": {"type": "string", "enum": ["supported","contradicted","partially_supported","unverifiable"]},
    "corrected_statement": {"type": ["string","null"], "description": "If contradicted or partially supported, the accurate statement"},
    "key_evidence_summary": {"type": "string", "description": "2-4 sentences summarizing the strongest evidence for and against"},
    "is_developing_story": {"type": "boolean", "description": "True if the underlying facts are likely to change before a release in the next 90 days"},
    "recommended_wording": {"type": ["string","null"], "description": "Narration wording that would be defensible given the evidence"}
  },
  "required": ["verdict","corrected_statement","key_evidence_summary","is_developing_story","recommended_wording"],
  "additionalProperties": false
}
```

### 2.6 Responses API structured output (`factual_quick.json`)
Same fields as 2.5 minus `is_developing_story` — used for the sync first pass.

## 3. Cloud SQL schema (Alembic `0001_initial`)

```sql
create table projects (
  project_id text primary key, studio_id text not null, title text not null,
  release_date date, shooting_countries text[] not null default '{}',
  distribution_territories text[] not null default '{}',
  budget_cap_usd numeric(10,2) not null default 10.00,
  created_at timestamptz not null default now());

create table assets (
  asset_id text primary key, project_id text references projects,
  kind text check (kind in ('script','cut')), gcs_uri text not null, language text,
  page_count int, duration_ms bigint, ingested_at timestamptz);

create table claims (
  claim_id text primary key, project_id text references projects, studio_id text not null,
  kind text not null, category text not null, entity_text text not null, normalized_text text not null,
  claim_text text not null, language text not null, source jsonb not null,
  jurisdictions text[] not null, priority int not null default 3,
  status text not null default 'pending', created_at timestamptz, updated_at timestamptz);
create index on claims (project_id, status); create index on claims (project_id, category);

create table evidence (
  evidence_id text primary key, claim_id text references claims, cycle int not null,
  method text not null, parallel_run_id text, previous_interaction_id text, processor text,
  output jsonb not null, basis jsonb not null, overall_confidence text not null,
  cost_usd numeric(10,5) not null default 0, created_at timestamptz not null);
create index on evidence (claim_id, cycle desc);

create table risk (
  claim_id text primary key references claims, evidence_id text references evidence,
  level text not null, score real not null, rationale text not null, cost_band text,
  remediation_suggested boolean not null default false, remediation_kind text,
  territory_flags jsonb not null default '{}', assessed_at timestamptz not null);

create table risk_history (like risk including all, id bigserial primary key);  -- append on every change

create table verification_history (
  event_id text primary key, claim_id text references claims, at timestamptz not null,
  actor text not null, from_status text, to_status text not null, note text, ref jsonb);
create index on verification_history (claim_id, at);

create table monitors (
  monitor_id text primary key, claim_id text references claims, type text not null,
  task_run_id text, query text, frequency text not null, status text not null,
  last_event_at timestamptz, created_at timestamptz not null);

create table cost_events (
  id bigserial primary key, project_id text, claim_id text, api text not null,
  sku text, units int not null default 1, cost_usd numeric(10,5) not null, at timestamptz not null);
create index on cost_events (project_id, at);

create table prior_decisions (           -- studio memory, human-entered or imported
  id bigserial primary key, studio_id text not null, category text, entity_normalized text not null,
  decision text not null, note text, decided_at timestamptz);
create index on prior_decisions (studio_id, entity_normalized);
```

## 4. Firestore documents (denormalized)

- `projects/{project_id}` — title, release_date, counts by status/risk, `reality_drift`, `spend_usd`, `updated_at`.
- `projects/{project_id}/claims/{claim_id}` — everything the UI needs in one read: claim core, current risk, latest evidence summary (verdict/holder, confidence, top 3 citations), monitor status, `history_count`.
- `projects/{project_id}/events/{event_id}` — monitor feed entries: `at`, `claim_id`, `kind` (`monitor_event`, `reverified`, `risk_changed`), `summary`, `delta`.
- `projects/{project_id}/runs/{run_id}` — agent run progress for SSE: stage, done/total, started/finished.

## 5. BigQuery (`ouroboros.*`)

Tables mirror Cloud SQL (`claims`, `evidence`, `risk_history`, `cost_events`, `verification_history`) via a nightly Cloud Run job plus streaming inserts for `cost_events`. Phase 7 adds a view `claims_for_enrichment` used by the Parallel BigQuery remote function demo.

## 6. Reality Drift score

Per project, recomputed on every re-verification:

```
drift = Σ_i w_i · changed_i / Σ_i w_i
where i ranges over claims with ≥1 evidence,
      w_i = {none:0.2, low:0.4, medium:0.7, high:1.0, blocking:1.2}[risk_level_i]
      changed_i = 1 if the latest cycle's (verdict|holder|confidence|risk_level) differs from the previous cycle's, else 0
```

Also store `drift_7d` (only cycles in the last 7 days) and `last_change_at`. Dashboard shows `drift` as a percentage with the count of changed claims.

## 7. Jurisdiction config (`config/jurisdictions.yaml`)

```yaml
in:
  parallel_location: in
  music_pro: [IPRS, PPL India]
  objective_hint: "Prefer official Indian rights bodies (IPRS, PPL), Indian trademark registry (ipindia.gov.in), and reputable Indian trade press."
us:
  parallel_location: us
  music_pro: [ASCAP, BMI, SESAC]
  objective_hint: "Prefer USPTO, ASCAP/BMI repertory, publisher and label official sites."
gb: {parallel_location: gb, music_pro: [PRS for Music, PPL], objective_hint: "Prefer PRS/PPL, UK IPO, official publisher sites."}
de: {parallel_location: de, music_pro: [GEMA], objective_hint: "Prefer GEMA, DPMA, official publisher sites."}
jp: {parallel_location: jp, music_pro: [JASRAC], objective_hint: "Prefer JASRAC, JPO, official label sites."}
# Countries not in Parallel's supported-location list: omit parallel_location, name the country in objective_hint.
ng: {music_pro: [COSON, MCSN], objective_hint: "Focus on Nigeria: COSON/MCSN, Nigerian trademark registry, Nigerian trade press."}
```
