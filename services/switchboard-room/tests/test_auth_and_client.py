"""Unit tests for ENV=local/prod OIDC auth and HttpChimeRegulatorClient."""

from __future__ import annotations

import json

import httpx
import pytest

from switchboard_room.auth import OidcAuthHeaderProvider
from switchboard_room.client import HttpChimeRegulatorClient, SessionNotFoundError
from switchboard_room.models import (
    FieldManualContent,
    GaugeReadings,
    InternalRegulateRequest,
    RealWorldParallel,
    Span,
    StageState,
    TraceWaterfall,
)


def _sample_state() -> dict[str, object]:
    return StageState(
        stage_id=1,
        stage_completed=False,
        targets=["chime-regulator", "escapement-gear", "pendulum-cache"],
        selected_target="chime-regulator",
        slider_value=50,
        chamber_logs=["ok"],
        manual=FieldManualContent(
            stage_title="Stage 1",
            how_to_play=["Probe"],
            stage_hints=["Hint"],
            real_world_parallel=RealWorldParallel(
                title="Cold Start",
                summary="Summary",
                completion_takeaway="Takeaway",
            ),
        ),
    ).model_dump(mode="json")


def _sample_waterfall() -> dict[str, object]:
    return TraceWaterfall(
        trace_id="abc123",
        timestamp="2026-11-21T18:00:00Z",  # type: ignore[arg-type]
        action="PROBE",
        target="chime-regulator",
        total_duration_ms=50,
        status="OK",
        spans=[
            Span(
                span_id="span1",
                parent_span_id=None,
                service_name="chime-regulator",
                operation_name="probe",
                start_offset_ms=0,
                duration_ms=50,
                status="OK",
                attributes={"gauge.mains_tension": 45.0, "cold_start": True},
            )
        ],
    ).model_dump(mode="json")


def test_oidc_auth_skipped_in_local_env() -> None:
    called = False

    def fake_fetcher(audience: str) -> str:
        nonlocal called
        called = True
        return "should-not-be-used"

    provider = OidcAuthHeaderProvider(env="local", token_fetcher=fake_fetcher)
    assert provider.get_headers("https://chime-regulator.run.app") == {}
    assert called is False


def test_oidc_auth_attaches_bearer_token_in_prod_env() -> None:
    received_audience: list[str] = []

    def fake_fetcher(audience: str) -> str:
        received_audience.append(audience)
        return "signed-oidc-token"

    provider = OidcAuthHeaderProvider(env="prod", token_fetcher=fake_fetcher)
    headers = provider.get_headers("https://chime-regulator.run.app")

    assert headers == {"Authorization": "Bearer signed-oidc-token"}
    assert received_audience == ["https://chime-regulator.run.app"]


async def test_http_client_routes_with_oidc_headers_and_handles_404() -> None:
    captured_auth: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_auth.append(request.headers.get("authorization"))
        if request.url.path == "/internal/regulate":
            body = json.loads(request.content.decode())
            if body["session_id"] == "missing":
                return httpx.Response(404, json={"detail": "not found"})
            return httpx.Response(
                200,
                json={
                    "state": _sample_state(),
                    "gauges": GaugeReadings(
                        mains_tension=45.0,
                        resonance_drag=20.0,
                        reserve_pressure=30.0,
                    ).model_dump(mode="json"),
                    "latest_trace": _sample_waterfall(),
                },
            )
        if request.url.path == "/internal/traces/sess-1":
            return httpx.Response(
                200,
                json={"session_id": "sess-1", "traces": [_sample_waterfall()]},
            )
        return httpx.Response(404)

    async_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    auth = OidcAuthHeaderProvider(env="prod", token_fetcher=lambda _: "prod-jwt")
    client = HttpChimeRegulatorClient(
        base_url="https://chime-regulator.internal",
        auth_provider=auth,
        http_client=async_http,
    )

    async with async_http:
        reg_resp = await client.regulate(
            InternalRegulateRequest(
                session_id="sess-1",
                stage_id=1,
                action="PROBE",
                target="chime-regulator",
                value=50,
            )
        )
        assert reg_resp.gauges.mains_tension == 45.0

        traces_resp = await client.get_traces("sess-1")
        assert len(traces_resp.traces) == 1

        with pytest.raises(SessionNotFoundError):
            await client.regulate(
                InternalRegulateRequest(
                    session_id="missing",
                    stage_id=1,
                    action="PROBE",
                    target="chime-regulator",
                    value=50,
                )
            )

    assert captured_auth == ["Bearer prod-jwt", "Bearer prod-jwt", "Bearer prod-jwt"]
