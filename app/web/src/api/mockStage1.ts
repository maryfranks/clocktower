// Local Stage 1 mock: "Wake the Tower — Scale-to-Zero Cold Starts". Responses follow openapi.yaml.
import { SUBSYSTEM_TARGETS, type ActionRequest, type ActionResponse, type CachedSessionState, type FieldManualContent, type GaugeReadings, type SessionResponse, type Span, type StageState, type SubsystemTarget, type TraceWaterfall } from "./types";

export const CALIBRATION_TARGET: SubsystemTarget = "mainspring-drive";
export const CALIBRATION_VALUE = 75;

const MANUAL: FieldManualContent = {
  stage_title: "Stage 1 — Wake the Tower",
  how_to_play: [
    "The console on the left is the tower switchboard. Everything you can touch lives there.",
    "Use PREV and NEXT to choose a subsystem. The lever sets a value from 0 to 100 in notches of 5.",
    "PROBE sends a signal through the chosen subsystem and records a trace. CALIBRATE applies the lever value. ENGAGE asks the tower to run. RESET returns the tower to its overnight state.",
    "Flip the screen switch to Trace View to read the last five traces. Open a span to see its attributes.",
    "The three dials report the tower's health. They carry no numbers; read their direction and their calm.",
  ],
  stage_hints: [
    "Every subsystem slept overnight. The first signal through a sleeping gear is slow — look for the long span in Trace View.",
    "A span attribute will tell you when a gear had to wake from nothing. Probe again and compare durations.",
    "Resonance drag climbs each time a cold gear wakes. It settles once all four answer quickly.",
    "The mainspring drive holds the tower's tension. It will only accept calibration once nothing is left cold. Three quarters is the working setting.",
    "Engage only when every gear is warm and the mains tension has settled.",
  ],
  real_world_parallel: {
    title: "Scale-to-zero and cold starts",
    summary: "Serverless platforms and autoscaled containers shut idle instances down to save cost. The first request after idle pays for booting a runtime, loading code and opening connections — often seconds instead of milliseconds. Distributed traces expose this as one fat span, usually tagged with an attribute such as faas.coldstart or container.cold_start.",
    completion_takeaway: "You found the cold path by reading spans, not by guessing. In production, teams warm critical paths with provisioned concurrency, minimum instance counts or synthetic probes, and only tune downstream settings once latency is stable.",
  },
};

interface MockSession extends CachedSessionState { selected_target: SubsystemTarget; slider_value: number; logs: string[]; traces: TraceWaterfall[]; gauges: GaugeReadings }

const sessions = new Map<string, MockSession>();
let counter = 0;
const id = (p: string) => `${p}-${Date.now().toString(36)}${(counter++).toString(36)}${Math.random().toString(36).slice(2, 6)}`;
const jitter = (n: number) => Math.round(n * (0.95 + Math.random() * 0.1));

function fresh(session_id: string): MockSession {
  return {
    session_id, stage_id: 1, warm_targets: [], calibrated_targets: [], calibration_values: {}, stage_completed: false,
    selected_target: SUBSYSTEM_TARGETS[0]!, slider_value: 50,
    logs: ["TOWER DORMANT. ALL GEARS AT REST.", "AWAITING SIGNAL."], traces: [],
    gauges: { mains_tension: 20, resonance_drag: 10, reserve_pressure: 5 },
  };
}

function toState(s: MockSession): StageState {
  return { stage_id: s.stage_id, stage_completed: s.stage_completed, targets: [...SUBSYSTEM_TARGETS], selected_target: s.selected_target, slider_value: s.slider_value, chamber_logs: s.logs.slice(-12), manual: s.stage_id === 1 ? MANUAL : { ...MANUAL, stage_title: `Stage ${s.stage_id} — Briefing` } };
}

