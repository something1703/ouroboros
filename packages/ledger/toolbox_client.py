"""Thin wrapper around toolbox-core, loading MCP Toolbox toolsets for ADK agents.

Verified against the installed toolbox-core 1.x API (`ToolboxSyncClient.load_toolset`
returns `list[ToolboxSyncTool]`, itself directly usable as an ADK `FunctionTool`-style
callable — confirmed live in Phase 5 against a real `LlmAgent`).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping

from toolbox_core import ToolboxSyncClient
from toolbox_core.sync_tool import ToolboxSyncTool


def _toolbox_url() -> str:
    return os.environ.get("TOOLBOX_MCP_URL", "http://localhost:5000")


def _id_token_header(audience: str) -> str:
    """A fresh Google-signed ID token for `audience` — how a caller authenticates to
    the private (`--no-allow-unauthenticated`) Cloud Run `toolbox` service: sa-agent-
    engine's own identity when running for real, or a developer's `gcloud auth`
    session locally against the real deployed service. Minted fresh per call (passed
    as a callable in `client_headers`, not a cached string) since ID tokens are
    short-lived and toolbox-core re-invokes the callable on every request.
    """
    import google.auth.transport.requests
    import google.oauth2.id_token

    request = google.auth.transport.requests.Request()
    token: str = google.oauth2.id_token.fetch_id_token(request, audience)  # type: ignore[no-untyped-call]
    return f"Bearer {token}"


def load_toolset(name: str, *, url: str | None = None) -> list[ToolboxSyncTool]:
    """Load one named toolset (e.g. "ledger_read", "ledger_write") as ADK-ready tools.

    Deliberately does not close the underlying client: each returned ToolboxSyncTool
    holds a reference back to it and needs the connection alive for its whole
    lifetime (an ADK agent's, typically). There's nothing to await here — the client
    lives for the life of the process that called this.
    """
    toolbox_url = url or _toolbox_url()
    headers: Mapping[str, Callable[[], str] | str] | None = None
    if not toolbox_url.startswith("http://localhost"):
        headers = {"Authorization": lambda: _id_token_header(toolbox_url)}
    client = ToolboxSyncClient(toolbox_url, client_headers=headers)
    return client.load_toolset(name=name)
