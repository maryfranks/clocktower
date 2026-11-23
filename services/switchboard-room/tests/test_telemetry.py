"""Unit and integration tests for OTel span flushing and gauge.* attribute stripping."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from switchboard_room.config import Settings
from switchboard_room.main import create_app


async def test_spans_are_emitted_and_flushed_synchronously_per_request() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    # BatchSpanProcessor buffers spans; only synchronous force_flush() makes them
    # immediately available before the HTTP handler returns.
    provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=60_000))

    original_flush = provider.force_flush
    flush_spy = MagicMock(side_effect=original_flush)
    provider.force_flush = flush_spy  # type: ignore[method-assign]

    app = create_app(
        settings=Settings(env="local", chime_regulator_mode="mock"),
        tracer_provider=provider,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_resp = await client.post("/api/session", json={})
        assert session_resp.status_code == 200
        assert flush_spy.call_count == 1
        assert [s.name for s in exporter.get_finished_spans()] == ["switchboard.session"]

        session_id = session_resp.json()["session_id"]
        action_resp = await client.post(
            "/api/action",
            json={
                "session_id": session_id,
                "stage_id": 1,
                "action": "PROBE",
                "target": "chime-regulator",
                "value": 50,
            },
        )
        assert action_resp.status_code == 200
        assert flush_spy.call_count == 2
        assert [s.name for s in exporter.get_finished_spans()] == [
            "switchboard.session",
            "switchboard.action",
        ]

        traces_resp = await client.get(f"/api/traces/{session_id}")
        assert traces_resp.status_code == 200
        assert flush_spy.call_count == 3
        assert [s.name for s in exporter.get_finished_spans()] == [
            "switchboard.session",
            "switchboard.action",
            "switchboard.traces",
        ]


async def test_gauge_attributes_stripped_from_responses_but_preserved_on_otel_spans() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(exporter, schedule_delay_millis=60_000))

    app = create_app(
        settings=Settings(env="local", chime_regulator_mode="mock"),
        tracer_provider=provider,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        session_resp = await client.post("/api/session", json={})
        session_id = session_resp.json()["session_id"]

        action_resp = await client.post(
            "/api/action",
            json={
                "session_id": session_id,
                "stage_id": 1,
                "action": "PROBE",
                "target": "escapement-gear",
                "value": 50,
            },
        )
        assert action_resp.status_code == 200
        action_payload = action_resp.json()

        # Verify no gauge.* keys exist anywhere in POST /api/action span attributes
        for span in action_payload["latest_trace"]["spans"]:
            gauge_keys = [k for k in span["attributes"] if k.startswith("gauge.")]
            assert gauge_keys == []
        # Player-facing attributes remain intact
        child_span = action_payload["latest_trace"]["spans"][1]
        assert child_span["attributes"]["container.cold_start"] is True

        # Verify GET /api/traces/{session_id} also strips all gauge.* keys
        traces_resp = await client.get(f"/api/traces/{session_id}")
        assert traces_resp.status_code == 200
        for trace in traces_resp.json()["traces"]:
            for span in trace["spans"]:
                gauge_keys = [k for k in span["attributes"] if k.startswith("gauge.")]
                assert gauge_keys == []

        # Verify POST /api/session recent_traces also strips all gauge.* keys
        resume_resp = await client.post("/api/session", json={"session_id": session_id})
        assert resume_resp.status_code == 200
        for trace in resume_resp.json()["recent_traces"]:
            for span in trace["spans"]:
                gauge_keys = [k for k in span["attributes"] if k.startswith("gauge.")]
                assert gauge_keys == []

    # Verify exported OTel span for switchboard.action preserved gauge.* attributes
    action_otel_spans = [s for s in exporter.get_finished_spans() if s.name == "switchboard.action"]
    assert len(action_otel_spans) == 1
    attrs = dict(action_otel_spans[0].attributes or {})
    assert "gauge.mains_tension" in attrs
    assert "gauge.resonance_drag" in attrs
    assert "gauge.reserve_pressure" in attrs
    assert "gauge.mains_tension.overload_pct" in attrs
