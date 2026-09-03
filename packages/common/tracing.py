"""OpenTelemetry tracing exported to Cloud Trace. One span per claim verification, one trace across service boundaries."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter

AttributeValue = str | bool | int | float

if TYPE_CHECKING:
    from fastapi import FastAPI

_CONFIGURED = False


def configure_tracing(*, service: str) -> None:
    """Call once at process start. Exports to Cloud Trace when a GCP project is configured, else to stdout."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    resource = Resource.create({SERVICE_NAME: service})
    provider = TracerProvider(resource=resource)

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    exporter: SpanExporter
    if project_id:
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter

        exporter = CloudTraceSpanExporter(project_id=project_id)  # type: ignore[no-untyped-call]
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _CONFIGURED = True


def instrument_fastapi(app: FastAPI) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)


@contextmanager
def span(name: str, **attributes: AttributeValue) -> Iterator[trace.Span]:
    """`with span("verify", claim_id=claim_id): ...` — attributes are recorded as span attributes."""
    tracer = trace.get_tracer("ouroboros")
    with tracer.start_as_current_span(name) as current_span:
        for key, value in attributes.items():
            current_span.set_attribute(key, value)
        yield current_span
