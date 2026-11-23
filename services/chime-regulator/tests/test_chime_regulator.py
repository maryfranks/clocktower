"""Offline unit tests for chime-regulator using fakeredis and InMemorySpanExporter."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import fakeredis.aioredis
import httpx
import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from redis.exceptions import ConnectionError as RedisConnectionError

from chime_regulator.clients import MockEscapementGearClient, MockPendulumCacheClient
from chime_regulator.config import Settings
from chime_regulator.main import create_app
from chime_regulator.models import (
    CachedSessionState,
    InternalRegulateResponse,
    SessionResponse,
    TracesResponse,
    TraceWaterfall,
)
from chime_regulator.trace_store import RedisTraceStore


class FailingRedisClient:
    """Stub redis.asyncio client that raises ConnectionError on all operations."""

    def pipeline(self, transaction: bool = True) -> _FailingPipeline:
        return _FailingPipeline()

    async def lrange(self, key: str, start: int, end: int) -> list[bytes]:
        raise RedisConnectionError("Simulated Redis outage during lrange")


class _FailingPipeline:
    async def __aenter__(self) -> _FailingPipeline:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def lpush(self, key: str, value: str) -> None:
        return None

    def ltrim(self, key: str, start: int, end: int) -> None:
        return None

    def expire(self, key: str, seconds: int) -> None:
        return None

    async def execute(self) -> list[object]:
        raise RedisConnectionError("Simulated Redis outage during pipeline execute")


@pytest.fixture
def span_exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
async def fake_redis() -> AsyncGenerator[fakeredis.aioredis.FakeRedis, None]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=False)
    yield client
    await client.aclose()


@pytest.fixture
def cache_client() -> MockPendulumCacheClient:
    return MockPendulumCacheClient(
        initial_states={
            "sess-1": CachedSessionState(
                session_id="sess-1",
                stage_id=1,
                warm_targets=[],
                calibrated_targets=[],
                calibration_values={},
                stage_completed=False,
            )
        }
    )


@pytest.fixture
def async_client(
    fake_redis: fakeredis.aioredis.FakeRedis,
    cache_client: MockPendulumCacheClient,
    span_exporter: InMemorySpanExporter,
) -> httpx.AsyncClient:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    store = RedisTraceStore(client=fake_redis, max_traces=5, ttl_seconds=3600)
    app = create_app(
        settings=Settings(env="local"),
        cache_client=cache_client,
        escapement_client=MockEscapementGearClient(),
        trace_store=store,
        tracer_provider=provider,
    )
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def test_healthz_returns_200(async_client: httpx.AsyncClient) -> None:
    async with async_client as client:
        resp = await client.get("/healthz")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_internal_session_creates_and_resumes(async_client: httpx.AsyncClient) -> None:
    async with async_client as client:
        create_resp = await client.post("/internal/session", json={"session_id": None})
        assert create_resp.status_code == 200
        created = SessionResponse.model_validate(create_resp.json())
        assert created.session_id.startswith("sess-")
        assert created.state.stage_id == 1
        assert created.state.stage_completed is False
        assert created.gauges.mains_tension == 0.0

        resume_resp = await client.post(
            "/internal/session", json={"session_id": created.session_id}
        )
        assert resume_resp.status_code == 200
        resumed = SessionResponse.model_validate(resume_resp.json())
        assert resumed.session_id == created.session_id


async def test_stage1_regulate_evaluation_and_otel_spans(
    async_client: httpx.AsyncClient,
    span_exporter: InMemorySpanExporter,
) -> None:
    async with async_client as client:
        # Early ENGAGE before targets are warm -> ERROR span, stage_completed=False
        early_resp = await client.post(
            "/internal/regulate",
            json={
                "session_id": "sess-1",
                "stage_id": 1,
                "action": "ENGAGE",
                "target": "chime-regulator",
                "value": 50,
            },
        )
        assert early_resp.status_code == 200
        early = InternalRegulateResponse.model_validate(early_resp.json())
        assert early.state.stage_completed is False
        assert early.latest_trace.status == "ERROR"

        # Cold-start PROBE on escapement-gear -> cold_start=True, high duration
        cold_probe = await client.post(
            "/internal/regulate",
            json={
                "session_id": "sess-1",
                "stage_id": 1,
                "action": "PROBE",
                "target": "escapement-gear",
                "value": 50,
            },
        )
        assert cold_probe.status_code == 200
        cold = InternalRegulateResponse.model_validate(cold_probe.json())
        assert cold.latest_trace.status == "OK"
        assert cold.gauges.resonance_drag == 78.0
        assert any(
            span.attributes.get("container.cold_start") is True for span in cold.latest_trace.spans
        )

        # Warm PROBE on escapement-gear -> cold_start=False, lower drag
        warm_probe = await client.post(
            "/internal/regulate",
            json={
                "session_id": "sess-1",
                "stage_id": 1,
                "action": "PROBE",
                "target": "escapement-gear",
                "value": 50,
            },
        )
        assert warm_probe.status_code == 200
        warm = InternalRegulateResponse.model_validate(warm_probe.json())
        assert warm.gauges.resonance_drag == 18.0
        assert warm.latest_trace.total_duration_ms < cold.latest_trace.total_duration_ms

        # Probe remaining targets
        for target in ("chime-regulator", "pendulum-cache"):
            resp = await client.post(
                "/internal/regulate",
                json={
                    "session_id": "sess-1",
                    "stage_id": 1,
                    "action": "PROBE",
                    "target": target,
                    "value": 50,
                },
            )
            assert resp.status_code == 200

        # CALIBRATE updates slider_value
        cal_resp = await client.post(
            "/internal/regulate",
            json={
                "session_id": "sess-1",
                "stage_id": 1,
                "action": "CALIBRATE",
                "target": "escapement-gear",
                "value": 75,
            },
        )
        assert cal_resp.status_code == 200
        cal = InternalRegulateResponse.model_validate(cal_resp.json())
        assert cal.state.slider_value == 75

        # ENGAGE now succeeds and completes Stage 1
        engage_resp = await client.post(
            "/internal/regulate",
            json={
                "session_id": "sess-1",
                "stage_id": 1,
                "action": "ENGAGE",
                "target": "chime-regulator",
                "value": 75,
            },
        )
        assert engage_resp.status_code == 200
        engaged = InternalRegulateResponse.model_validate(engage_resp.json())
        assert engaged.state.stage_completed is True
        assert engaged.latest_trace.status == "OK"
        assert engaged.gauges.reserve_pressure == 90.0

        # RESET clears state and zeroes gauges
        reset_resp = await client.post(
            "/internal/regulate",
            json={
                "session_id": "sess-1",
                "stage_id": 1,
                "action": "RESET",
                "target": "chime-regulator",
                "value": 50,
            },
        )
        assert reset_resp.status_code == 200
        reset = InternalRegulateResponse.model_validate(reset_resp.json())
        assert reset.state.stage_completed is False
        assert reset.gauges.mains_tension == 0.0

    # Verify OTel spans were flushed and include gauge.* attributes
    finished_spans = span_exporter.get_finished_spans()
    assert len(finished_spans) >= 8
    regulate_spans = [s for s in finished_spans if s.name == "chime_regulator.regulate"]
    assert regulate_spans
    assert all(
        s.attributes is not None and "gauge.mains_tension" in s.attributes for s in regulate_spans
    )


async def test_redis_trace_store_caps_at_5_newest_first(
    async_client: httpx.AsyncClient,
) -> None:
    async with async_client as client:
        recorded_ids: list[str] = []
        actions_and_targets = [
            ("PROBE", "chime-regulator"),
            ("PROBE", "escapement-gear"),
            ("PROBE", "pendulum-cache"),
            ("CALIBRATE", "escapement-gear"),
            ("CALIBRATE", "chime-regulator"),
            ("ENGAGE", "chime-regulator"),
            ("RESET", "chime-regulator"),
        ]
        for action, target in actions_and_targets:
            resp = await client.post(
                "/internal/regulate",
                json={
                    "session_id": "sess-1",
                    "stage_id": 1,
                    "action": action,
                    "target": target,
                    "value": 50,
                },
            )
            assert resp.status_code == 200
            parsed = InternalRegulateResponse.model_validate(resp.json())
            recorded_ids.append(parsed.latest_trace.trace_id)

        traces_resp = await client.get("/internal/traces/sess-1")

    assert traces_resp.status_code == 200
    traces_parsed = TracesResponse.model_validate(traces_resp.json())
    assert traces_parsed.session_id == "sess-1"
    assert len(traces_parsed.traces) == 5

    # Newest-first ordering: last 5 recorded traces in reverse order
    expected_ids = list(reversed(recorded_ids[-5:]))
    assert [t.trace_id for t in traces_parsed.traces] == expected_ids
    assert traces_parsed.traces[0].action == "RESET"
    assert traces_parsed.traces[1].action == "ENGAGE"


async def test_graceful_degradation_when_redis_indexing_fails(
    cache_client: MockPendulumCacheClient,
    span_exporter: InMemorySpanExporter,
) -> None:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    failing_store = RedisTraceStore(client=FailingRedisClient())  # type: ignore[arg-type]
    app = create_app(
        settings=Settings(env="local"),
        cache_client=cache_client,
        escapement_client=MockEscapementGearClient(),
        trace_store=failing_store,
        tracer_provider=provider,
    )
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg_resp = await client.post(
            "/internal/regulate",
            json={
                "session_id": "sess-1",
                "stage_id": 1,
                "action": "PROBE",
                "target": "chime-regulator",
                "value": 50,
            },
        )
        assert reg_resp.status_code == 200
        parsed_reg = InternalRegulateResponse.model_validate(reg_resp.json())
        assert isinstance(parsed_reg.latest_trace, TraceWaterfall)

        traces_resp = await client.get("/internal/traces/sess-1")
        assert traces_resp.status_code == 200
        parsed_traces = TracesResponse.model_validate(traces_resp.json())
        assert parsed_traces.traces == []


async def test_unknown_session_returns_404(async_client: httpx.AsyncClient) -> None:
    async with async_client as client:
        reg_resp = await client.post(
            "/internal/regulate",
            json={
                "session_id": "missing-session",
                "stage_id": 1,
                "action": "PROBE",
                "target": "chime-regulator",
                "value": 50,
            },
        )
        traces_resp = await client.get("/internal/traces/missing-session")

    assert reg_resp.status_code == 404
    assert traces_resp.status_code == 404
