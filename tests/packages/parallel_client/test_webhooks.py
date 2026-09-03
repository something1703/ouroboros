"""Signature verification test vectors (valid, tampered, replayed) and event payload
parsing, per PHASE_04.md §4.5's acceptance criteria and the Standard Webhooks spec
verified in docs/vendor/parallel/README.md.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

import pytest

from packages.parallel_client.webhooks import (
    MonitorEventDetected,
    TaskRunStatusEvent,
    WebhookVerificationError,
    parse_event,
    verify_signature,
)

_SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"
_WEBHOOK_ID = "msg_p5jXN8AQM9LWM0D4loKWxJek"
_BODY = b'{"type":"monitor.event.detected","timestamp":"2026-09-03T12:00:00Z","data":{}}'


def _sign(secret: str, webhook_id: str, timestamp: str, body: bytes) -> str:
    key = base64.b64decode(secret.removeprefix("whsec_"))
    payload = f"{webhook_id}.{timestamp}.{body.decode()}".encode()
    digest = hmac.new(key, payload, hashlib.sha256).digest()
    return f"v1,{base64.b64encode(digest).decode()}"


def test_valid_signature_verifies() -> None:
    now = time.time()
    timestamp = str(int(now))
    signature = _sign(_SECRET, _WEBHOOK_ID, timestamp, _BODY)
    verify_signature(
        secret=_SECRET,
        webhook_id=_WEBHOOK_ID,
        webhook_timestamp=timestamp,
        webhook_signature=signature,
        body=_BODY,
        now=now,
    )  # does not raise


def test_valid_signature_among_multiple_candidates_verifies() -> None:
    """Standard Webhooks allows space-separated multi-version signatures — a match on
    any one of them is sufficient."""
    now = time.time()
    timestamp = str(int(now))
    real_signature = _sign(_SECRET, _WEBHOOK_ID, timestamp, _BODY)
    combined = f"v0,bm9wZQ== {real_signature}"
    verify_signature(
        secret=_SECRET,
        webhook_id=_WEBHOOK_ID,
        webhook_timestamp=timestamp,
        webhook_signature=combined,
        body=_BODY,
        now=now,
    )


def test_tampered_body_fails() -> None:
    now = time.time()
    timestamp = str(int(now))
    signature = _sign(_SECRET, _WEBHOOK_ID, timestamp, _BODY)
    tampered_body = _BODY.replace(b"monitor.event.detected", b"monitor.event.faked!!")
    with pytest.raises(WebhookVerificationError, match="does not match"):
        verify_signature(
            secret=_SECRET,
            webhook_id=_WEBHOOK_ID,
            webhook_timestamp=timestamp,
            webhook_signature=signature,
            body=tampered_body,
            now=now,
        )


def test_wrong_secret_fails() -> None:
    now = time.time()
    timestamp = str(int(now))
    signature = _sign(_SECRET, _WEBHOOK_ID, timestamp, _BODY)
    with pytest.raises(WebhookVerificationError, match="does not match"):
        verify_signature(
            secret="whsec_" + base64.b64encode(b"a-completely-different-key-32by").decode(),
            webhook_id=_WEBHOOK_ID,
            webhook_timestamp=timestamp,
            webhook_signature=signature,
            body=_BODY,
            now=now,
        )


def test_replayed_old_timestamp_fails() -> None:
    """A captured-and-resent request: signature is genuinely valid for its own
    timestamp, but that timestamp is far in the past by the time it's checked."""
    old_timestamp = str(int(time.time()) - 3600)
    signature = _sign(_SECRET, _WEBHOOK_ID, old_timestamp, _BODY)
    with pytest.raises(WebhookVerificationError, match="tolerance"):
        verify_signature(
            secret=_SECRET,
            webhook_id=_WEBHOOK_ID,
            webhook_timestamp=old_timestamp,
            webhook_signature=signature,
            body=_BODY,
        )


def test_malformed_signature_header_fails() -> None:
    now = time.time()
    timestamp = str(int(now))
    with pytest.raises(WebhookVerificationError, match="malformed"):
        verify_signature(
            secret=_SECRET,
            webhook_id=_WEBHOOK_ID,
            webhook_timestamp=timestamp,
            webhook_signature="not-a-valid-signature-header",
            body=_BODY,
            now=now,
        )


def test_parse_monitor_event_detected() -> None:
    payload = {
        "type": "monitor.event.detected",
        "timestamp": "2025-12-10T19:00:36.199543+00:00",
        "data": {
            "monitor_id": "monitor_b0079f70195e4258a3b982c1b6d8bd3a",
            "event": {"event_group_id": "mevtgrp_35ab7d16b00f412b9d6b6c0eff1f49733b5cf0b02056a29c"},
            "metadata": {"external_id": "acme-monitor-001"},
        },
    }
    event = parse_event(payload)
    assert isinstance(event, MonitorEventDetected)
    assert event.monitor_id == "monitor_b0079f70195e4258a3b982c1b6d8bd3a"
    assert event.event_group_id == "mevtgrp_35ab7d16b00f412b9d6b6c0eff1f49733b5cf0b02056a29c"
    assert event.metadata == {"external_id": "acme-monitor-001"}


def test_parse_task_run_status_completed() -> None:
    payload = {
        "type": "task_run.status",
        "timestamp": "2025-04-23T20:21:48.037943Z",
        "data": {
            "run_id": "trun_9907962f83aa4d9d98fd7f4bf745d654",
            "status": "completed",
            "is_active": False,
            "warnings": None,
            "error": None,
            "processor": "core",
            "metadata": {"key": "value"},
        },
    }
    event = parse_event(payload)
    assert isinstance(event, TaskRunStatusEvent)
    assert event.run_id == "trun_9907962f83aa4d9d98fd7f4bf745d654"
    assert event.status == "completed"
    assert event.is_active is False
    assert event.error_message is None


def test_parse_task_run_status_failed_carries_error_message() -> None:
    payload = {
        "type": "task_run.status",
        "timestamp": "2025-04-23T20:21:48.037943Z",
        "data": {
            "run_id": "trun_9907962f83aa4d9d98fd7f4bf745d654",
            "status": "failed",
            "is_active": False,
            "error": {"message": "Task execution failed", "details": "Additional error details"},
            "metadata": {},
        },
    }
    event = parse_event(payload)
    assert isinstance(event, TaskRunStatusEvent)
    assert event.status == "failed"
    assert event.error_message == "Task execution failed"


def test_parse_unrecognized_event_type_raises() -> None:
    with pytest.raises(ValueError, match="unrecognized"):
        parse_event({"type": "something.else", "data": {}})
