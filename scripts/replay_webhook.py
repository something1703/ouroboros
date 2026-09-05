"""Replays a recorded webhook fixture against a real `webhook_receiver` deployment,
signing it exactly the way Parallel would (Standard Webhooks: `webhook-id`,
`webhook-timestamp`, `webhook-signature`). PHASE_07.md §7.1's acceptance test:
`make replay-webhook FIXTURE=monitor_event_1`.

Reads the fixture from `fixtures/webhooks/<fixture>.json` and the real signing secret
via `packages.common.secrets.get_secret("PARALLEL_WEBHOOK_SECRET")` — the same
Secret Manager value (or local env var override) `webhook_receiver` itself verifies
against, so a successful replay here is a genuine signature match, not a bypass.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4

from packages.common.secrets import get_secret

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "webhooks"


def _sign(secret: str, *, webhook_id: str, webhook_timestamp: str, body: bytes) -> str:
    trimmed = secret.removeprefix("whsec_")
    key = base64.b64decode(trimmed)
    payload = f"{webhook_id}.{webhook_timestamp}.{body.decode()}".encode()
    digest = hmac.new(key, payload, hashlib.sha256).digest()
    return f"v1,{base64.b64encode(digest).decode()}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", required=True, help="fixtures/webhooks/<fixture>.json")
    parser.add_argument(
        "--base-url",
        default="https://webhook-receiver-492372502792.us-central1.run.app",
        help="webhook_receiver's real base URL",
    )
    parser.add_argument(
        "--event-kind",
        choices=["monitor", "task"],
        default="monitor",
        help="which /webhooks/parallel/{event_kind} route to hit",
    )
    parser.add_argument(
        "--tamper",
        action="store_true",
        help="send a deliberately wrong signature, to test the 401 path",
    )
    parser.add_argument(
        "--webhook-id",
        default=None,
        help="fix the webhook-id header (e.g. to two identical calls to test dedup) "
        "instead of generating a fresh one each run",
    )
    args = parser.parse_args()

    fixture_path = _FIXTURES_DIR / f"{args.fixture}.json"
    body = fixture_path.read_bytes()

    secret = get_secret("PARALLEL_WEBHOOK_SECRET")
    webhook_id = args.webhook_id or str(uuid4())
    webhook_timestamp = str(int(time.time()))
    signature = (
        "v1,dGFtcGVyZWQ="
        if args.tamper
        else _sign(secret, webhook_id=webhook_id, webhook_timestamp=webhook_timestamp, body=body)
    )

    req = urllib.request.Request(
        f"{args.base_url}/webhooks/parallel/{args.event_kind}",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "webhook-id": webhook_id,
            "webhook-timestamp": webhook_timestamp,
            "webhook-signature": signature,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"status={resp.status}")
    except urllib.error.HTTPError as exc:
        print(f"status={exc.code} body={exc.read().decode()[:500]}")


if __name__ == "__main__":
    main()
