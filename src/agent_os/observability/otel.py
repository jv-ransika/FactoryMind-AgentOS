from __future__ import annotations

import os
from typing import Any


def init_otel(service_name: str = "agent-os") -> dict[str, Any]:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        return {"enabled": False, "reason": "missing_endpoint"}
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", service_name)}))
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        return {"enabled": True, "endpoint": endpoint}
    except Exception as exc:  # noqa: BLE001
        return {"enabled": False, "reason": f"otel_init_error:{exc.__class__.__name__}"}
