"""Slack alerts via an Incoming Webhook URL (`SLACK_WEBHOOK_URL`, Secret Manager). Block
Kit messages, posted by `reverify_worker` on a risk change (PHASE_07.md §7.4 "Option
B" — implemented regardless of whether Parallel's own Slack Monitor integration
(Option A) is also installed, since Option A can't compute a *risk* change on its own,
only relay a raw Monitor event."""

from __future__ import annotations

import os

import httpx

from packages.common.logging import get_logger
from packages.common.secrets import get_secret

log = get_logger(__name__)

_TIMEOUT_S = 5.0


def post_risk_change_alert(
    *,
    project_id: str,
    claim_id: str,
    claim_text: str,
    risk_level: str,
    rationale: str,
    delta: dict[str, dict[str, object]],
    top_citation: str | None,
) -> None:
    """Raises on a genuine delivery failure (bad webhook URL, Slack 4xx/5xx) — the
    caller decides whether that should be swallowed (a Slack outage must never fail the
    re-verification it's reporting on)."""
    webhook_url = get_secret("SLACK_WEBHOOK_URL")
    dashboard_base_url = os.environ.get("DASHBOARD_BASE_URL", "https://dashboard.ouroboros.app")
    deep_link = f"{dashboard_base_url}/projects/{project_id}/claims/{claim_id}"

    delta_lines = (
        "\n".join(
            f"• *{field}*: `{change.get('from')}` → `{change.get('to')}`"
            for field, change in delta.items()
        )
        or "_no field-level delta available_"
    )

    blocks: list[dict[str, object]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":rotating_light: Risk changed to *{risk_level.upper()}* for a claim",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f">{claim_text}"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Rationale:* {rationale}\n*Changed:*\n{delta_lines}",
            },
        },
    ]
    if top_citation:
        blocks.append(
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"<{top_citation}|Top citation>"}],
            }
        )
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"<{deep_link}|View in Ouroboros>"},
        }
    )

    response = httpx.post(webhook_url, json={"blocks": blocks}, timeout=_TIMEOUT_S)
    response.raise_for_status()
    log.info("slack_alert_sent", project_id=project_id, claim_id=claim_id, risk_level=risk_level)
