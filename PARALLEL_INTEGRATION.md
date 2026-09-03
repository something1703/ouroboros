# PARALLEL_INTEGRATION.md — Contracts for the research layer

All Parallel usage is confined to `packages/parallel_client/`. This document is the contract for that package. Verified against docs.parallel.ai on 31 Aug 2026; when in doubt, fetch the page as markdown by appending `.md` to its URL.

---

## 1. Package layout

```
packages/parallel_client/
├── __init__.py          # exports: search, task, responses, entity, extract, monitor, memory, cost
├── client.py            # single Parallel() instance; API key from Secret Manager/env; timeouts; retries
├── search.py            # search(objective, queries, *, mode, location, exclude_domains, after_date, max_results, session_id)
├── task.py              # run(input, spec, *, processor, mcp_servers, metadata, previous_interaction_id, wait) ; result(run_id) ; group(...)
├── responses.py         # ask(question, *, schema, effort)
├── entity.py            # search(objective, entity_type, limit)
├── extract.py           # extract(urls, *, objective, full_content)
├── monitor.py           # create_snapshot(task_run_id, freq, webhook) ; create_stream(query, freq, webhook, location) ; update ; cancel ; events
├── memory.py            # retrieve(query, scope_key)
├── basis.py             # parse FieldBasis[] -> packages.claims.FieldBasis, overall_confidence
├── specs/               # *.json Task specs + factual_quick schema; loader validates rules in §3
├── cost.py              # price table, meter, BudgetExceeded
├── webhooks.py          # signature verification, event models
└── fixtures/            # vcr cassettes (scrubbed)
```

## 2. Price table (`cost.py`) — hard-coded from Parallel pricing, 31 Aug 2026

| SKU | USD |
|---|---|
| `search.turbo` / `search.fast` (10 results) | 0.001 (+0.001 per extra result) |
| `search.basic` / `search.advanced` (10 results) | 0.005 (+0.001 per extra result) |
| `extract` per URL | 0.001 |
| `task.lite(-fast)` | 0.005 |
| `task.base(-fast)` | 0.010 |
| `task.core(-fast)` | 0.025 |
| `task.core2x(-fast)` | 0.050 |
| `task.pro(-fast)` | 0.100 |
| `task.ultra*` | **forbidden in pipeline** |
| `responses.low` / `medium` / `high` | 0.010 / 0.050 / 0.250 |
| `monitor.lite` / `base` per execution | 0.003 / 0.010 |
| `entity_search` (100 results) | 0.005 |
| `findall.*` | not used |

The meter records a `cost_events` row per call *before* the call (estimated) and corrects after (actual `usage` if returned). `BudgetExceeded` when `sum(cost_events for project) + estimate > project.budget_cap_usd`.

## 3. Task Spec rules (enforced by `specs/loader.py` at import time)

- Root `"type":"object"` with `properties`; no root `anyOf`.
- Every property listed in `required`; `additionalProperties:false` on every object.
- Optional ⇒ `"type":["string","null"]` etc.
- Forbidden keywords: `contains, format, maxContains, maxItems, maxLength, maxProperties, maximum, minContains, minItems, minLength, minimum, minProperties, multipleOf, pattern, patternProperties, propertyNames, uniqueItems, unevaluatedItems, unevaluatedProperties`.
- Nesting ≤ 5, total properties ≤ 100, enum values ≤ 500.
- Spec ≤ 15,000 chars; spec + input ≤ 25,000 chars. `task.run` asserts this and truncates `input` hints (search URLs list) first if needed.

## 4. Per-API contracts

### 4.1 Search
```python
def search(objective: str, queries: list[str], *, mode: Literal["turbo","fast","basic","advanced"]="fast",
           location: str|None=None, exclude_domains: list[str]|None=None, after_date: date|None=None,
           max_results: int=10, session_id: str|None=None, claim_id: str|None=None) -> SearchResult
```
- Always send `objective` **and** `search_queries` (1–3 concise queries).
- `location` only if in the supported list (`config/parallel.py: SUPPORTED_LOCATIONS`, 37 codes; `gb` not `uk`). Otherwise omit and rely on objective wording.
- Never set `include_domains` by default. `exclude_domains` default: `["pinterest.com","facebook.com","instagram.com","tiktok.com"]` for legal categories (noise), none for factual.
- `after_date` used only by re-verification (`since last cycle`) and developing-story checks.
- Store `session_id` in the claim's current cycle so Search + Extract calls for one claim group together.
- Response handling: keep `url, title, publish_date, excerpts[:3]`; Model-Armor-screen excerpts before they reach any prompt.

