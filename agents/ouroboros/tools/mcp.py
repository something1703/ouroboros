"""The public, read-only Toolbox proxy (Phase 5.6) attached to every Task run so
Parallel can call back into our ledger (PARALLEL_INTEGRATION.md §4.2). Shared between
the exposed `parallel.task_run` ADK tool and the specialists' internal Task calls.
"""

from __future__ import annotations

import os

from packages.common.errors import NotFound
from packages.common.secrets import get_secret
from packages.parallel_client.task import McpServer


def toolbox_mcp_servers() -> list[McpServer] | None:
    """Returns None (no MCP attachment) until PARALLEL_MCP_URL/PARALLEL_MCP_TOKEN are
    configured — lets specialists be built and tested before Phase 5.6 exists.
    `get_secret` (not a raw env var read) so the token is never duplicated as a plain
    `env_vars` entry on the deployed engine — same convention as every other secret."""
    url = os.environ.get("PARALLEL_MCP_URL")
    if not url:
        return None
    try:
        token = get_secret("PARALLEL_MCP_TOKEN")
    except NotFound:
        return None
    return [
        {
            "type": "url",
            "name": "ouroboros_ledger",
            "url": url,
            "headers": {"Authorization": f"Bearer {token}"},
            "allowed_tools": ["get_claim", "get_prior_decisions", "list_claims"],
        }
    ]
