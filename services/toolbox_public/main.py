"""services/toolbox_public — Cloud Run, FastAPI (PHASE_05.md §5.6). A public,
bearer-token-gated reverse proxy in front of the private `toolbox` service's MCP
endpoint, exposing only the `parallel_readonly` toolset — never `ledger_write` — so a
Parallel Task run's `mcp_servers` callback can look up prior decisions without this
service (or Parallel) ever holding real GCP credentials.

Genai-toolbox's MCP transport already puts the tool name being called on the
`Mcp-Name` request header (and the JSON-RPC method on `Mcp-Method`), so this proxy
never needs to parse the request body to log or gate on it — verified by reading
toolbox-core's own transport implementation, not guessed.

Rate limiting is a single in-memory counter, correct for one Cloud Run instance (the
expected scale here — this endpoint's only caller is Parallel's own infrastructure, not
end users) but not correct across multiple concurrent instances. Revisit with a shared
counter (e.g. Firestore or Redis) if traffic ever justifies scaling this out.
"""

from __future__ import annotations

import os
import time
from collections import deque

import google.auth.transport.requests
import google.oauth2.id_token
import httpx
from fastapi import FastAPI, HTTPException, Request, Response

from packages.common.logging import get_logger
from packages.common.secrets import get_secret
from packages.common.tracing import configure_tracing, instrument_fastapi

configure_tracing(service="toolbox_public")
log = get_logger(__name__)

app = FastAPI(title="Ouroboros Toolbox Public Proxy")
instrument_fastapi(app)

_ALLOWED_TOOLSET = "parallel_readonly"
_RATE_LIMIT_PER_MIN = 60
_RATE_WINDOW_SECONDS = 60.0
_recent_calls: deque[float] = deque()


def _id_token_header(audience: str) -> str:
    """A fresh Google-signed ID token for `audience`, this service's own identity
    (sa-toolbox-public) authenticating to the private toolbox service."""
    request = google.auth.transport.requests.Request()
    token: str = google.oauth2.id_token.fetch_id_token(request, audience)  # type: ignore[no-untyped-call]
    return f"Bearer {token}"


def _check_rate_limit() -> None:
    now = time.monotonic()
    while _recent_calls and now - _recent_calls[0] > _RATE_WINDOW_SECONDS:
        _recent_calls.popleft()
    if len(_recent_calls) >= _RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "rate limit exceeded")
    _recent_calls.append(now)


@app.get("/status")
def status() -> dict[str, object]:
    return {"ok": True, "service": "toolbox_public"}


@app.post("/mcp/{toolset}")
async def proxy(toolset: str, request: Request) -> Response:
    if toolset != _ALLOWED_TOOLSET:
        raise HTTPException(404, "not found")

    token = get_secret("PARALLEL_MCP_TOKEN")
    if request.headers.get("authorization") != f"Bearer {token}":
        raise HTTPException(401, "invalid bearer token")

    caller = request.client.host if request.client else "unknown"
    tool_name = request.headers.get("mcp-name", "?")
    mcp_method = request.headers.get("mcp-method", "?")
    log.info("mcp_tool_call", tool_name=tool_name, mcp_method=mcp_method, caller=caller)

    _check_rate_limit()

    backend_url = os.environ["TOOLBOX_BACKEND_URL"]
    body = await request.body()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{backend_url}/mcp/{toolset}",
            content=body,
            headers={
                "content-type": request.headers.get("content-type", "application/json"),
                "mcp-protocol-version": request.headers.get("mcp-protocol-version", ""),
                "mcp-method": mcp_method,
                "mcp-name": tool_name,
                "authorization": _id_token_header(backend_url),
            },
        )

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )
