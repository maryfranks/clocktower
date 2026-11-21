import { describe, expect, it } from "vitest";
import { mockAction, mockCreateSession } from "@/api/mockStage1";
import { SUBSYSTEM_TARGETS } from "@/api/types";

describe("advance_stage", () => {
  it("increments stage_id and resets stage_completed after completion", () => {
    const { session_id } = mockCreateSession();
    const a = (action: "PROBE" | "CALIBRATE" | "ENGAGE", target = SUBSYSTEM_TARGETS[0]!, value = 75) => mockAction({ session_id, stage_id: 1, action, target, value });
    SUBSYSTEM_TARGETS.forEach((t) => a("PROBE", t));
    a("CALIBRATE"); expect(a("ENGAGE").state.stage_completed).toBe(true);
    const r = mockCreateSession(session_id, true);
    expect(r.state.stage_id).toBe(2);
    expect(r.state.stage_completed).toBe(false);
  });
  it("does not advance an unfinished stage", () => {
    const { session_id } = mockCreateSession();
    expect(mockCreateSession(session_id, true).state.stage_id).toBe(1);
  });
});
