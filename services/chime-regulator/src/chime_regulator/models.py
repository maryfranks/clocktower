"""Pydantic models strictly conforming to openapi.yaml."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ControlAction = Literal["PROBE", "CALIBRATE", "ENGAGE", "RESET"]
SubsystemTarget = Literal[
    "mainspring-drive",
    "chime-regulator",
    "escapement-gear",
    "pendulum-cache",
]
SpanStatus = Literal["OK", "ERROR"]
AttributeValue = bool | int | float | str


class GaugeReadings(BaseModel):
    """Analog chamber gauge readings (0-100)."""

    mains_tension: float = Field(ge=0, le=100)
    resonance_drag: float = Field(ge=0, le=100)
    reserve_pressure: float = Field(ge=0, le=100)


class Span(BaseModel):
    """Single structured span inside a trace waterfall."""

    span_id: str
    parent_span_id: str | None
    service_name: str
    operation_name: str
    start_offset_ms: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    status: SpanStatus
    attributes: dict[str, AttributeValue]


class TraceWaterfall(BaseModel):
    """Distributed trace waterfall returned to the UI."""

    trace_id: str
    timestamp: datetime
    action: ControlAction
    target: SubsystemTarget
    total_duration_ms: int = Field(ge=0)
    status: SpanStatus
    spans: list[Span]


class RealWorldParallel(BaseModel):
    """Educational observability parallel for a puzzle stage."""

    title: str
    summary: str
    completion_takeaway: str


class FieldManualContent(BaseModel):
    """Engineer's Field Manual content for the active stage."""

    stage_title: str
    how_to_play: list[str]
    stage_hints: list[str]
    real_world_parallel: RealWorldParallel


class StageState(BaseModel):
    """Current stage puzzle state and operator controls."""

    stage_id: int = Field(ge=1, le=5)
    stage_completed: bool
    targets: list[SubsystemTarget]
    selected_target: SubsystemTarget
    slider_value: int = Field(ge=0, le=100, multiple_of=5)
    chamber_logs: list[str]
    manual: FieldManualContent


class SessionRequest(BaseModel):
    """Request body for POST /internal/session."""

    session_id: str | None = None
    advance_stage: bool = False


class SessionResponse(BaseModel):
    """Response body for POST /internal/session."""

    session_id: str
    state: StageState
    gauges: GaugeReadings
    recent_traces: list[TraceWaterfall]


class TracesResponse(BaseModel):
    """Response body for GET /internal/traces/{session_id}."""

    session_id: str
    traces: list[TraceWaterfall] = Field(max_length=5)


class CachedSessionState(BaseModel):
    """Session state persisted in pendulum-cache."""

    session_id: str
    stage_id: int = Field(ge=1, le=5)
    warm_targets: list[SubsystemTarget]
    calibrated_targets: list[SubsystemTarget]
    calibration_values: dict[str, int] = Field(default_factory=dict)
    stage_completed: bool


class InternalRegulateRequest(BaseModel):
    """Internal request received by POST /internal/regulate."""

    session_id: str
    stage_id: int = Field(ge=1, le=5)
    action: ControlAction
    target: SubsystemTarget
    value: int = Field(ge=0, le=100, multiple_of=5)


class InternalRegulateResponse(BaseModel):
    """Internal response returned by POST /internal/regulate."""

    state: StageState
    gauges: GaugeReadings
    latest_trace: TraceWaterfall


class InternalTickRequest(BaseModel):
    """Internal request sent to escapement-gear POST /internal/tick."""

    session_id: str
    stage_id: int = Field(ge=1, le=5)
    action: ControlAction
    target: SubsystemTarget
    value: int = Field(ge=0, le=100, multiple_of=5)
    is_warm: bool


class InternalTickResponse(BaseModel):
    """Internal response returned by escapement-gear POST /internal/tick."""

    duration_ms: int = Field(ge=0)
    cold_start: bool
    status: SpanStatus
    message: str
    span: Span
