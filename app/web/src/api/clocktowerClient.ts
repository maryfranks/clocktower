// Client for openapi.yaml gateway endpoints. VITE_USE_MOCK_API defaults to true (local Stage 1 mock).
import { mockAction, mockCreateSession, mockTraces } from "./mockStage1";
import type {
  ActionRequest,
  ActionResponse,
  SessionRequest,
  SessionResponse,
  TraceWaterfall,
  TracesResponse,
} from "./types";

export const USE_MOCK_API = String(import.meta.env["VITE_USE_MOCK_API"] ?? "true") !== "false";
const BASE = (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ?? "";

/** UI must never see gauge.* span attributes. */
export function stripGaugeAttributes(trace: TraceWaterfall): TraceWaterfall {
  return {
    ...trace,
    spans: trace.spans.map((sp) => ({
      ...sp,
      attributes: Object.fromEntries(
        Object.entries(sp.attributes).filter(([k]) => !k.startsWith("gauge.")),
      ),
    })),
  };
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}
const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function createOrResumeSession(body: SessionRequest = {}): Promise<SessionResponse> {
  const r = USE_MOCK_API
    ? (await delay(120), mockCreateSession(body.session_id, body.advance_stage === true))
    : await http<SessionResponse>("/api/session", { method: "POST", body: JSON.stringify(body) });
  return { ...r, recent_traces: r.recent_traces.map(stripGaugeAttributes) };
}

export async function executeControlAction(body: ActionRequest): Promise<ActionResponse> {
  let r: ActionResponse;
  if (USE_MOCK_API) {
    r = mockAction(body);
    await delay(Math.min(r.latest_trace.total_duration_ms, 2200));
  } else
    r = await http<ActionResponse>("/api/action", { method: "POST", body: JSON.stringify(body) });
  return { ...r, latest_trace: stripGaugeAttributes(r.latest_trace) };
}

export async function getSessionTraces(session_id: string): Promise<TracesResponse> {
  const r = USE_MOCK_API
    ? mockTraces(session_id)
    : await http<TracesResponse>(`/api/traces/${encodeURIComponent(session_id)}`);
  return { ...r, traces: r.traces.slice(0, 5).map(stripGaugeAttributes) };
}

export function advanceStage(session_id: string): Promise<SessionResponse> {
  return createOrResumeSession({ session_id, advance_stage: true });
}
