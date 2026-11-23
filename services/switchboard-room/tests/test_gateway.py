"""Integration tests for switchboard-room public endpoints using httpx.AsyncClient."""

from __future__ import annotations

import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from switchboard_room.config import Settings
from switchboard_room.main import create_app
from switchboard_room.models import (
    ActionResponse,
    SessionResponse,
    TracesResponse,
)


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def async_client(span_exporter: InMemorySpanExporter) -> httpx.AsyncClient:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    app = create_app(
        settings=Settings(env="local", chime_regulator_mode="mock"),
        tracer_provider=provider,
    )
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def test_healthz_returns_200(async_client: httpx.AsyncClient) -> None:
    async with async_client as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_create_session_with_empty_body(async_client: httpx.AsyncClient) -> None:
    async with async_client as client:
        response = await client.post("/api/session")

    assert response.status_code == 200
    parsed = SessionResponse.model_validate(response.json())
    assert parsed.session_id.startswith("sess-")
    assert parsed.state.stage_id == 1
    assert parsed.state.stage_completed is False
    assert parsed.state.targets == ["chime-regulator", "escapement-gear", "pendulum-cache"]
    assert parsed.state.slider_value % 5 == 0
    assert parsed.gauges.mains_tension == 0.0
    assert parsed.recent_traces == []


async def test_stage1_actions_probe_calibrate_engage_reset(
    async_client: httpx.AsyncClient,
) -> None:
    async with async_client as client:
        session_resp = await client.post("/api/session", json={"session_id": None})
        session_id = session_resp.json()["session_id"]

        # ENGAGE before all targets are warm should return ERROR span and incomplete stage
        early_engage = await client.post(
            "/api/action",
            json={
                "session_id": session_id,
                "stage_id": 1,
                "action": "ENGAGE",
                "target": "chime-regulator",
                "value": 50,
            },
        )
        assert early_engage.status_code == 200
        early_parsed = ActionResponse.model_validate(early_engage.json())
        assert early_parsed.state.stage_completed is False
        assert early_parsed.latest_trace.status == "ERROR"

        # PROBE all three Stage 1 targets
        for target in ("chime-regulator", "escapement-gear", "pendulum-cache"):
            probe_resp = await client.post(
                "/api/action",
                json={
                    "session_id": session_id,
                    "stage_id": 1,
                    "action": "PROBE",
                    "target": target,
                    "value": 50,
                },
            )
            assert probe_resp.status_code == 200
            probe_parsed = ActionResponse.model_validate(probe_resp.json())
            assert probe_parsed.latest_trace.action == "PROBE"
            assert probe_parsed.latest_trace.target == target
            assert probe_parsed.latest_trace.status == "OK"

        # CALIBRATE action conforms to ActionResponse
        calibrate_resp = await client.post(
            "/api/action",
            json={
                "session_id": session_id,
                "stage_id": 1,
                "action": "CALIBRATE",
                "target": "escapement-gear",
                "value": 75,
            },
        )
        assert calibrate_resp.status_code == 200
        cal_parsed = ActionResponse.model_validate(calibrate_resp.json())
        assert cal_parsed.latest_trace.action == "CALIBRATE"
        assert cal_parsed.state.slider_value == 75

        # ENGAGE after all targets are warm completes Stage 1
        engage_resp = await client.post(
            "/api/action",
            json={
                "session_id": session_id,
                "stage_id": 1,
                "action": "ENGAGE",
                "target": "chime-regulator",
                "value": 75,
            },
        )
        assert engage_resp.status_code == 200
        engage_parsed = ActionResponse.model_validate(engage_resp.json())
        assert engage_parsed.state.stage_completed is True
        assert engage_parsed.latest_trace.status == "OK"

        # RESET returns stage_completed to False and zeroes gauges
        reset_resp = await client.post(
            "/api/action",
            json={
                "session_id": session_id,
                "stage_id": 1,
                "action": "RESET",
                "target": "chime-regulator",
                "value": 50,
            },
        )
        assert reset_resp.status_code == 200
        reset_parsed = ActionResponse.model_validate(reset_resp.json())
        assert reset_parsed.state.stage_completed is False
        assert reset_parsed.gauges.mains_tension == 0.0


async def test_get_traces_returns_up_to_5_newest_first(
    async_client: httpx.AsyncClient,
) -> None:
    async with async_client as client:
        session_resp = await client.post("/api/session", json={})
        session_id = session_resp.json()["session_id"]

        for idx in range(6):
            target = "chime-regulator" if idx % 2 == 0 else "escapement-gear"
            action = "PROBE" if idx < 5 else "CALIBRATE"
            resp = await client.post(
                "/api/action",
                json={
                    "session_id": session_id,
                    "stage_id": 1,
                    "action": action,
                    "target": target,
                    "value": 50,
                },
            )
            assert resp.status_code == 200

        traces_resp = await client.get(f"/api/traces/{session_id}")

    assert traces_resp.status_code == 200
    parsed = TracesResponse.model_validate(traces_resp.json())
    assert parsed.session_id == session_id
    assert len(parsed.traces) == 5
    assert parsed.traces[0].action == "CALIBRATE"


async def test_unknown_session_returns_404(async_client: httpx.AsyncClient) -> None:
    async with async_client as client:
        action_resp = await client.post(
            "/api/action",
            json={
                "session_id": "nonexistent-session",
                "stage_id": 1,
                "action": "PROBE",
                "target": "chime-regulator",
                "value": 50,
            },
        )
        traces_resp = await client.get("/api/traces/nonexistent-session")

    assert action_resp.status_code == 404
    assert traces_resp.status_code == 404


async def test_action_request_rejects_invalid_slider_step(
    async_client: httpx.AsyncClient,
) -> None:
    async with async_client as client:
        resp = await client.post(
            "/api/action",
            json={
                "session_id": "any",
                "stage_id": 1,
                "action": "PROBE",
                "target": "chime-regulator",
                "value": 42,
            },
        )

    assert resp.status_code == 422
