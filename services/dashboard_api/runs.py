"""Starts a CLEAR/TRUE CUT/Ask run on the deployed Agent Engine (PHASE_05.md §5.5).

Fire-and-forget from the HTTP handler's perspective: `start_run` writes an initial
`runs/{run_id}` Firestore doc and hands the actual multi-minute run to a background
task, returning `run_id` immediately. The agent's own tool calls (`write_run_progress`,
`write_claim_summary`, `write_project_summary`) update Firestore directly as part of
its own remote execution on Agent Engine — not this process — so this module's
background task only needs to drain the event stream to notice when the run ends
(and record that), not to relay progress itself.

Cloud Run's request-based CPU allocation freezes a container's CPU between HTTP
responses (see `packages/common/tracing.py`'s `flush_tracing` docstring for the same
constraint hit elsewhere in this repo): once `start_run` returns its response, this
background task's own consumption of the stream may stall until the next request wakes
the container. That's fine here — the actual computation is remote (Agent Engine), so
a stalled local `for` loop only delays *this process's* "done" bookkeeping, not the
run itself.
"""

from __future__ import annotations

import asyncio
import json
import os
from functools import cache

import vertexai
from sqlalchemy import text
from vertexai import agent_engines
from vertexai.agent_engines import AgentEngine

from packages.common.ids import new_ulid
from packages.common.logging import get_logger
from packages.ledger.db import session_scope
from packages.ledger.projections import Projector

log = get_logger(__name__)
_projector = Projector()


class _RunAlreadyActive(Exception):
    """A concurrent run is already in progress for this project (see
    `_drive_run_sync`'s advisory-lock docstring)."""


@cache
def _engine() -> AgentEngine:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    region = os.environ.get("OUROBOROS_REGION", "us-central1")
    resource_name = os.environ["AGENT_ENGINE_RESOURCE_NAME"]
    vertexai.init(project=project, location=region)
    return agent_engines.get(resource_name)


def start_run(project_id: str, asset_id: str, *, mode: str = "clear") -> str:
    """Kicks off a run and returns its `run_id` immediately, without waiting for the
    run to finish."""
    run_id = new_ulid()
    _projector.run_progress(project_id, run_id, stage="queued", done=0, total=0)
    task = asyncio.create_task(_drive_run(project_id, asset_id, run_id, mode=mode))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return run_id


# A bare `asyncio.create_task` result must be kept referenced somewhere, or the event
# loop is free to garbage-collect it mid-run (a well-known asyncio footgun).
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


async def _drive_run(project_id: str, asset_id: str, run_id: str, *, mode: str) -> None:
    try:
        await asyncio.to_thread(_drive_run_sync, project_id, asset_id, run_id, mode=mode)
        _projector.run_progress(project_id, run_id, stage="done", done=0, total=0)
    except _RunAlreadyActive:
        log.warning("run_skipped_concurrent", project_id=project_id, run_id=run_id)
        _projector.run_progress(project_id, run_id, stage="skipped_concurrent", done=0, total=0)
    except Exception as exc:
        log.error("run_failed", project_id=project_id, run_id=run_id, error=str(exc))
        _projector.run_progress(project_id, run_id, stage="error", done=0, total=0)


def _drive_run_sync(project_id: str, asset_id: str, run_id: str, *, mode: str) -> None:
    # A Postgres advisory lock, held for this whole function's duration on the one
    # session/connection that acquires it (session_scope's `with` block keeps that
    # connection checked out the entire time, so the lock can't be silently released
    # by SQLAlchemy reclaiming the connection mid-run). Found live (docs/DECISIONS.md
    # #076): a stalled CLEAR pass being retriggered every few minutes, combined with
    # the Agent Engine's own max_instances=2, let two `stream_query` sessions run
    # genuinely concurrently against the same project -- both saw the same claim's
    # `has_monitor=false` before either had committed its own `record_monitor` write,
    # and both created a real, separate Monitor at Parallel for it. `pg_try_advisory_lock`
    # is non-blocking (returns immediately, true/false) and this repo already runs a
    # single Cloud SQL instance, so a plain lock keyed by `hashtext(project_id)` is
    # enough -- no new table, no migration.
    with session_scope() as session:
        acquired = session.execute(
            text("SELECT pg_try_advisory_lock(hashtext(:project_id))"), {"project_id": project_id}
        ).scalar()
        if not acquired:
            raise _RunAlreadyActive(project_id)
        try:
            _stream_run(project_id, asset_id, run_id, mode=mode)
        finally:
            session.execute(
                text("SELECT pg_advisory_unlock(hashtext(:project_id))"),
                {"project_id": project_id},
            )


def _stream_run(project_id: str, asset_id: str, run_id: str, *, mode: str) -> None:
    # create_session/stream_query aren't on AgentEngine's class -- they're attached to
    # the *instance* at __init__ from the deployed engine's own operation_schemas
    # (verified live via _register_api_methods_or_raise; DECISIONS.md #056), invisible
    # to mypy. Real signatures confirmed against the underlying AdkApp class.
    engine = _engine()
    adk_session = engine.create_session(user_id=project_id)  # type: ignore[attr-defined]
    message = json.dumps({"project_id": project_id, "asset_id": asset_id, "mode": mode})
    event_count = 0
    for _event in engine.stream_query(  # type: ignore[attr-defined]
        message=message, user_id=project_id, session_id=adk_session["id"]
    ):
        event_count += 1
    if event_count == 0:
        # Found live (docs/DECISIONS.md #068): when the remote Agent Engine worker
        # handling this stream dies mid-flight (e.g. an OOM kill), stream_query's
        # generator just ends -- it doesn't raise -- so without this check the run got
        # marked "done" in Firestore despite doing zero work, indistinguishable from a
        # real (if oddly instant) success.
        raise RuntimeError(
            f"stream_query yielded no events for run {run_id} -- the remote worker "
            "likely died before doing any work"
        )
