"""Integration tests for switchboard-room HTTP routing to chime-regulator."""

from __future__ import annotations

import json

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from switchboard_room.auth import OidcAuthHeaderProvider
from switchboard_room.client import HttpChimeRegulatorClient
from switchboard_room.config import Environment, Settings, load_settings
from switchboard_room.main import create_app
from switchboard_room.models import (
    ActionResponse,
    FieldManualContent,
    GaugeReadings,
    RealWorldParallel,
    SessionResponse,
    Span,
    StageState,
    TracesResponse,
    TraceWaterfall,
)


def _sample_state(stage_completed: bool = False) -> dict[str, object]:
    return StageState(
        stage_id=1,
        stage_completed=stage_completed,
        targets=["chime-regulator", "escapement-gear", "pendulum-cache"],
        selected_target="chime-regulator",
        slider_value=50,
        chamber_logs=["Stage 1 ready."],
        manual=FieldManualContent(
            stage_title="Stage 1: Wake the Tower",
            how_to_play=["Probe all targets."],
            stage_hints=["Watch for cold starts."],
            real_world_parallel=RealWorldParallel(
                title="Scale-to-Zero Cold Starts",
                summary="Containers wake on first request.",
                completion_takeaway="All subsystems warm.",
            ),
        ),
    ).model_dump(mode="json")


def _sample_waterfall(action: str = "PROBE") -> dict[str, object]:
    return TraceWaterfall(
        trace_id="trace-1234",
        timestamp="2026-11-23T12:00:00Z",  # type: ignore[arg-type]
        action=action,  # type: ignore[arg-type]
        target="chime-regulator",
        total_duration_ms=800,
        status="OK",
        spans=[
            Span(
                span_id="span-root",
                parent_span_id=None,
                service_name="chime-regulator",
                operation_name=f"POST /internal/regulate ({action})",
                start_offset_ms=0,
                duration_ms=800,
                status="OK",
                attributes={
                    "action.type": action,
                    "gauge.mains_tension": 45.0,
                    "gauge.resonance_drag.spike_ms": 780,
                },
            ),
            Span(
                span_id="span-child",
                parent_span_id="span-root",
                service_name="escapement-gear",
                operation_name="probe.escapement-gear",
                start_offset_ms=12,
                duration_ms=780,
                status="OK",
                attributes={
                    "container.cold_start": True,
                    "gauge.reserve_pressure": 30.0,
                },
            ),
        ],
    ).model_dump(mode="json")


def test_default_settings_use_http_chime_regulator_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CHIME_REGULATOR_MODE", raising=False)
    settings = load_settings()
    assert settings.chime_regulator_mode == "http"


@pytest.mark.parametrize("env_name", ["local", "prod"])
async def test_http_routing_and_oidc_in_local_vs_prod_and_gauge_stripping(
    env_name: Environment,
) -> None:
    captured_requests: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append((request.url.path, request.headers.get("authorization")))
        if request.url.path == "/internal/session":
            return httpx.Response(
                200,
                json={
                    "session_id": "sess-http-1",
                    "state": _sample_state(),
                    "gauges": GaugeReadings(
                        mains_tension=0.0,
                        resonance_drag=0.0,
                        reserve_pressure=0.0,
                    ).model_dump(mode="json"),
                    "recent_traces": [],
                },
            )
        if request.url.path == "/internal/regulate":
            payload = json.loads(request.content.decode())
            assert payload["session_id"] == "sess-http-1"
            return httpx.Response(
                200,
                json={
                    "state": _sample_state(),
                    "gauges": GaugeReadings(
                        mains_tension=45.0,
                        resonance_drag=78.0,
                        reserve_pressure=30.0,
                    ).model_dump(mode="json"),
                    "latest_trace": _sample_waterfall(payload["action"]),
                },
            )
        if request.url.path == "/internal/traces/sess-http-1":
            return httpx.Response(
                200,
                json={
                    "session_id": "sess-http-1",
                    "traces": [_sample_waterfall("PROBE")],
                },
            )
        return httpx.Response(404)

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    async_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    auth = OidcAuthHeaderProvider(
        env=env_name,
        token_fetcher=lambda aud: f"oidc-token-for-{aud}",
    )
    downstream = HttpChimeRegulatorClient(
        base_url="https://chime-regulator.internal",
        auth_provider=auth,
        http_client=async_http,
    )
    app = create_app(
        settings=Settings(env=env_name, chime_regulator_mode="http"),
        downstream_client=downstream,
        tracer_provider=provider,
    )

    async with (
        async_http,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        sess_resp = await client.post("/api/session", json={"session_id": None})
        assert sess_resp.status_code == 200
        SessionResponse.model_validate(sess_resp.json())

        action_resp = await client.post(
            "/api/action",
            json={
                "session_id": "sess-http-1",
                "stage_id": 1,
                "action": "PROBE",
                "target": "chime-regulator",
                "value": 50,
            },
        )
        assert action_resp.status_code == 200
        parsed_action = ActionResponse.model_validate(action_resp.json())
        for span in parsed_action.latest_trace.spans:
            assert not any(k.startswith("gauge.") for k in span.attributes)

        traces_resp = await client.get("/api/traces/sess-http-1")
        assert traces_resp.status_code == 200
        parsed_traces = TracesResponse.model_validate(traces_resp.json())
        assert len(parsed_traces.traces) == 1
        for span in parsed_traces.traces[0].spans:
            assert not any(k.startswith("gauge.") for k in span.attributes)

    expected_auth = (
        "Bearer oidc-token-for-https://chime-regulator.internal" if env_name == "prod" else None
    )
    assert captured_requests == [
        ("/internal/session", expected_auth),
        ("/internal/regulate", expected_auth),
        ("/internal/traces/sess-http-1", expected_auth),
    ]

    # OTel exported spans retain gauge.* attributes
    action_spans = [s for s in exporter.get_finished_spans() if s.name == "switchboard.action"]
    assert len(action_spans) == 1
    attrs = action_spans[0].attributes or {}
    assert attrs.get("gauge.mains_tension") == 45.0
    assert attrs.get("gauge.resonance_drag.spike_ms") == 780


async def test_graceful_degradation_when_chime_regulator_traces_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/internal/traces/sess-1":
            return httpx.Response(503, json={"detail": "Redis unavailable"})
        return httpx.Response(404)

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    async_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    downstream = HttpChimeRegulatorClient(
        base_url="https://chime-regulator.internal",
        auth_provider=OidcAuthHeaderProvider(env="local"),
        http_client=async_http,
    )
    app = create_app(
        settings=Settings(env="local", chime_regulator_mode="http"),
        downstream_client=downstream,
        tracer_provider=provider,
    )

    async with (
        async_http,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client,
    ):
        resp = await client.get("/api/traces/sess-1")

    assert resp.status_code == 200
    parsed = TracesResponse.model_validate(resp.json())
    assert parsed.session_id == "sess-1"
    assert parsed.traces == []
