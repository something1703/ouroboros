"""Monitor + Memory wrappers. See PARALLEL_INTEGRATION.md §4.6, §4.7."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from config.parallel import FORBIDDEN_MONITOR_PROCESSORS, MonitorFrequency
from packages.claims.models import MonitorRecord
from packages.parallel_client.client import call, env_metadata, get_client


class MonitorEvent(BaseModel):
    event_id: str
    event_type: str
    event_group_id: str | None = None
    error_message: str | None = None


def _monitor_processor(processor: str) -> str:
    if processor in FORBIDDEN_MONITOR_PROCESSORS:
        raise ValueError(f"monitor processor {processor!r} is forbidden")
    return processor


def create_snapshot(
    task_run_id: str,
    *,
    frequency: MonitorFrequency,
    webhook_url: str,
    claim_id: str,
    project_id: str,
    memory_scope_key: str | None = None,
) -> MonitorRecord:
    metadata: dict[str, str | float | bool] = dict(
        env_metadata(claim_id=claim_id, project_id=project_id, monitor_kind="snapshot")
    )

    def _call() -> object:
        return get_client().monitor.create(
            type="snapshot",
            frequency=frequency,
            settings={"task_run_id": task_run_id},
            webhook={"url": webhook_url, "event_types": ["monitor.event.detected"]},
            metadata=metadata,  # type: ignore[arg-type]
            memory_scope_key=memory_scope_key,
        )

    monitor = call(_call, api="monitor_create", sku="monitor.lite", claim_id=claim_id)
    return _to_domain(monitor, claim_id=claim_id, task_run_id=task_run_id, query=None)


def create_stream(
    query: str,
    *,
    frequency: MonitorFrequency,
    webhook_url: str,
    claim_id: str,
    project_id: str,
    location: str | None = None,
    memory_scope_key: str | None = None,
    processor: str = "lite",
) -> MonitorRecord:
    processor = _monitor_processor(processor)
    settings: dict[str, object] = {"query": query}
    if location is not None:
        settings["advanced_settings"] = {"location": location}
    metadata: dict[str, str | float | bool] = dict(
        env_metadata(claim_id=claim_id, project_id=project_id, monitor_kind="event_stream")
    )

    def _call() -> object:
        return get_client().monitor.create(
            type="event_stream",
            frequency=frequency,
            settings=settings,  # type: ignore[arg-type]
            processor=processor,  # type: ignore[arg-type]
            webhook={"url": webhook_url, "event_types": ["monitor.event.detected"]},
            metadata=metadata,  # type: ignore[arg-type]
            memory_scope_key=memory_scope_key,
        )

    sku = f"monitor.{processor}"
    monitor = call(_call, api="monitor_create", sku=sku, claim_id=claim_id)
    return _to_domain(monitor, claim_id=claim_id, task_run_id=None, query=query)


def update(
    monitor_id: str, *, frequency: MonitorFrequency | None = None, webhook_url: str | None = None
) -> None:
    webhook = (
        {"url": webhook_url, "event_types": ["monitor.event.detected"]} if webhook_url else None
    )

    def _call() -> object:
        return get_client().monitor.update(monitor_id, frequency=frequency, webhook=webhook)  # type: ignore[arg-type]

    call(_call, api="monitor_update", sku="monitor.update")


def cancel(monitor_id: str) -> None:
    def _call() -> object:
        return get_client().monitor.cancel(monitor_id)

    call(_call, api="monitor_cancel", sku="monitor.cancel")


def trigger(monitor_id: str) -> None:
    """Enqueues an immediate, off-schedule run of an existing Monitor (PHASE_07.md §7.6).
    Per Parallel's own docstring, this only emits a `monitor.event.detected` webhook if
    the triggered run actually detects a material change -- a no-op call is a normal,
    silent outcome, not a bug."""

    def _call() -> object:
        get_client().monitor.trigger(monitor_id)
        return None

    call(_call, api="monitor_trigger", sku="monitor.trigger")


def events(monitor_id: str, *, event_group_id: str | None = None) -> list[MonitorEvent]:
    def _call() -> object:
        return get_client().monitor.events(monitor_id, event_group_id=event_group_id)

    response = call(_call, api="monitor_events", sku="monitor.events")
    return [
        MonitorEvent(
            event_id=getattr(e, "event_id", ""),
            event_type=e.event_type or "unknown",
            event_group_id=getattr(e, "event_group_id", None),
            error_message=getattr(e, "error_message", None),
        )
        for e in response.events  # type: ignore[attr-defined]
    ]


def _to_domain(
    monitor: object, *, claim_id: str, task_run_id: str | None, query: str | None
) -> MonitorRecord:
    return MonitorRecord(
        monitor_id=monitor.monitor_id,  # type: ignore[attr-defined]
        claim_id=claim_id,
        type=monitor.type,  # type: ignore[attr-defined]
        task_run_id=task_run_id,
        query=query,
        frequency=monitor.frequency,  # type: ignore[attr-defined]
        status=monitor.status,  # type: ignore[attr-defined]
        created_at=datetime.now(UTC),
    )
