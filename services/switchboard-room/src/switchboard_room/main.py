"""FastAPI application and public gateway endpoints for switchboard-room."""

from __future__ import annotations

from typing import Annotated

from fastapi import Body, FastAPI, HTTPException
from opentelemetry.sdk.trace import TracerProvider

from switchboard_room.auth import OidcAuthHeaderProvider
from switchboard_room.client import (
    ChimeRegulatorClient,
    HttpChimeRegulatorClient,
    MockChimeRegulatorClient,
    SessionNotFoundError,
)
from switchboard_room.config import Settings, load_settings
from switchboard_room.models import (
    ActionRequest,
    ActionResponse,
    InternalRegulateRequest,
    SessionRequest,
    SessionResponse,
    TracesResponse,
)
from switchboard_room.telemetry import (
    create_tracer_provider,
    flush_tracer_provider,
    record_gauge_attributes,
    strip_gauge_attributes,
)


def _build_downstream_client(settings: Settings) -> ChimeRegulatorClient:
    if settings.chime_regulator_mode == "http":
        auth_provider = OidcAuthHeaderProvider(env=settings.env)
        return HttpChimeRegulatorClient(
            base_url=settings.chime_regulator_url,
            auth_provider=auth_provider,
            timeout_seconds=settings.downstream_timeout_seconds,
        )
    return MockChimeRegulatorClient()


def create_app(
    settings: Settings | None = None,
    downstream_client: ChimeRegulatorClient | None = None,
    tracer_provider: TracerProvider | None = None,
) -> FastAPI:
    """Create and configure the switchboard-room FastAPI application."""
    cfg = settings or load_settings()
    client = downstream_client or _build_downstream_client(cfg)
    provider = tracer_provider or create_tracer_provider(cfg)
    tracer = provider.get_tracer("switchboard-room")

    app = FastAPI(
        title="The Clock Tower — switchboard-room",
        version="0.1.0",
    )
    app.state.settings = cfg
    app.state.downstream_client = client
    app.state.tracer_provider = provider

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/session", response_model=SessionResponse)
    async def create_or_resume_session(
        body: Annotated[SessionRequest | None, Body()] = None,
    ) -> SessionResponse:
        req = body or SessionRequest()
        try:
            with tracer.start_as_current_span("switchboard.session") as otel_span:
                resp = await client.create_or_resume_session(req)
                otel_span.set_attribute("session.id", resp.session_id)
                otel_span.set_attribute("stage.id", resp.state.stage_id)
                record_gauge_attributes(otel_span, resp.gauges)
                stripped_traces = [strip_gauge_attributes(trace) for trace in resp.recent_traces]
                return resp.model_copy(update={"recent_traces": stripped_traces})
        finally:
            flush_tracer_provider(provider)

    @app.post("/api/action", response_model=ActionResponse)
    async def execute_action(body: ActionRequest) -> ActionResponse:
        internal_req = InternalRegulateRequest(
            session_id=body.session_id,
            stage_id=body.stage_id,
            action=body.action,
            target=body.target,
            value=body.value,
        )
        try:
            with tracer.start_as_current_span("switchboard.action") as otel_span:
                otel_span.set_attribute("session.id", body.session_id)
                otel_span.set_attribute("stage.id", body.stage_id)
                otel_span.set_attribute("action.type", body.action)
                otel_span.set_attribute("action.target", body.target)
                otel_span.set_attribute("action.value", body.value)
                try:
                    resp = await client.regulate(internal_req)
                except SessionNotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc

                record_gauge_attributes(otel_span, resp.gauges, resp.latest_trace)
                stripped_trace = strip_gauge_attributes(resp.latest_trace)
                return ActionResponse(
                    session_id=body.session_id,
                    state=resp.state,
                    gauges=resp.gauges,
                    latest_trace=stripped_trace,
                )
        finally:
            flush_tracer_provider(provider)

    @app.get("/api/traces/{session_id}", response_model=TracesResponse)
    async def get_traces(session_id: str) -> TracesResponse:
        try:
            with tracer.start_as_current_span("switchboard.traces") as otel_span:
                otel_span.set_attribute("session.id", session_id)
                try:
                    resp = await client.get_traces(session_id)
                except SessionNotFoundError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc

                stripped_traces = [strip_gauge_attributes(trace) for trace in resp.traces[:5]]
                return TracesResponse(session_id=resp.session_id, traces=stripped_traces)
        finally:
            flush_tracer_provider(provider)

    return app


app = create_app()
