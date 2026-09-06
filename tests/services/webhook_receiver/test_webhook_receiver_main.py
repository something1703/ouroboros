"""PHASE_09.md §9.5: duplicate webhook deliveries (the same `webhook-id` twice)
produce only one republish onto Pub/Sub, not two -- exercised against the real
`handle_webhook` route (real signature verification, a real valid HMAC signature
built the same way `tests/packages/parallel_client/test_webhooks.py` does) with only
Firestore, Secret Manager, and Pub/Sub publishing mocked (no real network/GCP calls).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

import services.webhook_receiver.main as webhook_receiver

_SECRET = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"  # pragma: allowlist secret — same fake test vector as tests/packages/parallel_client/test_webhooks.py
_WEBHOOK_ID = "msg_p5jXN8AQM9LWM0D4loKWxJek"
_BODY = (
    b'{"type":"monitor.event.detected","timestamp":"2026-09-06T12:00:00Z",'
    b'"data":{"monitor_id":"mon_1",'
    b'"event":{"event_group_id":"grp_1"},'
    b'"metadata":{"claim_id":"claim-1","project_id":"demo"}}}'
)


def _sign(secret: str, webhook_id: str, timestamp: str, body: bytes) -> str:
    key = base64.b64decode(secret.removeprefix("whsec_"))
    payload = f"{webhook_id}.{timestamp}.{body.decode()}".encode()
    digest = hmac.new(key, payload, hashlib.sha256).digest()
    return f"v1,{base64.b64encode(digest).decode()}"


class _FakeDoc:
    def __init__(self, exists: bool = False) -> None:
        self.exists = exists

    def set(self, data: dict[str, Any]) -> None:
        self.exists = True


class _FakeDocRef:
    def __init__(self, doc: _FakeDoc) -> None:
        self._doc = doc

    def get(self) -> _FakeDoc:
        return self._doc

    def set(self, data: dict[str, Any]) -> None:
        self._doc.set(data)


class _FakeCollection:
    def __init__(self, docs: dict[str, _FakeDoc]) -> None:
        self._docs = docs

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(self._docs.setdefault(doc_id, _FakeDoc()))


class _FakeFirestoreClient:
    def __init__(self) -> None:
        self._docs: dict[str, _FakeDoc] = {}

    def collection(self, _name: str) -> _FakeCollection:
        return _FakeCollection(self._docs)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(webhook_receiver, "get_secret", lambda name: _SECRET)
    fake_firestore = _FakeFirestoreClient()
    monkeypatch.setattr(webhook_receiver, "get_firestore_client", lambda: fake_firestore)
    monkeypatch.setattr(webhook_receiver, "publish_json", lambda *a, **kw: None)
    return TestClient(webhook_receiver.app)


def _post(client: TestClient) -> Any:
    timestamp = str(int(time.time()))
    signature = _sign(_SECRET, _WEBHOOK_ID, timestamp, _BODY)
    return client.post(
        "/webhooks/parallel/monitor",
        content=_BODY,
        headers={
            "webhook-id": _WEBHOOK_ID,
            "webhook-timestamp": timestamp,
            "webhook-signature": signature,
            "content-type": "application/json",
        },
    )


def test_first_delivery_publishes_and_second_identical_delivery_does_not(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    publish_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        webhook_receiver,
        "publish_json",
        lambda *a, **kw: publish_calls.append((a, kw)),
    )

    first = _post(client)
    assert first.status_code == 200
    assert len(publish_calls) == 1

    second = _post(client)
    assert second.status_code == 200  # still acked, not rejected
    assert len(publish_calls) == 1  # but not republished a second time
