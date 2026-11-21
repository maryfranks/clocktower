import { describe, expect, it, vi } from "vitest";
import {
  advanceStage,
  createOrResumeSession,
  executeControlAction,
  getSessionTraces,
} from "@/api/clocktowerClient";
import { SUBSYSTEM_TARGETS } from "@/api/types";

const hasGaugeAttr = (spans: { attributes: Record<string, unknown> }[]) =>
  spans.flatMap((s) => Object.keys(s.attributes)).some((k) => k.startsWith("gauge."));

describe("clocktowerClient", () => {
  it("creates session, runs actions, fetches up to 5 traces, and strips gauge.* attributes", async () => {
    vi.useFakeTimers();
    try {
      const sPromise = createOrResumeSession();
      await vi.runAllTimersAsync();
      const s = await sPromise;
      expect(s.session_id).toMatch(/^sess-/);

      for (let i = 0; i < 6; i++) {
        const p = executeControlAction({
          session_id: s.session_id,
          stage_id: 1,
          action: "PROBE",
          target: SUBSYSTEM_TARGETS[i % 4]!,
          value: 50,
        });
        await vi.runAllTimersAsync();
        const res = await p;
        expect(hasGaugeAttr(res.latest_trace.spans)).toBe(false);
      }

      const tr = await getSessionTraces(s.session_id);
      expect(tr.traces).toHaveLength(5);
      tr.traces.forEach((t) => expect(hasGaugeAttr(t.spans)).toBe(false));

      const cal = executeControlAction({
        session_id: s.session_id,
        stage_id: 1,
        action: "CALIBRATE",
        target: "mainspring-drive",
        value: 75,
      });
      await vi.runAllTimersAsync();
      await cal;

      const eng = executeControlAction({
        session_id: s.session_id,
        stage_id: 1,
        action: "ENGAGE",
        target: "mainspring-drive",
        value: 75,
      });
      await vi.runAllTimersAsync();
      await eng;

      const adv = advanceStage(s.session_id);
      await vi.runAllTimersAsync();
      expect((await adv).state.stage_id).toBe(2);
    } finally {
      vi.useRealTimers();
    }
  });
});
