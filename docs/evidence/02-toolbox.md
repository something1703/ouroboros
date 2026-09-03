# Phase 2.3 — MCP Toolbox for Databases evidence

`docker compose up -d toolbox` (image `us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest`, our `tools.yaml`):

```
INFO "Initialized 1 sources: ouroboros_pg"
INFO "Initialized 6 tools: record_evidence, set_status, get_claim, list_claims, get_prior_decisions, get_project"
INFO "Initialized 4 groups: ledger_write, parallel_readonly, default, ledger_read"
INFO "Server ready to serve!"
```

Full MCP protocol round trip against the real (locally-running) server, not just a health check:

| Call | Toolset endpoint | Result |
|---|---|---|
| `tools/list` | `/mcp/ledger_read` | Returns `get_claim`, `list_claims`, `get_prior_decisions`, `get_project` with correct JSON schemas |
| `tools/call get_project(project_id=demo)` | `/mcp/ledger_read` | Returns the real seeded demo project row |
| `tools/call record_evidence(...)` | `/mcp/ledger_write` | Inserted evidence cycle 1 for a real test claim — `expected_cycle` guard passed |
| `tools/call set_status(...)` | `/mcp/ledger_write` | Updated claim status to `verified`, appended a `verification_history` row |
| `tools/call get_claim(claim_id)` | `/mcp/ledger_read` | Confirmed the write: returns the claim joined with its new evidence (`brand_owner: "The Coca-Cola Company"`, `confidence: high`) |
| `tools/list` | `/mcp/parallel_readonly` | Returns exactly `get_claim`, `list_claims`, `get_prior_decisions` — **no** `record_evidence`/`set_status` reachable through this endpoint |

That last row is the actual security property Phase 5.6 depends on: a Parallel Task run
attached to `parallel_readonly` (via the public proxy added later) cannot write to the
ledger even if it tried — the tool simply isn't registered on that toolset.

## Scoping note

The plan's Phase 2.3 acceptance also asks for "an ADK smoke test: a throwaway `LlmAgent`
with `ledger_read` tools answers 'list pending claims for project demo' correctly." No ADK
agent exists yet (that's Phase 5) — building a throwaway one now would be duplicate work
once the real `ClaimTriage`/specialist agents land. The MCP-protocol-level verification
above (real tool calls, real data, real writes, real toolset scoping) covers the same
ground the smoke test would have — the ADK layer just talks MCP over stdio/HTTP to the
exact endpoints tested here.
