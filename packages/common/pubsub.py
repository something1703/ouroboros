"""Thin Pub/Sub publish helper shared by every service that publishes an event
(`services/ingest` publishes `claims.extracted`; `webhook_receiver` and `reverify_worker`
publish their own topics in later phases — see ARCHITECTURE.md's event flow)."""

from __future__ import annotations

import json
import os
from functools import cache
from typing import Any

import google.cloud.pubsub_v1 as pubsub_v1


@cache
def _publisher() -> pubsub_v1.PublisherClient:
    return pubsub_v1.PublisherClient()


def publish_json(
    topic_id: str, payload: dict[str, Any], *, attributes: dict[str, str] | None = None
) -> str:
    """Publish `payload` as JSON bytes to `topic_id` in the current project, with
    optional Pub/Sub message attributes (PHASE_07.md §7.1: `webhook_receiver` publishes
    `verification.events` with `{kind, project_id, claim_id}` so a subscriber can filter/
    route without decoding the body first). Returns the published message ID (blocks on
    the publish future — every publisher here is already request-scoped, so there's no
    benefit to fire-and-forget)."""
    project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
    topic_path = _publisher().topic_path(project_id, topic_id)
    future = _publisher().publish(
        topic_path, json.dumps(payload).encode("utf-8"), **(attributes or {})
    )
    return str(future.result())
