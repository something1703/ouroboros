"""Webhook signature verification + event models. See PARALLEL_INTEGRATION.md §5 and
docs/vendor/parallel/README.md.

Parallel webhooks follow the Standard Webhooks spec: headers `webhook-id`,
`webhook-timestamp` (unix seconds), `webhook-signature` (space-separated
`v1,<base64 hmac>` values — verify against *any* of them, not just the first, per the
spec). Signed string: `f"{id}.{timestamp}.{raw_body}"`, HMAC-SHA256, key = the secret
with any `whsec_` prefix stripped, then base64-decoded.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Literal

from pydantic import BaseModel

# Standard Webhooks recommends rejecting anything outside this tolerance, guarding
# against a replayed (captured-and-resent) request — PHASE_04.md §4.5's "replayed"
# test vector.
_TIMESTAMP_TOLERANCE_S = 300


class WebhookVerificationError(ValueError):
    """A webhook's signature is missing, malformed, doesn't match, or is outside the
    replay-tolerance window."""


def _signing_key(secret: str) -> bytes:
    trimmed = secret.removeprefix("whsec_")
    return base64.b64decode(trimmed)


def _compute_signature(secret: str, webhook_id: str, webhook_timestamp: str, body: bytes) -> str:
    payload = f"{webhook_id}.{webhook_timestamp}.{body.decode()}".encode()
    digest = hmac.new(_signing_key(secret), payload, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def verify_signature(
    *,
    secret: str,
    webhook_id: str,
    webhook_timestamp: str,
    webhook_signature: str,
    body: bytes,
    now: float | None = None,
) -> None:
    """Raises `WebhookVerificationError` on any failure; returns None on success."""
    try:
        timestamp = int(webhook_timestamp)
    except ValueError as exc:
        raise WebhookVerificationError(
            f"malformed webhook-timestamp: {webhook_timestamp!r}"
        ) from exc

    current = now if now is not None else time.time()
    if abs(current - timestamp) > _TIMESTAMP_TOLERANCE_S:
        raise WebhookVerificationError(
            f"webhook-timestamp {timestamp} outside the {_TIMESTAMP_TOLERANCE_S}s tolerance"
        )

    expected = _compute_signature(secret, webhook_id, webhook_timestamp, body)
    candidates = [part.split(",", 1)[1] for part in webhook_signature.split() if "," in part]
    if not candidates:
        raise WebhookVerificationError(f"malformed webhook-signature: {webhook_signature!r}")

    if not any(hmac.compare_digest(expected, candidate) for candidate in candidates):
        raise WebhookVerificationError("signature does not match any provided value")


class MonitorEventDetected(BaseModel):
    type: Literal["monitor.event.detected"]
    timestamp: str
    monitor_id: str
    event_group_id: str
    metadata: dict[str, str] = {}

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> MonitorEventDetected:
        data = payload["data"]
        assert isinstance(data, dict)
        event = data["event"]
        assert isinstance(event, dict)
        return cls(
            type="monitor.event.detected",
            timestamp=str(payload["timestamp"]),
            monitor_id=str(data["monitor_id"]),
            event_group_id=str(event["event_group_id"]),
            metadata=dict(data.get("metadata") or {}),
        )


class TaskRunStatusEvent(BaseModel):
    type: Literal["task_run.status"]
    timestamp: str
    run_id: str
    status: str
    is_active: bool
    error_message: str | None = None
    metadata: dict[str, str] = {}

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> TaskRunStatusEvent:
        data = payload["data"]
        assert isinstance(data, dict)
        error = data.get("error")
        error_message = None
        if isinstance(error, dict):
            error_message = str(error.get("message"))
        return cls(
            type="task_run.status",
            timestamp=str(payload["timestamp"]),
            run_id=str(data["run_id"]),
            status=str(data["status"]),
            is_active=bool(data["is_active"]),
            error_message=error_message,
            metadata=dict(data.get("metadata") or {}),
        )


def parse_event(payload: dict[str, object]) -> MonitorEventDetected | TaskRunStatusEvent:
    event_type = payload.get("type")
    if event_type == "monitor.event.detected":
        return MonitorEventDetected.from_payload(payload)
    if event_type == "task_run.status":
        return TaskRunStatusEvent.from_payload(payload)
    raise ValueError(f"unrecognized webhook event type: {event_type!r}")