function settleGauges(s: MockSession, dragSpike = false) {
  const cold = SUBSYSTEM_TARGETS.length - s.warm_targets.length;
  const calibrated = s.calibrated_targets.includes(CALIBRATION_TARGET);
  s.gauges = {
    mains_tension: calibrated ? 50 : 20 + s.warm_targets.length * 4,
    resonance_drag: dragSpike ? 90 : 12 + cold * 14,
    reserve_pressure: Math.min(100, 5 + s.warm_targets.length * 18 + (calibrated ? 10 : 0) + (s.stage_completed ? 13 : 0)),
  };
}

function buildTrace(req: ActionRequest, inner: { duration: number; cold: boolean; status: "OK" | "ERROR"; message: string; extra?: Record<string, string | number | boolean> }, s: MockSession): TraceWaterfall {
  const root = id("span"), reg = id("span");
  const gw = 4, regStart = 6, cacheRead = 3, tickStart = regStart + 2 + cacheRead;
  const tickEnd = tickStart + inner.duration;
  const spans: Span[] = [
    { span_id: root, parent_span_id: null, service_name: "switchboard-room", operation_name: `POST /api/action ${req.action}`, start_offset_ms: 0, duration_ms: tickEnd + 6 + gw, status: inner.status,
      attributes: { "http.method": "POST", "http.route": "/api/action", "tower.action": req.action, "tower.target": req.target, "gauge.resonance_drag": s.gauges.resonance_drag } },
    { span_id: reg, parent_span_id: root, service_name: "chime-regulator", operation_name: "regulate", start_offset_ms: regStart, duration_ms: tickEnd + 4 - regStart, status: inner.status,
      attributes: { "tower.stage_id": 1, "tower.value": req.value, "gauge.mains_tension": s.gauges.mains_tension } },
    { span_id: id("span"), parent_span_id: reg, service_name: "pendulum-cache", operation_name: "state.get", start_offset_ms: regStart + 2, duration_ms: cacheRead, status: "OK",
      attributes: { "cache.hit": true, "cache.warm_targets": s.warm_targets.length } },
    { span_id: id("span"), parent_span_id: reg, service_name: req.target === "chime-regulator" || req.target === "pendulum-cache" ? req.target : "escapement-gear", operation_name: `tick ${req.target}`, start_offset_ms: tickStart, duration_ms: inner.duration, status: inner.status,
      attributes: { "container.cold_start": inner.cold, "tick.message": inner.message, "tower.target": req.target, ...(inner.extra ?? {}), "gauge.reserve_pressure": s.gauges.reserve_pressure } },
    { span_id: id("span"), parent_span_id: reg, service_name: "pendulum-cache", operation_name: "state.set", start_offset_ms: tickEnd + 1, duration_ms: 2, status: "OK", attributes: { "cache.write": true } },
  ];
  return { trace_id: id("trace"), timestamp: new Date().toISOString(), action: req.action, target: req.target, total_duration_ms: spans[0]!.duration_ms, status: inner.status, spans };
}

export function mockCreateSession(session_id?: string | null, advance_stage = false): SessionResponse {
  let s = session_id ? sessions.get(session_id) : undefined;
  if (!s) { s = fresh(id("sess")); sessions.set(s.session_id, s); }
  else if (advance_stage && s.stage_completed && s.stage_id < 5) {
    const next = s.stage_id + 1;
    Object.assign(s, fresh(s.session_id), { stage_id: next });
    s.logs = [`STAGE ${next} BRIEFING ISSUED.`, "AWAITING SIGNAL."];
  }
  return { session_id: s.session_id, state: toState(s), gauges: s.gauges, recent_traces: s.traces.slice(0, 5) };
}

