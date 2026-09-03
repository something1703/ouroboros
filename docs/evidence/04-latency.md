# Phase 4 — latency evidence

Real latencies observed during live development/verification (`packages/parallel_client`'s
own structured `parallel_call` log line, `latency_ms` field), not synthetic. Single-sample
per API (not a proper p50 over many runs — noted where the phase plan expected one).

| API | Call | Observed latency |
|---|---|---|
| Search | `mode=fast`, 2 queries | 1.2s – 1.7s across several calls |
| Task | `processor=core-fast`, `legal_brand`, `wait=True` (create + result) | 28.7s – 43.0s |
| Extract | 1 URL | 1.3s |
| Entity Search | `companies`, `match_limit=5` | 1.2s |
| Responses | `effort=low` | 6.4s |
| Monitor create (`snapshot`) | | 0.6s |
| Monitor events | | 0.5s |
| Monitor cancel | | 0.4s |
| Memory retrieve | | 0.8s |

Task's `core-fast` latency (real research + structured-output synthesis, not just an
HTTP round-trip) dominates end-to-end `verify_claim.py` runtime — search + task
together took ~30s wall-clock in the real Cloud Run Job transcript
(`docs/evidence/04-verify.txt`), consistent with `PARALLEL_INTEGRATION.md §4.2`'s
expectation that Task latency, not the wrapper overhead, is what a caller needs to
design around (never block a UI request on it; `verify_batch.py`'s default
concurrency of 5 exists for exactly this reason).

Responses `effort=medium`/`high` and Task `processor=pro` weren't separately timed —
both are documented by Parallel as substantially slower (Responses: "~30–60s for deep
research" at `high`; Task `pro` is the explicit escalation-only, higher-latency tier
per `config/parallel.py`) and neither is on the default hot path.
