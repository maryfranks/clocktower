"""OpenTelemetry setup and synchronous span flushing for chime-regulator."""

from __future__ import annotations

import logging

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span as OtelSpan

from chime_regulator.config import Settings
from chime_regulator.models import GaugeReadings, TraceWaterfall

logger = logging.getLogger(__name__)

GAUGE_PREFIX = "gauge."


def record_gauge_attributes(
    otel_span: OtelSpan,
    gauges: GaugeReadings,
    waterfall: TraceWaterfall | None = None,
) -> None:
    """Attach gauge.* telemetry attributes to an OpenTelemetry span prior to export."""
    otel_span.set_attribute("gauge.mains_tension", gauges.mains_tension)
    otel_span.set_attribute("gauge.resonance_drag", gauges.resonance_drag)
    otel_span.set_attribute("gauge.reserve_pressure", gauges.reserve_pressure)
    if waterfall is None:
        return
    for span in waterfall.spans:
        for key, value in span.attributes.items():
            if key.startswith(GAUGE_PREFIX):
                otel_span.set_attribute(key, value)


def create_tracer_provider(settings: Settings) -> TracerProvider:
    """Initialize an OpenTelemetry TracerProvider with optional OTLP/HTTP export."""
    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    endpoint = settings.otel_exporter_otlp_endpoint
    if endpoint or settings.honeycomb_api_key:
        headers: dict[str, str] = {}
        if settings.honeycomb_api_key:
            headers["x-honeycomb-team"] = settings.honeycomb_api_key
            endpoint = endpoint or "https://api.honeycomb.io/v1/traces"
        exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers or None)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    return provider


def flush_tracer_provider(provider: TracerProvider) -> None:
    """Synchronously flush pending spans so Cloud Run does not drop telemetry."""
    try:
        provider.force_flush()
    except Exception:
        logger.warning("Failed to flush OpenTelemetry TracerProvider", exc_info=True)
