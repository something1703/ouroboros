# services/toolbox_public

A public, bearer-token-gated reverse proxy in front of the private `toolbox` service's
MCP endpoint. Exposes only the `parallel_readonly` toolset (`get_claim`, `list_claims`,
`get_prior_decisions`) to Parallel Task's `mcp_servers` callback — never
`ledger_write`. Built in Phase 5.6.
