"""services/webhook_receiver — Cloud Run, **public** ingress, `sa-webhook`. Verifies
every inbound Parallel Monitor/Task webhook's signature, dedupes by the delivery's own
`webhook-id` header, and republishes onto Pub/Sub `verification.events` for
`reverify_worker` to actually act on. PHASE_07.md §7.1, ARCHITECTURE.md §2.5.

Deliberately thin: signature verification + dedup + republish, nothing else — keeps
this public-facing surface's blast radius small and its response time well under
Parallel's own webhook timeout (PARALLEL_INTEGRATION.md §5: "respond 200 within 2s;
all work happens after publishing").
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import FastAPI, Request, Response

from packages.common.logging import get_logger
from packages.common.pubsub import publish_json
from packages.common.secrets import get_secret
from packages.common.tracing import configure_tracing, flush_tracing, instrument_fastapi
from packages.ledger.projections import get_client as get_firestore_client
from packages.parallel_client.webhooks import (
    MonitorEventDetected,
    TaskRunStatusEvent,
    WebhookVerificationError,
    parse_event,
    verify_signature,
)

configure_tracing(service="webhook_receiver")

app = FastAPI()
instrument_fastapi(app)
log = get_logger(__name__)

VERIFICATION_EVENTS_TOPIC = "verification.events"
_DEDUPE_COLLECTION = "webhook_dedupe"
_DEDUPE_TTL = timedelta(days=7)


@app.get("/status")
def status() -> dict[str, object]:
    return {"ok": True, "service": "webhook_receiver"}


@app.post("/webhooks/parallel/{event_kind}")
async def handle_webhook(event_kind: Literal["monitor", "task"], request: Request) -> Response:
    body = await request.body()
    webhook_id = request.headers.get("webhook-id", "")
    webhook_timestamp = request.headers.get("webhook-timestamp", "")
    webhook_signature = request.headers.get("webhook-signature", "")

    try:
        verify_signature(
            secret=get_secret("PARALLEL_WEBHOOK_SECRET"),
            webhook_id=webhook_id,
            webhook_timestamp=webhook_timestamp,
            webhook_signature=webhook_signature,
            body=body,
        )
    except WebhookVerificationError as exc:
        log.warning("webhook_signature_invalid", event_kind=event_kind, reason=str(exc))
        return Response(status_code=401)

    if not webhook_id:
        # Standard Webhooks guarantees this header on every real delivery; its absence
        # means this isn't a real Parallel webhook even if the signature (against an
        # empty webhook_id) somehow matched — reject rather than dedupe on an empty key.
        log.warning("webhook_missing_id", event_kind=event_kind)
        return Response(status_code=401)

    if _already_processed(webhook_id):
        log.info("webhook_duplicate", webhook_id=webhook_id, event_kind=event_kind)
        return Response(status_code=200)

    payload = json.loads(body)
    try:
        event = parse_event(payload)
    except ValueError as exc:
        # A permanently-unparseable payload will never succeed on retry — ack (200) so
        # Parallel stops redelivering it, rather than 500 into an infinite retry loop.
        log.warning("webhook_unrecognized_event", event_kind=event_kind, error=str(exc))
        return Response(status_code=200)

    claim_id, project_id = _route(event)
    publish_json(
        VERIFICATION_EVENTS_TOPIC,
        payload,
        attributes={"kind": event_kind, "project_id": project_id, "claim_id": claim_id},
    )
    _mark_processed(webhook_id)

    flush_tracing()
    return Response(status_code=200)


def _route(event: MonitorEventDetected | TaskRunStatusEvent) -> tuple[str, str]:
    """`claim_id`/`project_id` always come from `metadata` (echoed back verbatim from
    whatever `monitor.create`/`task_run.create` sent, ADK_AGENTS.md/PARALLEL_INTEGRATION.md
    §4.6) — never guessed from the event's own business fields, which don't carry them."""
    return event.metadata.get("claim_id", ""), event.metadata.get("project_id", "")


def _already_processed(webhook_id: str) -> bool:
    doc = get_firestore_client().collection(_DEDUPE_COLLECTION).document(webhook_id).get()
    return doc.exists


def _mark_processed(webhook_id: str) -> None:
    now = datetime.now(UTC)
    get_firestore_client().collection(_DEDUPE_COLLECTION).document(webhook_id).set(
        {"processed_at": now, "expires_at": now + _DEDUPE_TTL}
    )
