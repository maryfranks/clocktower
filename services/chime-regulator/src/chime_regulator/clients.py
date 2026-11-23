"""Downstream client protocols and Stage 1 mocks for pendulum-cache and escapement-gear."""

from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from chime_regulator.models import (
    CachedSessionState,
    InternalTickRequest,
    InternalTickResponse,
    Span,
    SpanStatus,
)


class PendulumCacheClient(Protocol):
    """Client boundary for pendulum-cache (/internal/state/{session_id})."""

    async def get_state(self, session_id: str) -> CachedSessionState | None:
        """Fetch cached session state, returning None if not found."""
        ...

    async def set_state(self, session_id: str, state: CachedSessionState) -> CachedSessionState:
        """Persist updated session state."""
        ...


class EscapementGearClient(Protocol):
    """Client boundary for escapement-gear (/internal/tick)."""

    async def tick(self, request: InternalTickRequest) -> InternalTickResponse:
        """Simulate mechanical escapement timing and return span diagnostics."""
        ...


class MockPendulumCacheClient:
    """In-memory mock of pendulum-cache for Stage 1 regulation."""

    def __init__(self, initial_states: dict[str, CachedSessionState] | None = None) -> None:
        self._states: dict[str, CachedSessionState] = {
            sid: state.model_copy(deep=True) for sid, state in (initial_states or {}).items()
        }

    async def get_state(self, session_id: str) -> CachedSessionState | None:
        """Return a copy of cached session state or None if missing."""
        state = self._states.get(session_id)
        return state.model_copy(deep=True) if state is not None else None

    async def set_state(self, session_id: str, state: CachedSessionState) -> CachedSessionState:
        """Store a copy of the session state and return it."""
        stored = state.model_copy(deep=True)
        self._states[session_id] = stored
        return stored.model_copy(deep=True)


class MockEscapementGearClient:
    """In-memory mock of escapement-gear (/internal/tick) for Stage 1."""

    async def tick(self, request: InternalTickRequest) -> InternalTickResponse:
        """Return deterministic Stage 1 timing, cold-start flag, and child span."""
        cold_start = request.action == "PROBE" and not request.is_warm
        status: SpanStatus = "OK"

        if request.action == "PROBE":
            duration_ms = 780 if cold_start else 35
            state_label = "cold-start" if cold_start else "warm"
            message = f"PROBE {request.target}: {state_label} response recorded."
        elif request.action == "CALIBRATE":
            duration_ms = 40
            message = f"CALIBRATE {request.target}: trim set to {request.value}."
        elif request.action == "RESET":
            duration_ms = 20
            message = "RESET: All subsystems returned to dormant state."
        else:  # ENGAGE
            duration_ms = 55 if request.is_warm else 120
            message = f"ENGAGE tick on {request.target} completed."

        span = Span(
            span_id=uuid4().hex[:16],
            parent_span_id=None,
            service_name=request.target,
            operation_name=f"{request.action.lower()}.{request.target}",
            start_offset_ms=15,
            duration_ms=duration_ms,
            status=status,
            attributes={
                "container.cold_start": cold_start,
                "target.warm": request.is_warm or request.action == "PROBE",
                "action.value": request.value,
            },
        )

        return InternalTickResponse(
            duration_ms=duration_ms,
            cold_start=cold_start,
            status=status,
            message=message,
            span=span,
        )
