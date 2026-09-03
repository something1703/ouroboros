"""Thin wrapper around toolbox-core, loading MCP Toolbox toolsets for ADK agents.

Verified against the installed toolbox-core 1.x API (`ToolboxSyncClient.load_toolset`
returns `list[ToolboxSyncTool]`) — not guessed. Whether ADK's `LlmAgent(tools=...)`
accepts these directly or needs each wrapped in `google.adk.tools.FunctionTool` is a
Phase 5 question (no ADK agent exists yet to verify against); this module hands back
the raw `ToolboxSyncTool` list either way.
"""

from __future__ import annotations

import os

from toolbox_core import ToolboxSyncClient
from toolbox_core.sync_tool import ToolboxSyncTool


def _toolbox_url() -> str:
    return os.environ.get("TOOLBOX_MCP_URL", "http://localhost:5000")


def load_toolset(name: str, *, url: str | None = None) -> list[ToolboxSyncTool]:
    """Load one named toolset (e.g. "ledger_read", "ledger_write") as ADK-ready tools.

    Deliberately does not close the underlying client: each returned ToolboxSyncTool
    holds a reference back to it and needs the connection alive for its whole
    lifetime (an ADK agent's, typically). There's nothing to await here — the client
    lives for the life of the process that called this.
    """
    client = ToolboxSyncClient(url or _toolbox_url())
    return client.load_toolset(name=name)
