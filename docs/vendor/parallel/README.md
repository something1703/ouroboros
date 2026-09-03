# Vendored Parallel API notes (Phase 4.1)

Verified 2026-09-03 against the installed `parallel-web` SDK (v1.3.3) via live
introspection (`inspect.signature`, pydantic `model_fields`) plus the current
docs.parallel.ai pages. **The docs site restructured URLs since
`PARALLEL_INTEGRATION.md` was written** (`/resources/*` → `/task-api/*`,
`/findall-api/*`, `/responses-api/*`, `/monitor-api/*`, `/chat-api/*`); the old
`/resources/responses-quickstart.md` and similar links 404. Corrections below
are authoritative over `PARALLEL_INTEGRATION.md` wherever they conflict —
`packages/parallel_client/` follows this file.

## Real SDK surface (`from parallel import Parallel`)

Top-level on the client: `search()`, `extract()`, `.task_run.*`, `.task_group.*`,
`.monitor.*`, `.beta.findall.*`, `.beta.memory.*`. **No `responses`, no
top-level `entity` resource** — both differ from the original plan's package
layout:

- **Responses API** is not in the `parallel` SDK at all — it's called with the
  **`openai` SDK** pointed at Parallel's base URL:
  ```python
  from openai import OpenAI
  client = OpenAI(api_key=PARALLEL_API_KEY, base_url="https://api.parallel.ai/v1")
  response = client.responses.create(model="parallel", input=question, reasoning={"effort": "low"})
  ```
  Structured output: `text={"format": {"type": "json_schema", "name": ..., "schema": {...}}}`,
  parse `json.loads(response.output_text)`. Citations:
  `response.output[].content[].annotations[]`, each `{type: "url_citation", url, title, start_index, end_index}`.
  Added `openai` as a dependency for exactly this one wrapper.

- **Entity Search** is `client.beta.findall.entity_search(entity_type, objective, match_limit)`
  — under `beta.findall`, not a standalone `entity` client. Response:
  `{entity_set_id, entities: [{name, url, description}]}`.

- **Memory** is `client.beta.memory.retrieve(query, kind, limit, memory_scope_key, since)` /
  `.clear(memory_scope_key)` / `.evict(id, kind, memory_scope_key)`.

## `search()` (top-level, confirmed matches `PARALLEL_INTEGRATION.md §4.1`)
```python
client.search(*, search_queries: list[str], objective: str | None = None,
               mode: Literal["turbo","fast","basic","advanced"] = ...,
               advanced_settings: {"location": str, "max_results": int,
                                     "source_policy": {"exclude_domains": [...], "include_domains": [...], "after_date": date}},
               session_id: str | None = None) -> SearchResult
```
`SearchResult`: `results: WebSearchResult[]` (`url, title, publish_date, excerpts: list[str]`),
`search_id`, `session_id`, `usage: UsageItem[]`, `warnings: Warning[]`.

## `client.task_run.*` (confirmed matches `PARALLEL_INTEGRATION.md §4.2`)
```python
client.task_run.create(*, input: str | dict, processor: str,
                        task_spec: {"output_schema": {"type": "json", "json_schema": {...}}},
                        metadata: dict[str, str|float|bool] | None = None,
                        mcp_servers: [{"type":"url","name":...,"url":...,"headers":...,"allowed_tools":[...]}] | None = None,
                        previous_interaction_id: str | None = None,
                        memory_scope_key: str | None = None,
                        source_policy: {"exclude_domains":..., "include_domains":..., "after_date":...} | None = None,
                        webhook: {"url":..., "event_types": [...]} | None = None) -> TaskRun
client.task_run.result(run_id, *, api_timeout: int) -> TaskRunResult  # {output, run}
client.task_run.retrieve(run_id) -> TaskRun  # {run_id, status, is_active, error, warnings, metadata, ...}
```
`TaskRunResult.output`: `TaskRunJsonOutput` (`content: dict, basis: FieldBasis[]`) or
`TaskRunTextOutput` (`content: str, basis: FieldBasis[]`).
`FieldBasis`: `field, reasoning, citations: Citation[] | None, confidence: "high"|"medium"|"low"|None`.
Confidence levels confirmed exactly 3 (`task-api/guides/access-research-basis`);
`None` means Parallel itself couldn't rate it — our own `overall_confidence`
min-rule (not a Parallel concept) treats a missing/`None` field confidence as
`Confidence.UNKNOWN`, the worst case, per `PARALLEL_INTEGRATION.md §4.2`.

## `client.extract()` (matches plan)
```python
client.extract(*, urls: list[str], objective: str | None = None,
                search_queries: list[str] | None = None,
                advanced_settings: {...} | None = None) -> ExtractResponse
```
`ExtractResponse`: `results: ExtractResult[]` (`url, title, publish_date, excerpts, full_content`),
`errors: ExtractError[]`, `session_id`, `usage`, `warnings`.

## `client.monitor.*` (matches plan; `settings` shape confirmed)
```python
client.monitor.create(*, type: "snapshot"|"event_stream", frequency: str,
                       settings: {"task_run_id": str}                                    # snapshot
                               | {"query": str, "advanced_settings": {"location":...}},   # event_stream
                       processor: "lite"|"base" = "lite", webhook: {...} | None = None,
                       metadata: dict[str,str] | None = None, memory_scope_key: str | None = None) -> Monitor
client.monitor.update(monitor_id, *, frequency=None, settings=None, webhook=None, ...) -> Monitor
client.monitor.cancel(monitor_id) -> Monitor
client.monitor.events(monitor_id, *, cursor=None, event_group_id=None, limit=None) -> PaginatedMonitorEvents
```
Events are a discriminated union on `event_type`: `MonitorSnapshotEvent`
(`event_group_id, previous_output, changed_output`), `MonitorEventStreamEvent`,
`MonitorCompletionEvent`, `MonitorErrorEvent`.

## Webhooks — Standard Webhooks spec (`task-api/features/webhooks`, `resources/webhook-setup`)
Headers: `webhook-id`, `webhook-timestamp` (unix seconds), `webhook-signature`
(`v1,<base64 sig>`, possibly multiple space-separated `v1,...` values per the
Standard Webhooks spec — verify against *any* of them, not just the first).
Signed string: `f"{webhook_id}.{webhook_timestamp}.{raw_body_str}"`, HMAC-SHA256,
key = base64-decode(secret with any `whsec_` prefix stripped).

Monitor payload:
```json
{"type": "monitor.event.detected", "timestamp": "...",
 "data": {"monitor_id": "...", "event": {"event_group_id": "..."}, "metadata": {...}}}
```
Task payload:
```json
{"type": "task_run.status", "timestamp": "...",
 "data": {"run_id": "...", "status": "completed"|"failed"|..., "is_active": bool,
          "warnings": [...] | null, "error": {"message":...} | null, "processor": "...",
          "metadata": {...}, "created_at": "...", "modified_at": "..."}}
```

## Price-table SKU note
`monitor.create()`'s `processor` is only `"lite"|"base"` (no `-fast` variants,
unlike Task) — matches `config/parallel.py: FORBIDDEN_MONITOR_PROCESSORS = {"base"}`
already assuming this two-value set.
