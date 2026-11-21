import { useState } from "react";
import type { ControlAction, GaugeReadings, StageState, SubsystemTarget, TraceWaterfall } from "@/api/types";
import { Gauge } from "./Gauge";
import { ChamberView, TraceView } from "./Crt";
import { Button } from "@/components/ui/button";

interface Props {
  state: StageState; gauges: GaugeReadings; traces: TraceWaterfall[]; warm: Set<SubsystemTarget>; busy: boolean;
  target: SubsystemTarget; value: number; calibrated: boolean;
  onTarget: (dir: -1 | 1) => void; onValue: (v: number) => void; onAction: (a: ControlAction) => void;
}

export function Console(p: Props) {
  const [view, setView] = useState<"chamber" | "trace">("chamber");
  return (
    <section aria-label="Clock tower switchboard" className="faceplate aged-console relative flex h-full min-h-0 flex-col rounded-md font-mono uppercase text-ink-100">
      <span className="bolt left-2 top-2" /><span className="bolt right-2 top-2" />
      <span className="bolt bottom-2 left-2" /><span className="bolt bottom-2 right-2" />

      <header className="flex items-center justify-between gap-3">
        <div className="nameplate console-name px-3 py-1 text-[11px] font-semibold">CLOCK TOWER · SWITCHBOARD Nº 1</div>
        <div className="flex items-center gap-2 text-[10px] tracking-[0.12em] text-ink-300">
          <span className={`size-2.5 rounded-full ${p.state.stage_completed ? "bg-phosphor shadow-[0_0_6px_var(--color-phosphor)]" : p.busy ? "bg-warn" : "bg-steel-500"}`} />
          {p.state.stage_completed ? "RUNNING" : "DORMANT"}
        </div>
      </header>

      {/* CRT */}
      <div className="console-screen flex min-h-0 flex-1 gap-3">
        <div className="screen-controls flex shrink-0 items-stretch">
        <div className="mode-switch flex w-12 flex-col items-center justify-center gap-2 text-[9px] text-ink-300">
          <span className={view === "chamber" ? "text-brass-400" : ""}>CHAMBER</span>
          <div className="rocker-housing">
          <Button variant="instrument" role="switch" aria-checked={view === "trace"} aria-label="Screen mode: trace view"
            onClick={() => setView(view === "chamber" ? "trace" : "chamber")}
             className="rocker-slot relative h-16 w-7 rounded-sm p-0">
            <span className={`toggle-handle absolute left-1/2 h-7 w-3 -translate-x-1/2 rounded-sm transition-all duration-150 ${view === "chamber" ? "top-1" : "top-8"}`}><span className="rocker-grip" /></span>
          </Button>
          </div>
          <span className={view === "trace" ? "text-brass-400" : ""}>TRACE</span>
        </div>
        </div>
        <div className="bezel crt-bezel min-w-0 flex-1 rounded-[22px] p-3">
          <div className="crt-glass phosphor h-full p-3 sm:p-4">
            {view === "chamber" ? <ChamberView state={p.state} warm={p.warm} busy={p.busy} /> : <TraceView traces={p.traces} />}
          </div>
        </div>
        <div className="screen-controls flex shrink-0 items-stretch">
        <div className="setting-assembly flex w-14 min-h-0 flex-col items-center gap-1">
          <label htmlFor="setting-lever" className="text-center text-[9px] leading-tight text-ink-300">SETTING</label>
          <span className="phosphor text-[11px] tabular-nums">{String(p.value).padStart(3, "0")}</span>
          <div className="vertical-track relative min-h-0 w-full flex-1">
            <div className="lever-notches pointer-events-none absolute inset-y-3 right-0 w-4" aria-hidden="true">
              {Array.from({ length: 21 }, (_, i) => <span key={i} className={`stamped-notch absolute right-0 ${i % 5 === 0 ? "major-notch" : ""}`} style={{ bottom: `${i * 5}%` }}>{i % 10 === 0 ? i * 5 : ""}</span>)}
            </div>
            <input id="setting-lever" type="range" min={0} max={100} step={5} value={p.value} disabled={p.busy} aria-label="Setting lever" aria-orientation="vertical"
              onChange={(e) => p.onValue(Number(e.target.value))} className="vertical-lever absolute inset-y-3 left-1" />
          </div>
        </div>
        </div>
      </div>

      {/* Gauges */}
      <div className="recess gauge-deck flex shrink-0 items-start justify-around gap-2 rounded-sm px-1 py-3">
        <Gauge label="MAINS TENSION" value={p.gauges.mains_tension} wobble={p.calibrated ? 0 : 3} />
        <Gauge label="RESONANCE DRAG" value={p.gauges.resonance_drag} wobble={p.busy ? 4 : 0.6} />
        <Gauge label="RESERVE PRESSURE" value={p.gauges.reserve_pressure} />
      </div>

      {/* Control deck */}
      <div className="control-cutout shrink-0">
        <div className="space-y-2">
          <div className="text-center text-[10px] text-ink-300">TARGET SELECTOR</div>
          <div className="selector-assembly">
            <Button variant="hardware" aria-label="Previous target" title="Previous target" onClick={() => p.onTarget(-1)} disabled={p.busy} className="step-switch"><span aria-hidden="true">◀</span><span className="text-[8px]">PREV</span></Button>
            <div className="drum-bezel"><div className="target-drum" aria-live="polite"><span key={p.target} className="drum-lettering">{p.target.toUpperCase()}</span></div></div>
            <Button variant="hardware" aria-label="Next target" title="Next target" onClick={() => p.onTarget(1)} disabled={p.busy} className="step-switch"><span aria-hidden="true">▶</span><span className="text-[8px]">NEXT</span></Button>
          </div>
        </div>

      <div className="action-deck grid shrink-0 grid-cols-4 gap-2">
        {(["PROBE", "CALIBRATE", "RESET", "ENGAGE"] as ControlAction[]).map((a) => (
          <Button variant="hardware" key={a} disabled={p.busy} onClick={() => p.onAction(a)}
            className="h-10 px-1 text-[11px] font-semibold"><span className="rubbed-lettering">{a}</span></Button>
        ))}
      </div>
      </div>
    </section>
  );
}
