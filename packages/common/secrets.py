"""Secret Manager access with an in-process cache; falls back to env vars for local dev.

Never log a secret value. Never put a secret in a URL.
"""

from __future__ import annotations

import os
from functools import cache, lru_cache

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import secretmanager

from packages.common.errors import NotFound
from packages.common.logging import get_logger

log = get_logger(__name__)


@cache
def _client() -> secretmanager.SecretManagerServiceClient:
    return secretmanager.SecretManagerServiceClient()


@lru_cache(maxsize=64)
def get_secret(name: str, *, version: str = "latest") -> str:
    """Return a secret's value.

    Resolution order: an env var of the same name (local dev / CI), then
    Secret Manager under `GOOGLE_CLOUD_PROJECT` (Cloud Run, Agent Engine).
    Cached in-process for the life of the container — secrets don't rotate
    mid-request, and a redeploy picks up new versions.
    """
    env_value = os.environ.get(name)
    if env_value:
        return env_value

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise NotFound("secret", f"{name} (no env var set and GOOGLE_CLOUD_PROJECT is unset)")

    secret_path = _client().secret_version_path(project_id, name, version)
    try:
        response = _client().access_secret_version(name=secret_path)
    except GoogleAPICallError as exc:
        log.error("secret_access_failed", secret_name=name, error=str(exc))
        raise NotFound("secret", name) from exc

    return response.payload.data.decode("utf-8")
