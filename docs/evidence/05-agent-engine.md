# Phase 5.5 — Agent Engine deployment evidence

`agents/ouroboros/agent.py`'s `root_agent` deployed to Vertex AI Agent Engine
(`agents/deploy/deploy.py`, `vertexai.agent_engines`).

## Deployment

```
$ TOOLBOX_MCP_URL=http://localhost:5001 uv run --env-file .env python -m agents.deploy.deploy
...
AgentEngine created. Resource name: projects/492372502792/locations/us-central1/reasoningEngines/4557033143701340160
```

Getting there took five real, sequentially-discovered bugs, each only visible by
actually attempting the deploy (see `docs/DECISIONS.md` #051, #053, #054, #056, #057
for the full narrative — not repeated here):

1. `ToolboxSyncTool` objects aren't `deepcopy`-safe (a live thread/event loop/HTTP
   session) — `agent_engines.create()` deep-copies the agent tree before upload.
2. `location="global"` (correct for this project's direct Gemini calls) is rejected
   by Agent Engine specifically — found via bisection with a trivial one-tool agent.
3. `extra_packages` was never set, so the deployed container couldn't import our own
   code at all (`ModuleNotFoundError: No module named 'agents'`).
4. The requirements list was missing five real transitive imports (`openai`,
   `google-cloud-modelarmor`, `google-cloud-pubsub`, `google-cloud-bigquery`,
   `fastapi`) — traced live via `sys.modules` diffing, not guessed.
5. `GOOGLE_CLOUD_LOCATION=global` (the deployed agent's own Gemini calls) is a
   separate setting from the engine's `us-central1` deploy region — an earlier
   defensive fix had dropped both when only `GOOGLE_CLOUD_PROJECT` was actually
   reserved.

## A run started from the API completes

`POST /projects/demo/runs` (via `services/dashboard_api`, itself calling the deployed
engine's `create_session`/`stream_query`) against real Cloud SQL data:

```
$ curl -X POST .../projects/demo/runs -d '{"asset_id": "local-dev-asset", "mode": "clear"}'
200 {"run_id":"01M1P17RHC5QXPHJHRJH3QKEV0"}
```

Real events observed via the deployed engine's own `stream_query` (a separate,
directly-invoked verification run, `google.adk` client against the live resource):
`initialize_run` → `transfer_to_agent(CLEAR)` → `list_claims` (56 real pending claims,
including some pre-existing production data from earlier ingestion, not just seeded
fixtures) → `get_prior_decisions` per entity → `set_status` → ClaimTriage's batched
output → all four specialists dispatched in parallel (`verify_music_batch`,
`verify_brand_batch`, `verify_person_batch`, `verify_location_artwork_batch`) — the
full agent tree, running for real on the deployed resource, not `InMemoryRunner`.

## Streaming disconnection isn't run failure

A long `stream_query` iteration (real, many-claim batches) can outlive the client-side
gRPC streaming call's own duration limit — the local iterator raised
`FAILED_PRECONDITION: Reasoning Engine Execution failed` around the 10-minute mark
while Cloud Logging showed the deployed agent's own `gemini-3.5-flash` calls still
succeeding for several minutes afterward. The agent kept running server-side after the
client's stream disconnected (`docs/DECISIONS.md` #056) — confirmed by querying the
ledger directly afterward and seeing continued real writes.
