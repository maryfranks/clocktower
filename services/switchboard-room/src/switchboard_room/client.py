"""Downstream client interface and Stage 1 mock for chime-regulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

import httpx
from opentelemetry import propagate

from switchboard_room.auth import AuthHeaderProvider
from switchboard_room.models import (
    ControlAction,
    FieldManualContent,
    GaugeReadings,
    InternalRegulateRequest,
    InternalRegulateResponse,
    RealWorldParallel,
    SessionRequest,
    SessionResponse,
    Span,
    SpanStatus,
    StageState,
    SubsystemTarget,
    TracesResponse,
    TraceWaterfall,
)

STAGE_1_TARGETS: list[SubsystemTarget] = [
    "chime-regulator",
    "escapement-gear",
    "pendulum-cache",
]

STAGE_1_MANUAL = FieldManualContent(
    stage_title="Stage 1: Wake the Tower",
    how_to_play=[
        "Select each dormant subsystem target and press PROBE to wake its container.",
        "Inspect the Trace Waterfall in Trace View to spot cold-start boot latency.",
        "Once all three subsystems are warm, press ENGAGE to synchronize the tower.",
    ],
    stage_hints=[
        "First PROBE to a dormant service incurs cold-start latency (container.cold_start = true).",
        "A second PROBE to the same target confirms warm baseline latency.",
    ],
    real_world_parallel=RealWorldParallel(
        title="Scale-to-Zero Cold Starts",
        summary=(
            "Serverless containers scale to zero when idle. The first request pays a boot "
            "penalty visible in distributed traces before settling into warm latency."
        ),
        completion_takeaway=(
            "You identified cold-start spans in the waterfall and verified warm readiness "
            "across all downstream services."
        ),
    ),
)


class SessionNotFoundError(Exception):
    """Raised when a requested session_id does not exist."""


class ChimeRegulatorClient(Protocol):
    """Swappable downstream client boundary for chime-regulator."""

    async def create_or_resume_session(self, request: SessionRequest) -> SessionResponse:
        """Create a new session, resume an existing one, or advance to the next stage."""
        ...

    async def regulate(self, request: InternalRegulateRequest) -> InternalRegulateResponse:
        """Forward a physical switchboard action to POST /internal/regulate."""
        ...

    async def get_traces(self, session_id: str) -> TracesResponse:
        """Fetch up to the 5 most recent trace waterfalls from GET /internal/traces/{id}."""
        ...


@dataclass
class _MockSession:
    session_id: str
    stage_id: int = 1
    stage_completed: bool = False
    selected_target: SubsystemTarget = "chime-regulator"
    slider_value: int = 50
    warm_targets: set[SubsystemTarget] = field(default_factory=set)
    chamber_logs: list[str] = field(
        default_factory=lambda: ["Stage 1 initialized. Downstream services are dormant."]
    )
    gauges: GaugeReadings = field(
        default_factory=lambda: GaugeReadings(
            mains_tension=0.0,
            resonance_drag=0.0,
            reserve_pressure=0.0,
        )
    )
    traces: list[TraceWaterfall] = field(default_factory=list)


class MockChimeRegulatorClient:
    """In-memory Stage 1 mock of chime-regulator for switchboard-room bootstrap."""

    def __init__(self) -> None:
        self._sessions: dict[str, _MockSession] = {}

    async def create_or_resume_session(self, request: SessionRequest) -> SessionResponse:
        """Create or resume a Stage 1 mock session."""
        if request.session_id and request.session_id in self._sessions:
            session = self._sessions[request.session_id]
            if request.advance_stage and session.stage_completed and session.stage_id < 5:
                session.stage_id += 1
                session.stage_completed = False
                session.warm_targets.clear()
                session.chamber_logs.append(f"Advanced to Stage {session.stage_id}.")
        else:
            session_id = request.session_id or f"sess-{uuid4().hex[:12]}"
            session = _MockSession(session_id=session_id)
            self._sessions[session_id] = session

        return SessionResponse(
            session_id=session.session_id,
            state=self._build_state(session),
            gauges=session.gauges,
            recent_traces=session.traces[:5],
        )

    async def regulate(self, request: InternalRegulateRequest) -> InternalRegulateResponse:
        """Evaluate Stage 1 control action and record a trace waterfall."""
        session = self._sessions.get(request.session_id)
        if session is None:
            raise SessionNotFoundError(f"Session '{request.session_id}' not found")

        session.selected_target = request.target
        session.slider_value = request.value

        cold_start, status, log_line = self._apply_action(session, request.action, request.target)
        session.chamber_logs = (session.chamber_logs + [log_line])[-10:]

        waterfall = self._build_waterfall(
            action=request.action,
            target=request.target,
            cold_start=cold_start,
            status=status,
            gauges=session.gauges,
        )
        session.traces = [waterfall, *session.traces][:5]

        return InternalRegulateResponse(
            state=self._build_state(session),
            gauges=session.gauges,
            latest_trace=waterfall,
        )

    async def get_traces(self, session_id: str) -> TracesResponse:
        """Return up to the 5 most recent trace waterfalls for the session."""
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(f"Session '{session_id}' not found")
        return TracesResponse(session_id=session_id, traces=session.traces[:5])

    def _apply_action(
        self,
        session: _MockSession,
        action: ControlAction,
        target: SubsystemTarget,
    ) -> tuple[bool, SpanStatus, str]:
        if action == "RESET":
            session.warm_targets.clear()
            session.stage_completed = False
            session.gauges = GaugeReadings(
                mains_tension=0.0,
                resonance_drag=0.0,
                reserve_pressure=0.0,
            )
            return False, "OK", "RESET: All subsystems returned to dormant state."

        if action == "PROBE":
            cold_start = target not in session.warm_targets
            session.warm_targets.add(target)
            warm_count = len(session.warm_targets)
            session.gauges = GaugeReadings(
                mains_tension=round(min(100.0, 25.0 + warm_count * 20.0), 1),
                resonance_drag=78.0 if cold_start else 18.0,
                reserve_pressure=round(min(100.0, warm_count * 30.0), 1),
            )
            state_label = "cold-start" if cold_start else "warm"
            return cold_start, "OK", f"PROBE {target}: {state_label} response recorded."

        if action == "CALIBRATE":
            warm_count = len(session.warm_targets)
            session.gauges = GaugeReadings(
                mains_tension=round(min(100.0, 20.0 + warm_count * 20.0), 1),
                resonance_drag=22.0 if warm_count else 45.0,
                reserve_pressure=round(min(100.0, warm_count * 30.0), 1),
            )
            return False, "OK", f"CALIBRATE {target}: trim set to {session.slider_value}."

        # action == "ENGAGE"
        all_warm = set(STAGE_1_TARGETS).issubset(session.warm_targets)
        if all_warm:
            session.stage_completed = True
            session.gauges = GaugeReadings(
                mains_tension=65.0,
                resonance_drag=12.0,
                reserve_pressure=90.0,
            )
            return False, "OK", "ENGAGE: All Stage 1 subsystems warm. Tower synchronized."

        session.gauges = GaugeReadings(
            mains_tension=30.0,
            resonance_drag=85.0,
            reserve_pressure=round(len(session.warm_targets) * 25.0, 1),
        )
        return False, "ERROR", "ENGAGE failed: dormant subsystems remain. Probe all targets first."

    @staticmethod
    def _build_state(session: _MockSession) -> StageState:
        return StageState(
            stage_id=session.stage_id,
            stage_completed=session.stage_completed,
            targets=list(STAGE_1_TARGETS),
            selected_target=session.selected_target,
            slider_value=session.slider_value,
            chamber_logs=list(session.chamber_logs),
            manual=STAGE_1_MANUAL,
        )

    @staticmethod
    def _build_waterfall(
        action: ControlAction,
        target: SubsystemTarget,
        cold_start: bool,
        status: SpanStatus,
        gauges: GaugeReadings,
    ) -> TraceWaterfall:
        root_id = uuid4().hex[:16]
        child_id = uuid4().hex[:16]
        child_duration = 780 if cold_start else 35
        total_duration = child_duration + 20

        spans = [
            Span(
                span_id=root_id,
                parent_span_id=None,
                service_name="chime-regulator",
                operation_name=f"POST /internal/regulate ({action})",
                start_offset_ms=0,
                duration_ms=total_duration,
                status=status,
                attributes={
                    "action.type": action,
                    "action.target": target,
                    "gauge.mains_tension": gauges.mains_tension,
                    "gauge.resonance_drag": gauges.resonance_drag,
                },
            ),
            Span(
                span_id=child_id,
                parent_span_id=root_id,
                service_name=target,
                operation_name=f"{action.lower()}.{target}",
                start_offset_ms=10,
                duration_ms=child_duration,
                status=status,
                attributes={
                    "container.cold_start": cold_start,
                    "target.warm": not cold_start,
                    "gauge.reserve_pressure": gauges.reserve_pressure,
                    "gauge.mains_tension.overload_pct": max(0.0, gauges.mains_tension - 80.0),
                },
            ),
        ]

        return TraceWaterfall(
            trace_id=uuid4().hex,
            timestamp=datetime.now(UTC),
            action=action,
            target=target,
            total_duration_ms=total_duration,
            status=status,
            spans=spans,
        )


class HttpChimeRegulatorClient:
    """HTTP downstream client for chime-regulator with OIDC and W3C traceparent."""

    def __init__(
        self,
        base_url: str,
        auth_provider: AuthHeaderProvider,
        timeout_seconds: float = 5.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth_provider = auth_provider
        self._timeout = timeout_seconds
        self._http_client = http_client

    async def create_or_resume_session(self, request: SessionRequest) -> SessionResponse:
        """Forward session creation/resumption to chime-regulator."""
        headers = self._build_headers()
        async with self._client_context() as client:
            response = await client.post(
                f"{self._base_url}/internal/session",
                json=request.model_dump(mode="json"),
                headers=headers,
            )
            response.raise_for_status()
            return SessionResponse.model_validate(response.json())

    async def regulate(self, request: InternalRegulateRequest) -> InternalRegulateResponse:
        """Invoke POST /internal/regulate on chime-regulator."""
        headers = self._build_headers()
        async with self._client_context() as client:
            response = await client.post(
                f"{self._base_url}/internal/regulate",
                json=request.model_dump(mode="json"),
                headers=headers,
            )
            if response.status_code == 404:
                raise SessionNotFoundError(f"Session '{request.session_id}' not found")
            response.raise_for_status()
            return InternalRegulateResponse.model_validate(response.json())

    async def get_traces(self, session_id: str) -> TracesResponse:
        """Invoke GET /internal/traces/{session_id} on chime-regulator."""
        headers = self._build_headers()
        async with self._client_context() as client:
            response = await client.get(
                f"{self._base_url}/internal/traces/{session_id}",
                headers=headers,
            )
            if response.status_code == 404:
                raise SessionNotFoundError(f"Session '{session_id}' not found")
            response.raise_for_status()
            return TracesResponse.model_validate(response.json())

    def _build_headers(self) -> dict[str, str]:
        headers = self._auth_provider.get_headers(self._base_url)
        propagate.inject(headers)
        return headers

    def _client_context(self) -> _AsyncClientContext:
        return _AsyncClientContext(self._http_client, self._timeout)


class _AsyncClientContext:
    """Reuses an injected httpx.AsyncClient or manages a per-call client."""

    def __init__(self, client: httpx.AsyncClient | None, timeout: float) -> None:
        self._injected = client
        self._timeout = timeout
        self._owned: httpx.AsyncClient | None = None

    async def __aenter__(self) -> httpx.AsyncClient:
        if self._injected is not None:
            return self._injected
        self._owned = httpx.AsyncClient(timeout=self._timeout)
        return self._owned

    async def __aexit__(self, *args: object) -> None:
        if self._owned is not None:
            await self._owned.aclose()
