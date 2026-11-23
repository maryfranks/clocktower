"""FastAPI application and internal endpoints for chime-regulator."""

from __future__ import annotations

from uuid import uuid4

import redis.asyncio as redis_async
from fastapi import FastAPI, HTTPException
from opentelemetry.sdk.trace import TracerProvider

from chime_regulator.clients import (
    EscapementGearClient,
    MockEscapementGearClient,
    MockPendulumCacheClient,
    PendulumCacheClient,
)
from chime_regulator.config import Settings, load_settings
from chime_regulator.models import (
    CachedSessionState,
    InternalRegulateRequest,
    InternalRegulateResponse,
    InternalTickRequest,
    SessionRequest,
    SessionResponse,
    TracesResponse,
)
from chime_regulator.stage1 import (
    assemble_waterfall,
    build_stage_state,
    evaluate_stage1_action,
    initial_gauges_for_state,
)
from chime_regulator.telemetry import (
    create_tracer_provider,
    flush_tracer_provider,
    record_gauge_attributes,
)
from chime_regulator.trace_store import RedisTraceStore, TraceStore


def create_app(
    settings: Settings | None = None,
    cache_client: PendulumCacheClient | None = None,
    escapement_client: EscapementGearClient | None = None,
    trace_store: TraceStore | None = None,
    tracer_provider: TracerProvider | None = None,
) -> FastAPI:
    """Create and configure the chime-regulator FastAPI application."""
    cfg = settings or load_settings()
    cache = cache_client or MockPendulumCacheClient()
    escapement = escapement_client or MockEscapementGearClient()
    if trace_store is None:
        redis_client: redis_async.Redis = redis_async.from_url(  # type: ignore[no-untyped-call]
            cfg.redis_url, decode_responses=False
        )
        store: TraceStore = RedisTraceStore(
            client=redis_client,
            max_traces=cfg.trace_history_limit,
            ttl_seconds=cfg.trace_ttl_seconds,
        )
    else:
        store = trace_store

    provider = tracer_provider or create_tracer_provider(cfg)
    tracer = provider.get_tracer("chime-regulator")

    app = FastAPI(
        title="The Clock Tower — chime-regulator",
        version="0.1.0",
    )
    app.state.settings = cfg
    app.state.cache_client = cache
    app.state.escapement_client = escapement
    app.state.trace_store = store
    app.state.tracer_provider = provider

    @app.get("/health")
    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/internal/session", response_model=SessionResponse)
    async def create_or_resume_session(body: SessionRequest | None = None) -> SessionResponse:
        req = body or SessionRequest()
        try:
            with tracer.start_as_current_span("chime_regulator.session") as otel_span:
                existing = (
                    await cache.get_state(req.session_id) if req.session_id is not None else None
                )
                if existing is None:
                    session_id = req.session_id or f"sess-{uuid4().hex[:12]}"
                    cached = CachedSessionState(
                        session_id=session_id,
                        stage_id=1,
                        warm_targets=[],
                        calibrated_targets=[],
                        calibration_values={},
                        stage_completed=False,
                    )
                    await cache.set_state(session_id, cached)
                    logs = ["Stage 1 initialized. Downstream services are dormant."]
                else:
                    cached = existing
                    logs = [f"Stage {cached.stage_id} session resumed."]
                    if req.advance_stage and cached.stage_completed and cached.stage_id < 5:
                        cached = CachedSessionState(
                            session_id=cached.session_id,
                            stage_id=cached.stage_id + 1,
                            warm_targets=[],
                            calibrated_targets=[],
                            calibration_values={},
                            stage_completed=False,
                        )
                        await cache.set_state(cached.session_id, cached)
                        logs = [f"Advanced to Stage {cached.stage_id}."]

                gauges = initial_gauges_for_state(cached)
                recent_traces = await store.get_traces(cached.session_id)
                otel_span.set_attribute("session.id", cached.session_id)
                otel_span.set_attribute("stage.id", cached.stage_id)
                record_gauge_attributes(otel_span, gauges)

                return SessionResponse(
                    session_id=cached.session_id,
                    state=build_stage_state(
                        cached=cached,
                        selected_target="chime-regulator",
                        slider_value=50,
                        chamber_logs=logs,
                    ),
                    gauges=gauges,
                    recent_traces=recent_traces,
                )
        finally:
            flush_tracer_provider(provider)

    @app.post("/internal/regulate", response_model=InternalRegulateResponse)
    async def regulate(body: InternalRegulateRequest) -> InternalRegulateResponse:
        try:
            with tracer.start_as_current_span("chime_regulator.regulate") as otel_span:
                otel_span.set_attribute("session.id", body.session_id)
                otel_span.set_attribute("stage.id", body.stage_id)
                otel_span.set_attribute("action.type", body.action)
                otel_span.set_attribute("action.target", body.target)
                otel_span.set_attribute("action.value", body.value)

                cached = await cache.get_state(body.session_id)
                if cached is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Session '{body.session_id}' not found",
                    )

                is_warm = body.target in cached.warm_targets
                tick_resp = await escapement.tick(
                    InternalTickRequest(
                        session_id=body.session_id,
                        stage_id=body.stage_id,
                        action=body.action,
                        target=body.target,
                        value=body.value,
                        is_warm=is_warm,
                    )
                )

                updated_cached, gauges, status, log_line = evaluate_stage1_action(
                    cached=cached,
                    action=body.action,
                    target=body.target,
                    value=body.value,
                    tick_resp=tick_resp,
                )
                await cache.set_state(body.session_id, updated_cached)

                span_ctx = otel_span.get_span_context()
                trace_id = (
                    f"{span_ctx.trace_id:032x}" if span_ctx.trace_id != 0 else uuid4().hex
                )
                waterfall = assemble_waterfall(
                    trace_id=trace_id,
                    action=body.action,
                    target=body.target,
                    status=status,
                    gauges=gauges,
                    tick_resp=tick_resp,
                )
                record_gauge_attributes(otel_span, gauges, waterfall)

                # Graceful degradation: trace indexing failure must not fail regulation.
                await store.append_trace(body.session_id, waterfall)

                state = build_stage_state(
                    cached=updated_cached,
                    selected_target=body.target,
                    slider_value=body.value,
                    chamber_logs=[log_line],
                )
                return InternalRegulateResponse(
                    state=state,
                    gauges=gauges,
                    latest_trace=waterfall,
                )
        finally:
            flush_tracer_provider(provider)

    @app.get("/internal/traces/{session_id}", response_model=TracesResponse)
    async def get_traces(session_id: str) -> TracesResponse:
        try:
            with tracer.start_as_current_span("chime_regulator.traces") as otel_span:
                otel_span.set_attribute("session.id", session_id)
                cached = await cache.get_state(session_id)
                traces = await store.get_traces(session_id)
                if cached is None and not traces:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Session '{session_id}' not found",
                    )
                return TracesResponse(session_id=session_id, traces=traces[:5])
        finally:
            flush_tracer_provider(provider)

    return app


app = create_app()
