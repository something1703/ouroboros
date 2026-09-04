# Phase 5.6 — two-way MCP evidence

`services/toolbox_public`: a bearer-token-gated, rate-limited reverse proxy in front of
the private `toolbox` service, exposing only the `parallel_readonly` toolset so a
Parallel Task run's `mcp_servers` callback can look up prior decisions without ever
holding real GCP credentials.

## A real, previously-undiscovered blocker

The first attempt to reach `services/toolbox_public` — from a Cloud Run Job with no VPC
connector, and separately from a real Parallel Task's `mcp_servers` callback path —
got a 404 with **zero corresponding request-log entries** on `toolbox` itself,
regardless of a valid ID token. `toolbox`'s `--ingress=internal` setting was silently
rejecting all such traffic at Cloud Run's edge, before the container ever saw the
request — this had never been exercised before (every earlier Toolbox call in this
whole session went through `localhost` in local dev). Fixed by widening to
`--ingress=all` (IAM — `--no-allow-unauthenticated` plus per-caller `run.invoker` — is
the only real gate either way); see `docs/DECISIONS.md` #052.

## Verified live, end-to-end, after the fix

A Cloud Run Job with **no VPC connector**, authenticated only via its own ID token,
calling `services/toolbox_public`:

```
--- unauthenticated (expect 401) ---
401
--- disallowed toolset, ledger_write (expect 404) ---
404
--- authenticated tools/call get_prior_decisions ---
HTTP_STATUS:200
--- healthz ---
{"ok": true, "service": "toolbox_public"}
```

`toolbox-public`'s own service logs for the same requests, confirming the tool name
comes straight off genai-toolbox's `Mcp-Name` request header (no body parsing needed):

```
INFO:  169.254.169.126:16042 - "POST /mcp/parallel_readonly HTTP/1.1" 401 Unauthorized
INFO:  169.254.169.126:16050 - "POST /mcp/ledger_write HTTP/1.1" 404 Not Found
HTTP Request: POST https://toolbox-...run.app/mcp/parallel_readonly "HTTP/1.1 200 OK"
INFO:  169.254.169.126:16066 - "POST /mcp/parallel_readonly HTTP/1.1" 200 OK
```

`agents/ouroboros/tools/mcp.py`'s `toolbox_mcp_servers()` attaches this exact URL +
token (via `get_secret`, never a plain env var — Secret Manager fallback, matching
every other secret in this repo) to every real `task.run()` call, with
`allowed_tools=["get_claim", "get_prior_decisions", "list_claims"]` — the same three
tools exercised directly above.
