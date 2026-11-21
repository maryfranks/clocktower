import { describe, expect, it } from "vitest";
import { mockAction, mockCreateSession } from "@/api/mockStage1";
import { stripGaugeAttributes } from "@/api/clocktowerClient";
import { SUBSYSTEM_TARGETS, type ControlAction, type SubsystemTarget } from "@/api/types";

const act = (id: string, action: ControlAction, target: SubsystemTarget, value = 50) =>
  mockAction({ session_id: id, stage_id: 1, action, target, value });
const tick = (r: ReturnType<typeof act>) =>
  r.latest_trace.spans.find((s) => s.operation_name.startsWith("tick"))!;

describe("Stage 1 mock", () => {
  it("cold probe ~2000ms with cold_start, then warm ~60ms", () => {
    const { session_id } = mockCreateSession();
    const a = act(session_id, "PROBE", "escapement-gear");
    expect(tick(a).attributes["container.cold_start"]).toBe(true);
    expect(tick(a).duration_ms).toBeGreaterThanOrEqual(1900);
    expect(a.gauges.resonance_drag).toBeGreaterThan(80);
    const b = act(session_id, "PROBE", "escapement-gear");
    expect(tick(b).attributes["container.cold_start"]).toBe(false);
    expect(tick(b).duration_ms).toBeLessThanOrEqual(70);
  });
  it("calibrate 75 on mainspring only after all warm; engage completes; reset clears", () => {
    const { session_id } = mockCreateSession();
    expect(act(session_id, "CALIBRATE", "mainspring-drive", 75).latest_trace.status).toBe("ERROR");
    SUBSYSTEM_TARGETS.forEach((t) => act(session_id, "PROBE", t));
    expect(act(session_id, "CALIBRATE", "mainspring-drive", 70).latest_trace.status).toBe("ERROR");
    expect(act(session_id, "ENGAGE", "mainspring-drive").state.stage_completed).toBe(false);
    expect(act(session_id, "CALIBRATE", "mainspring-drive", 75).latest_trace.status).toBe("OK");
    expect(act(session_id, "ENGAGE", "mainspring-drive").state.stage_completed).toBe(true);
    act(session_id, "RESET", "mainspring-drive");
    const s = mockCreateSession(session_id);
    expect(s.state.stage_completed).toBe(false);
    expect(s.recent_traces).toHaveLength(0);
  });
  it("strips gauge.* attributes", () => {
    const { session_id } = mockCreateSession();
    const t = stripGaugeAttributes(act(session_id, "PROBE", "pendulum-cache").latest_trace);
    expect(
      t.spans.flatMap((s) => Object.keys(s.attributes)).some((k) => k.startsWith("gauge.")),
    ).toBe(false);
  });
  it("handles non-mainspring calibration, overwound/slack values, engage failure reasons, and 404s", () => {
    const { session_id } = mockCreateSession();
    const noFit = act(session_id, "CALIBRATE", "escapement-gear", 75);
    expect(noFit.latest_trace.status).toBe("ERROR");
    expect(tick(noFit).attributes["calibrate.rejected"]).toBe("no_fitting");

    const coldEngage = act(session_id, "ENGAGE", "mainspring-drive");
    expect(coldEngage.latest_trace.status).toBe("ERROR");
    expect(tick(coldEngage).attributes["engage.all_warm"]).toBe(false);

    SUBSYSTEM_TARGETS.forEach((t) => act(session_id, "PROBE", t));

    const unwoundEngage = act(session_id, "ENGAGE", "mainspring-drive");
    expect(unwoundEngage.latest_trace.status).toBe("ERROR");
    expect(tick(unwoundEngage).attributes["engage.all_warm"]).toBe(true);
    expect(tick(unwoundEngage).attributes["engage.calibrated"]).toBe(false);

    expect(act(session_id, "CALIBRATE", "mainspring-drive", 75).latest_trace.status).toBe("OK");
    const overwound = act(session_id, "CALIBRATE", "mainspring-drive", 85);
    expect(overwound.latest_trace.status).toBe("ERROR");
    expect(tick(overwound).attributes["calibrate.rejected"]).toBe("overwound");
    expect(act(session_id, "ENGAGE", "mainspring-drive").state.stage_completed).toBe(false);

    expect(() => act("unknown-sess", "PROBE", "escapement-gear")).toThrow("404 Session not found");
  });
});
