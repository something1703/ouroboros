"""Structured JSON logging. Every log line carries service, env, and (via contextvars) project_id/claim_id/trace_id."""

from __future__ import annotations

import logging
import os
import sys
from typing import cast

import structlog
from structlog.types import EventDict, WrappedLogger

_CONFIGURED = False


def configure_logging(*, service: str) -> None:
    """Call once at process start (service main / agent entrypoint / test conftest)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    env = os.environ.get("OUROBOROS_ENV", "dev")
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    def add_service_context(
        _logger: WrappedLogger, _method: str, event_dict: EventDict
    ) -> EventDict:
        event_dict.setdefault("service", service)
        event_dict.setdefault("env", env)
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            add_service_context,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    if not _CONFIGURED:
        configure_logging(service=os.environ.get("OUROBOROS_SERVICE", name))
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


def bind_context(**kwargs: object) -> None:
    """Bind fields (project_id, claim_id, trace_id, ...) onto every subsequent log line on this task/thread."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()
