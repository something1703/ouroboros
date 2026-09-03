# ARCHITECTURE.md — Ouroboros system architecture

This is the binding architecture. Phases implement it; they do not redesign it. See `ouroboros_architecture.mermaid` for the diagram.

---

## 1. One-paragraph model

Ouroboros treats a film as a set of **claims about the real world**. A screenplay makes *legal* claims (this brand, song, person, artwork, location can be shown). A rough cut makes *factual* claims (this event happened, this figure is correct, this footage is what it says it is). Every claim is extracted by Gemini into a **Claim Ledger**, verified by ADK agents using Parallel's research APIs into an **Evidence** record with citations and confidence, scored for **Risk**, and then **Watched** by Parallel Monitors so that any change in the world triggers **Re-verification**. Outputs feed inputs — the loop is the product.

## 2. Components and responsibilities

### 2.1 Ingest (Google Cloud)
| Component | Responsibility |
|---|---|
| Cloud Storage `ouroboros-intake-{env}` | Landing zone. Prefixes `scripts/{project_id}/` and `cuts/{project_id}/`. |
| Eventarc | `google.cloud.storage.object.v1.finalized` → Cloud Run `ingest`. |
| Cloud Run `ingest` | Detects asset type; runs Gemini document understanding (PDF) or video understanding (mp4/mov); produces `Claim[]` via structured output; passes all text through Model Armor; upserts to ledger; publishes `claims.extracted` to Pub/Sub. Idempotent by `claim_id`. |
| Model Armor | Screens extracted text and, later, every web excerpt before it enters a model context. |

### 2.2 Claim Ledger (Google Cloud)
| Component | Responsibility |
|---|---|
| Cloud SQL (PostgreSQL 16) | System of record: `projects`, `assets`, `claims`, `evidence`, `verification_history`, `monitors`, `cost_events`. |
| MCP Toolbox for Databases (Cloud Run) | Exposes read tools (`get_claim`, `list_claims_by_project`, `get_prior_decisions`) and narrow write tools (`record_evidence`) as an MCP server. **Two consumers:** ADK agents, and Parallel Task runs (remote MCP). |
| Firestore | Denormalized live views: `projects/{id}/claims/{claim_id}` (current status), `projects/{id}/events` (monitor feed), `projects/{id}/metrics` (Reality Drift). Written by services, read by the dashboard in realtime. |
| BigQuery `ouroboros` dataset | Nightly + streaming mirror of ledger tables for analytics and the Parallel BigQuery remote-function enrichment path. |
| Secret Manager | `PARALLEL_API_KEY`, `PARALLEL_WEBHOOK_SECRET`, `SLACK_WEBHOOK_URL`, DB password. |

### 2.3 Orchestration (Agent Engine, ADK)
See `ADK_AGENTS.md` for the full catalog. Shape:

```
root: OuroborosCoordinator (LlmAgent, routes by asset type)
├── CLEAR (SequentialAgent)
│   ├── ClaimTriage (LlmAgent)                      # dedupe, prioritize, pick jurisdiction
│   ├── ClearFanOut (ParallelAgent)
│   │   ├── MusicAgent
│   │   ├── BrandAgent
│   │   ├── PersonAgent
│   │   └── LocationArtAgent
│   ├── RiskAssessor (LlmAgent, pro model)
│   └── Reporter (LlmAgent, pro model)
├── TRUECUT (SequentialAgent)
│   ├── ClaimTriage
│   ├── FactAgent (LlmAgent)                        # Responses API first, Task escalation
│   ├── ArchiveAgent (LlmAgent)                     # Extract on catalog pages
│   ├── RiskAssessor
│   └── Reporter
└── AskOuroboros (LlmAgent)                         # grounded Q&A: ToolParallelAiSearch + Vertex AI Search + ledger tools
```

Deterministic pipelines are `SequentialAgent`/`ParallelAgent`; LLM judgment lives only inside leaf `LlmAgent`s with narrow instructions and structured outputs. This is what "deterministic multi-step agent" means to the judges.

### 2.4 Research layer (Parallel Web Systems)
| API | Used by | Purpose |
|---|---|---|
| Search (`fast`, geo `location`, `exclude_domains`, `after_date`) | all specialists | Triage: does this entity have an obvious rights holder / is this claim obviously true or false? |
| Task (`core-fast` → `pro` escalation) with JSON Task Spec | CLEAR specialists, FactAgent escalation, re-verification | Structured evidence with per-field Basis (citations, reasoning, confidence). Receives our Toolbox MCP as `mcp_servers`. |
| Responses (`medium`) with structured output | FactAgent | Synchronous cited verdicts in ~15s for the timeline. |
| Entity Search | PersonAgent, MusicAgent | Resolve publishers, labels, estates, agents. |
| Extract | ArchiveAgent, BrandAgent | Pull licensing pages, archive catalog pages, trademark records into markdown. |
| Monitor (`snapshot` on Task runs; `event_stream` on stories) | loop | Watch high-risk findings; frequency managed by Cloud Scheduler. |
| Memory (`memory_scope_key = studio_id`) | Task, Monitor | Cross-production reuse. |
| Gemini grounding `ToolParallelAiSearch` | AskOuroboros | Conversational layer; second native integration path. |