### 4.2 Task
```python
def run(input: str, spec: str, *, processor: str="core-fast", claim_id: str, project_id: str,
        mcp_servers: list[McpServer]|None=None, previous_interaction_id: str|None=None,
        memory_scope_key: str|None=None, wait: bool=True, timeout_s: int=600) -> TaskResult | RunHandle
```
- `input` = f"{claim_text}\nJurisdictions: {codes}\nContext: {source excerpt}\nHints: {top urls}" (≤ 4k chars).
- `task_spec={"output_schema": {"type":"json","json_schema": spec_json}}`.
- `metadata={"env","project_id","claim_id","cycle","spec"}` — used to route webhooks.
- `mcp_servers=[{"type":"url","url": TOOLBOX_MCP_URL,"name":"ouroboros_ledger","headers":{"Authorization": f"Bearer {token}"},"allowed_tools":["get_claim","get_prior_decisions","list_claims"]}]` — **read-only tools only** are exposed to Parallel. Note: lite/core make at most one MCP call; that's fine.
- `wait=True` → `client.task_run.result(run_id, api_timeout=timeout_s)`; `wait=False` → return handle; completion arrives by webhook (`task_run.status` events).
- Escalation policy lives in the caller, not here.
- Parse with `basis.parse()`; `overall_confidence = min(confidence of required fields)`, `unknown` if any missing.

### 4.3 Responses
```python
def ask(question: str, *, schema: str="factual_quick", effort: Literal["low","medium","high"]="medium") -> ResponsesResult
```
- OpenAI-compatible endpoint; request structured output with the schema; read citations/annotations into `Citation[]`; map to `Evidence(method="responses")`.

### 4.4 Entity Search
`search(objective, entity_type: Literal["people","companies"], limit=25)` → list of `{name, url, description}`. Used to resolve publishers/labels/estates. Cheap; call once per person/music claim when the Task output leaves `*_rights_holder` null.

### 4.5 Extract
`extract(urls: list[str], *, objective: str, full_content=False)` → list of `{url, markdown, excerpts}`. Cap 5 URLs per claim. Screen with Model Armor.

### 4.6 Monitor
```python
def create_snapshot(task_run_id, *, frequency, webhook_url, claim_id, project_id, memory_scope_key) -> MonitorRecord
def create_stream(query, *, frequency, webhook_url, location, claim_id, project_id, memory_scope_key, processor="lite") -> MonitorRecord
def update(monitor_id, *, frequency=None, webhook=None)
def cancel(monitor_id)
def events(monitor_id, *, event_group_id=None) -> list[MonitorEvent]
```
- Webhook: `{"url": f"{PUBLIC_BASE_URL}/webhooks/parallel/monitor", "event_types":["monitor.event.detected"]}`.
- `metadata={"claim_id","project_id","monitor_kind"}` echoes back in the webhook payload — this is how we route.
- Event `output.content` + `basis` are stored as an `Evidence(method="task", cycle=n)` **only after** the follow-up Task run completes; the raw event is stored in Firestore `events` immediately.
- Frequency policy (`config/parallel.py`): `days_to_release > 60 → "1w"`, `8..60 → "1d"`, `≤7 → "1h"`. Cloud Scheduler applies daily.
- Monitors are cancelled when a claim is set to `none` risk by a human, or the project is archived.

### 4.7 Memory
- Every Task and Monitor call passes `memory_scope_key = studio_id`.
- `ClaimTriage` may call `memory.retrieve(query=entity_text, scope_key=studio_id)`; hits are attached as `prior_context` in the Task input hints (quoted, untrusted).

### 4.8 Gemini grounding (lives in `packages/gemini_client/grounding.py`, not here)
```python
types.Tool(parallel_ai_search=types.ToolParallelAiSearch(
    api_key=PARALLEL_API_KEY if PARALLEL_GROUNDING_MODE=="byok" else None,
    custom_configs={"mode":"basic","max_results":10,"location": loc}))
```
- Model must be one of the supported set (`gemini-3.5-flash` chosen).
- Render citations from `grounding_metadata.grounding_supports` using **byte offsets per part**, inserting markers in reverse order.
- 200 prompts/min quota is shared; fine for demo.

## 5. Webhooks (`webhooks.py`)

- Endpoint `/webhooks/parallel/{monitor|task}` on Cloud Run `webhook_receiver`.
- Verify signature per Parallel's webhook-setup doc (fetch `https://docs.parallel.ai/resources/webhook-setup.md` in Phase 7.2 and implement exactly; store the secret in Secret Manager as `PARALLEL_WEBHOOK_SECRET`).
- Respond 200 within 2s; all work happens after publishing to Pub/Sub. Idempotency key = `event_id`/`run_id`; duplicates are dropped.

## 6. Error handling

| Condition | Behaviour |
|---|---|
| 429 / 5xx / timeout | retry 3× with backoff 1s, 4s, 16s |
| 4xx validation | raise `ParallelValidationError` (no retry); record on claim as `error` |
| `warnings` present in response | log at WARN with `claim_id`; continue |
| Task `failed` | not billed; record `error`; caller may retry once with `base-fast` |
| Budget exceeded | stop the batch, mark remaining claims `pending` with note `budget`, surface in UI |

## 7. Rate limits (defaults)

Search 600/min, Extract 600/min, Tasks 2,000/min, Responses (chat family) 300/min, Entity Search 600/min, Monitor create 300/min. Pipeline concurrency of 10 keeps us far below all of these.

## 8. Testing strategy

- `vcrpy` cassettes for every function, recorded once via `make test-live`, scrubbed of `x-api-key` and any `Authorization` header.
- One golden cassette per spec (`legal_music` on a famous song, `legal_brand` on a major brand, `factual_claim` on a well-documented event).
- Contract tests assert Basis parsing, confidence min-rule, cost metering, spec validation, and webhook signature verification.
