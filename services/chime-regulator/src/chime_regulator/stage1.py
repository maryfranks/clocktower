"""Stage 1 evaluation logic, Field Manual content, gauge physics, and waterfall assembly."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from chime_regulator.models import (
    CachedSessionState,
    ControlAction,
    FieldManualContent,
    GaugeReadings,
    InternalTickResponse,
    RealWorldParallel,
    Span,
    SpanStatus,
    StageState,
    SubsystemTarget,
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


def initial_gauges_for_state(cached: CachedSessionState) -> GaugeReadings:
    """Compute baseline analog gauge readings from a CachedSessionState."""
    if cached.stage_completed:
        return GaugeReadings(
            mains_tension=65.0,
            resonance_drag=12.0,
            reserve_pressure=90.0,
        )
    warm_count = len(cached.warm_targets)
    if warm_count == 0:
        return GaugeReadings(
            mains_tension=0.0,
            resonance_drag=0.0,
            reserve_pressure=0.0,
        )
    return GaugeReadings(
        mains_tension=round(min(100.0, 25.0 + warm_count * 20.0), 1),
        resonance_drag=18.0,
        reserve_pressure=round(min(100.0, warm_count * 30.0), 1),
    )


def evaluate_stage1_action(
    cached: CachedSessionState,
    action: ControlAction,
    target: SubsystemTarget,
    value: int,
    tick_resp: InternalTickResponse,
) -> tuple[CachedSessionState, GaugeReadings, SpanStatus, str]:
    """Apply Stage 1 rules to cached state and return (new_state, gauges, status, log_line)."""
    warm_targets = list(cached.warm_targets)
    calibrated_targets = list(cached.calibrated_targets)
    calibration_values = dict(cached.calibration_values)
    stage_completed = cached.stage_completed

    if action == "RESET":
        warm_targets = []
        calibrated_targets = []
        calibration_values = {}
        stage_completed = False
        gauges = GaugeReadings(
            mains_tension=0.0,
            resonance_drag=0.0,
            reserve_pressure=0.0,
        )
        status: SpanStatus = "OK"
        log_line = "RESET: All subsystems returned to dormant state."
    elif action == "PROBE":
        if target not in warm_targets:
            warm_targets.append(target)
        warm_count = len(warm_targets)
        gauges = GaugeReadings(
            mains_tension=round(min(100.0, 25.0 + warm_count * 20.0), 1),
            resonance_drag=78.0 if tick_resp.cold_start else 18.0,
            reserve_pressure=round(min(100.0, warm_count * 30.0), 1),
        )
        status = tick_resp.status
        log_line = tick_resp.message
    elif action == "CALIBRATE":
        if target not in calibrated_targets:
            calibrated_targets.append(target)
        calibration_values[target] = value
        warm_count = len(warm_targets)
        gauges = GaugeReadings(
            mains_tension=round(min(100.0, 20.0 + warm_count * 20.0), 1),
            resonance_drag=22.0 if warm_count else 45.0,
            reserve_pressure=round(min(100.0, warm_count * 30.0), 1),
        )
        status = tick_resp.status
        log_line = f"CALIBRATE {target}: trim set to {value}."
    else:  # ENGAGE
        all_warm = set(STAGE_1_TARGETS).issubset(warm_targets)
        if all_warm:
            stage_completed = True
            gauges = GaugeReadings(
                mains_tension=65.0,
                resonance_drag=12.0,
                reserve_pressure=90.0,
            )
            status = "OK"
            log_line = "ENGAGE: All Stage 1 subsystems warm. Tower synchronized."
        else:
            gauges = GaugeReadings(
                mains_tension=30.0,
                resonance_drag=85.0,
                reserve_pressure=round(len(warm_targets) * 25.0, 1),
            )
            status = "ERROR"
            log_line = "ENGAGE failed: dormant subsystems remain. Probe all targets first."

    updated_state = CachedSessionState(
        session_id=cached.session_id,
        stage_id=cached.stage_id,
        warm_targets=warm_targets,
        calibrated_targets=calibrated_targets,
        calibration_values=calibration_values,
        stage_completed=stage_completed,
    )
    return updated_state, gauges, status, log_line


def build_stage_state(
    cached: CachedSessionState,
    selected_target: SubsystemTarget,
    slider_value: int,
    chamber_logs: list[str],
) -> StageState:
    """Build public StageState from CachedSessionState."""
    return StageState(
        stage_id=cached.stage_id,
        stage_completed=cached.stage_completed,
        targets=list(STAGE_1_TARGETS),
        selected_target=selected_target,
        slider_value=slider_value,
        chamber_logs=chamber_logs,
        manual=STAGE_1_MANUAL,
    )


def assemble_waterfall(
    trace_id: str,
    action: ControlAction,
    target: SubsystemTarget,
    status: SpanStatus,
    gauges: GaugeReadings,
    tick_resp: InternalTickResponse,
    cache_lookup_ms: int = 8,
) -> TraceWaterfall:
    """Assemble a TraceWaterfall combining regulator, cache lookup, and escapement-gear spans."""
    root_id = uuid4().hex[:16]
    cache_span_id = uuid4().hex[:16]
    tick_start_ms = cache_lookup_ms + 4
    total_duration_ms = tick_start_ms + tick_resp.duration_ms + 8

    root_span = Span(
        span_id=root_id,
        parent_span_id=None,
        service_name="chime-regulator",
        operation_name=f"POST /internal/regulate ({action})",
        start_offset_ms=0,
        duration_ms=total_duration_ms,
        status=status,
        attributes={
            "action.type": action,
            "action.target": target,
            "gauge.mains_tension": gauges.mains_tension,
            "gauge.mains_tension.raw": gauges.mains_tension,
            "gauge.resonance_drag": gauges.resonance_drag,
            "gauge.resonance_drag.spike_ms": tick_resp.duration_ms if tick_resp.cold_start else 0,
        },
    )

    cache_span = Span(
        span_id=cache_span_id,
        parent_span_id=root_id,
        service_name="pendulum-cache",
        operation_name="GET /internal/state",
        start_offset_ms=2,
        duration_ms=cache_lookup_ms,
        status="OK",
        attributes={"cache.hit": True},
    )

    tick_attrs = dict(tick_resp.span.attributes)
    tick_attrs["gauge.reserve_pressure"] = gauges.reserve_pressure
    tick_attrs["gauge.mains_tension.overload_pct"] = max(0.0, gauges.mains_tension - 80.0)

    tick_span = tick_resp.span.model_copy(
        update={
            "parent_span_id": root_id,
            "start_offset_ms": tick_start_ms,
            "status": status,
            "attributes": tick_attrs,
        }
    )

    return TraceWaterfall(
        trace_id=trace_id,
        timestamp=datetime.now(UTC),
        action=action,
        target=target,
        total_duration_ms=total_duration_ms,
        status=status,
        spans=[root_span, cache_span, tick_span],
    )