### 2.5 The loop (Google Cloud + Parallel)
1. Reporter writes Evidence → high-risk claims get a Parallel **snapshot Monitor** on their Task run (and an **event_stream Monitor** for factual claims about developing stories).
2. Monitor fires `monitor.event.detected` → Cloud Run `webhook_receiver` verifies signature → publishes `verification.event` to Pub/Sub.
3. Pub/Sub push → Cloud Run `reverify_worker` fetches the event, creates a new Task run with `previous_interaction_id = event_id`, same Task Spec, `metadata.claim_id`.
4. Task completes → Parallel Task webhook → `webhook_receiver` → `reverify_worker` writes new Evidence row, appends `verification_history`, recomputes risk and **Reality Drift**, updates Firestore, optionally posts Slack.
5. Cloud Scheduler (daily) computes days-to-release and calls Monitor `update` to tighten frequency: `1w` (>60d) → `1d` (8–60d) → `1h` (≤7d).

### 2.6 Presentation & governance
| Component | Responsibility |
|---|---|
| Cloud Run `dashboard_api` (FastAPI) | Project/claim/evidence endpoints; exports; proxies AskOuroboros to Agent Engine; SSE for Task progress. |
| Cloud Run `web` (React) | Script viewer with risk heatmap; video timeline with claim markers; live monitor feed; Reality Drift; role-aware views. |
| Identity-Aware Proxy | Google sign-in; IAM group → app role (`legal`, `editorial`, `producer`). |
| Exports | E&O evidence pack (PDF, per claim, citations + history); clearance log → Google Sheets; fact-check report (PDF). |
| Slack | High-risk monitor events via Parallel's Slack integration or our webhook. |
| Cloud Logging / Trace | Structured logs; one trace per claim verification. |
| Vertex AI Evaluation | Golden-set evals in CI (Phase 9). |

### 2.7 Remediation (stretch, Phase 10)
Lyria temp cue for unclearable songs; Gemini image mockup for unclearable brands/props. Triggered from RiskAssessor `remediation_suggested=true`.

## 3. Data flow (happy path, CLEAR)

```
PDF → GCS → Eventarc → ingest
  → Gemini doc understanding (structured) → Model Armor → Claim[] → Cloud SQL + Firestore + Pub/Sub(claims.extracted)
  → Agent Engine run (project_id, asset_id)
    → ClaimTriage (jurisdiction, priority, dedupe)
    → ClearFanOut (per-category specialist)
        → Search fast (triage) → Task core-fast (structured) [→ Task pro if low-confidence & high-risk]
        → Evidence + Basis → record_evidence (Toolbox MCP)
    → RiskAssessor → risk_level, cost_band, remediation_suggested → Firestore
    → Reporter → E&O pack sections; create Monitors for high-risk claims
  → Dashboard updates in realtime
```

## 4. Non-functional requirements

| NFR | Target |
|---|---|
| Idempotency | Re-running any stage on the same input yields the same rows; no duplicates. |
| Latency (demo) | Ingest of a 120-page PDF < 3 min. First evidence visible < 2 min after ingest. Full CLEAR pass on 150 claims < 25 min (core-fast, 10-way concurrency). |
| Cost | Per-project cap enforced in code; default $10 Parallel. |
| Resilience | Any single Parallel or Gemini failure marks the claim `verification_status=error` with the message; never blocks other claims. |
| Security | No secrets in code/logs/URLs; webhook signature verification; Model Armor on all untrusted text; IAP on UI; least-privilege SAs (one per service). |
| Observability | Every claim has a trace; every Parallel call has a `cost_events` row; dashboard shows spend. |
| Reproducibility | `make deploy ENV=dev` from a clean checkout stands up the whole system with Terraform. |

## 5. Environment topology

- One GCP project, two envs by suffix: `dev` (daily work) and `demo` (frozen 24h before submission, the one judges see). Same Terraform, different `tfvars`.
- Parallel: one API key; `metadata.env` on every run for cost separation.

## 6. Explicit non-goals

- No fine-tuning. No custom models.
- No FindAll `pro`, no `ultra*` Task processors in the pipeline.
- No storyboards/TTS/Veo — off-identity for this product.
- No multi-tenant billing; `studio_id` exists in the schema for memory scoping only.
