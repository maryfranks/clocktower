// Types mirror components.schemas in openapi.yaml (The Clock Tower API v1.0.0).
export type ControlAction = "PROBE" | "CALIBRATE" | "ENGAGE" | "RESET";
export type SubsystemTarget = "mainspring-drive" | "chime-regulator" | "escapement-gear" | "pendulum-cache";
export const SUBSYSTEM_TARGETS: SubsystemTarget[] = ["mainspring-drive", "chime-regulator", "escapement-gear", "pendulum-cache"];

export interface GaugeReadings { mains_tension: number; resonance_drag: number; reserve_pressure: number }
export interface Span {
  span_id: string; parent_span_id: string | null; service_name: string; operation_name: string;
  start_offset_ms: number; duration_ms: number; status: "OK" | "ERROR";
  attributes: Record<string, string | number | boolean>;
}
export interface TraceWaterfall {
  trace_id: string; timestamp: string; action: ControlAction; target: SubsystemTarget;
  total_duration_ms: number; status: "OK" | "ERROR"; spans: Span[];
}
export interface RealWorldParallel { title: string; summary: string; completion_takeaway: string }
export interface FieldManualContent { stage_title: string; how_to_play: string[]; stage_hints: string[]; real_world_parallel: RealWorldParallel }
export interface StageState {
  stage_id: number; stage_completed: boolean; targets: SubsystemTarget[]; selected_target: SubsystemTarget;
  slider_value: number; chamber_logs: string[]; manual: FieldManualContent;
}
export interface SessionRequest { session_id?: string | null; advance_stage?: boolean }
export interface SessionResponse { session_id: string; state: StageState; gauges: GaugeReadings; recent_traces: TraceWaterfall[] }
export interface ActionRequest { session_id: string; stage_id: number; action: ControlAction; target: SubsystemTarget; value: number }
export interface ActionResponse { session_id: string; state: StageState; gauges: GaugeReadings; latest_trace: TraceWaterfall }
export interface TracesResponse { session_id: string; traces: TraceWaterfall[] }
export interface CachedSessionState {
  session_id: string; stage_id: number; warm_targets: SubsystemTarget[]; calibrated_targets: SubsystemTarget[];
  calibration_values?: Record<string, number>; stage_completed: boolean;
}
