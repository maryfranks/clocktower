import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { mockAction, mockCreateSession } from "@/api/mockStage1";
import { stripGaugeAttributes } from "@/api/clocktowerClient";
import { Console } from "@/components/tower/Console";
import { ChamberView, TraceView } from "@/components/tower/Crt";
import { FieldManual } from "@/components/tower/FieldManual";
import { Gauge } from "@/components/tower/Gauge";
import type { SubsystemTarget } from "@/api/types";

describe("UI Components", () => {
  it("Gauge renders accessible meter role and clamps angle", () => {
    render(<Gauge label="MAINS TENSION" value={74.6} wobble={2} />);
    const meter = screen.getByRole("meter", { name: "MAINS TENSION" });
    expect(meter).toHaveAttribute("aria-valuemin", "0");
    expect(meter).toHaveAttribute("aria-valuemax", "100");
    expect(meter).toHaveAttribute("aria-valuenow", "75");
  });

  it("ChamberView and TraceView display targets, logs, spans, and omit gauge.* attributes", () => {
    const s = mockCreateSession();
    const act1 = mockAction({
      session_id: s.session_id,
      stage_id: 1,
      action: "PROBE",
      target: "escapement-gear",
      value: 50,
    });
    const act2 = mockAction({
      session_id: s.session_id,
      stage_id: 1,
      action: "CALIBRATE",
      target: "escapement-gear",
      value: 50,
    });

    const { rerender } = render(
      <ChamberView
        state={act1.state}
        warm={new Set<SubsystemTarget>(["escapement-gear"])}
        busy={true}
      />,
    );
    expect(screen.getByText("SIGNAL IN FLIGHT…")).toBeInTheDocument();
    expect(screen.getByText("WARM")).toBeInTheDocument();
    expect(screen.getAllByText("COLD")).toHaveLength(3);

    rerender(<TraceView traces={[]} />);
    expect(screen.getByText(/TRACE TAPE EMPTY/i)).toBeInTheDocument();

    const traces = [
      stripGaugeAttributes(act2.latest_trace),
      stripGaugeAttributes(act1.latest_trace),
    ];
    rerender(<TraceView traces={traces} />);
    expect(screen.getByText(/LATEST CALIBRATE/i)).toBeInTheDocument();
    expect(screen.getByText(/T-1 PROBE/i)).toBeInTheDocument();

    const rootSpanBtn = screen.getByRole("button", {
      name: /SWITCHBOARD-ROOM POST \/API\/ACTION/i,
    });
    expect(rootSpanBtn).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(rootSpanBtn);
    expect(rootSpanBtn).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("HTTP.ROUTE")).toBeInTheDocument();
    expect(screen.queryByText(/GAUGE\./i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /T-1 PROBE/i }));
    expect(screen.getByText(/PROBE → ESCAPEMENT-GEAR/i)).toBeInTheDocument();
  });

  it("Console toggles CRT mode and fires target, value, and action callbacks", () => {
    const s = mockCreateSession();
    const onTarget = vi.fn();
    const onValue = vi.fn();
    const onAction = vi.fn();

    const { rerender } = render(
      <Console
        state={s.state}
        gauges={s.gauges}
        traces={[]}
        warm={new Set()}
        busy={false}
        target="mainspring-drive"
        value={50}
        calibrated={false}
        onTarget={onTarget}
        onValue={onValue}
        onAction={onAction}
      />,
    );

    const modeSwitch = screen.getByRole("switch", { name: /Screen mode: trace view/i });
    expect(modeSwitch).toHaveAttribute("aria-checked", "false");
    fireEvent.click(modeSwitch);
    expect(modeSwitch).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText(/TRACE TAPE EMPTY/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Previous target" }));
    expect(onTarget).toHaveBeenCalledWith(-1);
    fireEvent.click(screen.getByRole("button", { name: "Next target" }));
    expect(onTarget).toHaveBeenCalledWith(1);

    fireEvent.change(screen.getByLabelText("Setting lever"), { target: { value: "75" } });
    expect(onValue).toHaveBeenCalledWith(75);

    fireEvent.click(screen.getByRole("button", { name: "PROBE" }));
    expect(onAction).toHaveBeenCalledWith("PROBE");

    rerender(
      <Console
        state={{ ...s.state, stage_completed: true }}
        gauges={s.gauges}
        traces={[]}
        warm={new Set()}
        busy={true}
        target="mainspring-drive"
        value={75}
        calibrated={true}
        onTarget={onTarget}
        onValue={onValue}
        onAction={onAction}
      />,
    );
    expect(screen.getByText("RUNNING")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "PROBE" })).toBeDisabled();
    expect(screen.getByLabelText("Setting lever")).toBeDisabled();
  });

  it("FieldManual switches tabs, reveals hints, and handles stage completion & advance", () => {
    const s = mockCreateSession();
    const onTab = vi.fn();
    const onNextStage = vi.fn();

    const { rerender } = render(
      <FieldManual
        manual={s.state.manual}
        tab="how"
        onTab={onTab}
        completed={false}
        stageId={1}
        onNextStage={onNextStage}
        advancing={false}
      />,
    );

    expect(screen.getByText(s.state.manual.how_to_play[0]!)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "STAGE HINTS" })[0]!);
    expect(onTab).toHaveBeenCalledWith("hints");

    rerender(
      <FieldManual
        manual={s.state.manual}
        tab="hints"
        onTab={onTab}
        completed={false}
        stageId={1}
        onNextStage={onNextStage}
        advancing={false}
      />,
    );
    expect(screen.getByText("Reveal hint 1")).toBeInTheDocument();

    rerender(
      <FieldManual
        manual={s.state.manual}
        tab="parallel"
        onTab={onTab}
        completed={false}
        stageId={1}
        onNextStage={onNextStage}
        advancing={false}
      />,
    );
    expect(screen.getByText("Finish the stage to read the closing note.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "NEXT STAGE" })).not.toBeInTheDocument();

    rerender(
      <FieldManual
        manual={s.state.manual}
        tab="parallel"
        onTab={onTab}
        completed={true}
        stageId={1}
        onNextStage={onNextStage}
        advancing={false}
      />,
    );
    expect(screen.getByText("STAGE LOGGED COMPLETE")).toBeInTheDocument();
    const nextBtn = screen.getByRole("button", { name: "NEXT STAGE" });
    fireEvent.click(nextBtn);
    expect(onNextStage).toHaveBeenCalledOnce();

    rerender(
      <FieldManual
        manual={s.state.manual}
        tab="parallel"
        onTab={onTab}
        completed={true}
        stageId={5}
        onNextStage={onNextStage}
        advancing={false}
      />,
    );
    expect(screen.queryByRole("button", { name: "NEXT STAGE" })).not.toBeInTheDocument();
  });
});