export function mockAction(req: ActionRequest): ActionResponse {
  const s = sessions.get(req.session_id);
  if (!s) throw new Error("404 Session not found");
  s.selected_target = req.target; s.slider_value = req.value;
  const t = req.target.toUpperCase();
  let inner: Parameters<typeof buildTrace>[1];

  if (req.action === "RESET") {
    const r = fresh(s.session_id); r.stage_id = s.stage_id; Object.assign(s, r); s.selected_target = req.target; s.slider_value = req.value;
    s.logs.push("RESET. GEARS RETURNED TO REST. TRACE TAPE CLEARED.");
    inner = { duration: 3, cold: false, status: "OK", message: "state cleared" };
    settleGauges(s);
    const trace = buildTrace(req, inner, s);
    return { session_id: s.session_id, state: toState(s), gauges: s.gauges, latest_trace: trace };
  }

  let spike = false;
  if (req.action === "PROBE") {
    const wasWarm = s.warm_targets.includes(req.target);
    if (!wasWarm) { s.warm_targets.push(req.target); spike = true; }
    inner = wasWarm ? { duration: jitter(60), cold: false, status: "OK", message: "tick clean" } : { duration: jitter(2000), cold: true, status: "OK", message: "gear woke from rest" };
    s.logs.push(wasWarm ? `PROBE ${t}: CLEAN TICK, ${inner.duration}MS.` : `PROBE ${t}: GEAR GROANS AWAKE, ${inner.duration}MS. DRAG RISING.`);
  } else if (req.action === "CALIBRATE") {
    const cold = SUBSYSTEM_TARGETS.filter((x) => !s.warm_targets.includes(x));
    if (req.target !== CALIBRATION_TARGET) {
      inner = { duration: jitter(60), cold: false, status: "ERROR", message: "no calibration fitting", extra: { "calibrate.rejected": "no_fitting" } };
      s.logs.push(`CALIBRATE ${t}: NO FITTING ON THIS GEAR.`);
    } else if (cold.length) {
      inner = { duration: jitter(60), cold: false, status: "ERROR", message: "cold gears in train", extra: { "calibrate.rejected": "cold_targets", "calibrate.cold_count": cold.length } };
      s.logs.push(`CALIBRATE ${t}: REFUSED. ${cold.length} GEAR(S) STILL COLD.`);
    } else if (req.value !== CALIBRATION_VALUE) {
      inner = { duration: jitter(60), cold: false, status: "ERROR", message: "tension out of band", extra: { "calibrate.value": req.value, "calibrate.rejected": req.value < CALIBRATION_VALUE ? "slack" : "overwound" } };
      s.calibrated_targets = s.calibrated_targets.filter((x) => x !== req.target);
      s.logs.push(`CALIBRATE ${t} @ ${req.value}: SPRING ${req.value < CALIBRATION_VALUE ? "SLACK" : "OVERWOUND"}.`);
    } else {
      if (!s.calibrated_targets.includes(req.target)) s.calibrated_targets.push(req.target);
      s.calibration_values = { ...s.calibration_values, [req.target]: req.value };
      inner = { duration: jitter(60), cold: false, status: "OK", message: "tension set", extra: { "calibrate.value": req.value } };
      s.logs.push(`CALIBRATE ${t} @ ${req.value}: MAINS TENSION HOLDS STEADY.`);
    }
  } else {
    const allWarm = s.warm_targets.length === SUBSYSTEM_TARGETS.length;
    const calibrated = s.calibrated_targets.includes(CALIBRATION_TARGET);
    if (allWarm && calibrated) {
      s.stage_completed = true;
      inner = { duration: jitter(60), cold: false, status: "OK", message: "tower engaged" };
      s.logs.push("ENGAGE: ALL GEARS TURN AS ONE. THE TOWER STRIKES THE HOUR.");
    } else {
      inner = { duration: jitter(60), cold: false, status: "ERROR", message: "engage refused", extra: { "engage.all_warm": allWarm, "engage.calibrated": calibrated } };
      s.logs.push(`ENGAGE REFUSED: ${!allWarm ? "COLD GEARS IN THE TRAIN" : "MAINS TENSION UNSET"}.`);
    }
  }
  settleGauges(s, spike);
  const trace = buildTrace(req, inner, s);
  s.traces = [trace, ...s.traces].slice(0, 5);
  return { session_id: s.session_id, state: toState(s), gauges: s.gauges, latest_trace: trace };
}

export function mockTraces(session_id: string) {
  const s = sessions.get(session_id);
  if (!s) throw new Error("404 Session not found");
  return { session_id, traces: s.traces.slice(0, 5) };
}
