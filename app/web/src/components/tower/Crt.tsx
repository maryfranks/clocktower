import { useState } from "react";
import type { GaugeReadings, StageState, SubsystemTarget, TraceWaterfall } from "@/api/types";
import { Button } from "@/components/ui/button";

export function ChamberView({
  state,
  warm,
  busy,
}: {
  state: StageState;
  warm: Set<SubsystemTarget>;
  busy: boolean;
}) {
  return (
    <div className="flex h-full flex-col gap-3 text-[11px] leading-relaxed">
      <div className="flex justify-between border-b border-phosphor-dim/50 pb-1">
        <span>CHAMBER // {state.manual.stage_title.split("—")[0]?.trim().toUpperCase()}</span>
        <span>
          {state.stage_completed ? "TOWER RUNNING" : busy ? "SIGNAL IN FLIGHT…" : "STANDING BY"}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {state.targets.map((t) => (
          <div
            key={t}
            className={`flex justify-between ${t === state.selected_target ? "bg-phosphor-dim/25" : ""} px-1`}
          >
            <span>
              {t === state.selected_target ? "▶ " : "  "}
              {t.toUpperCase()}
            </span>
            <span className={warm.has(t) ? "" : "opacity-60"}>{warm.has(t) ? "WARM" : "COLD"}</span>
          </div>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto border-t border-phosphor-dim/50 pt-1">
        {[...state.chamber_logs].reverse().map((l, i) => (
          <div key={i} className={i === 0 ? "" : "opacity-70"}>{`> ${l}`}</div>
        ))}
        {busy && <div className="animate-pulse">{"> _"}</div>}
      </div>
    </div>
  );
}

export function TraceView({ traces }: { traces: TraceWaterfall[] }) {
  const [sel, setSel] = useState(0);
  const [open, setOpen] = useState<string | null>(null);
  const tr = traces[Math.min(sel, traces.length - 1)];
  if (!tr) return <div className="text-[11px]">TRACE TAPE EMPTY. NO SIGNALS RECORDED.</div>;
  const depth = (id: string | null): number => {
    const s = tr.spans.find((x) => x.span_id === id);
    return s ? 1 + depth(s.parent_span_id) : 0;
  };
  return (
    <div className="flex h-full flex-col gap-2 text-[11px]">
      <div className="flex flex-wrap gap-1">
        {traces.map((t, i) => (
          <Button
            variant="instrument"
            key={t.trace_id}
            onClick={() => {
              setSel(i);
              setOpen(null);
            }}
            className={`h-auto whitespace-normal rounded-none border px-1.5 py-0.5 text-[10px] ${i === sel ? "border-phosphor bg-phosphor-dim/30" : "border-phosphor-dim/60"} ${t.status === "ERROR" ? "underline decoration-dotted" : ""}`}
          >
            {i === 0 ? "LATEST" : `T-${i}`} {t.action} {t.total_duration_ms}MS
          </Button>
        ))}
      </div>
      <div className="flex justify-between border-b border-phosphor-dim/50 pb-1">
        <span>
          {tr.action} → {tr.target.toUpperCase()}
        </span>
        <span>
          {tr.status} · {tr.total_duration_ms}MS
        </span>
      </div>
      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto">
        {tr.spans.map((s) => {
          const d = depth(s.parent_span_id);
          const total = Math.max(1, tr.total_duration_ms);
          const left = Math.min(100, Math.max(0, (s.start_offset_ms / total) * 100));
          const width = Math.min(100 - left, Math.max(0.8, (s.duration_ms / total) * 100));
          const isOpen = open === s.span_id;
          return (
            <div key={s.span_id}>
              <Button
                variant="instrument"
                className="trace-row grid h-auto w-full items-center gap-2 rounded-none p-0 text-left text-[11px] hover:bg-phosphor-dim/20"
                onClick={() => setOpen(isOpen ? null : s.span_id)}
                aria-expanded={isOpen}
              >
                <span className="truncate" style={{ paddingLeft: d * 10 }}>
                  {isOpen ? "▾" : "▸"} {s.service_name.toUpperCase()}{" "}
                  {s.operation_name.toUpperCase()}
                </span>
                <span className="relative h-3 min-w-0 overflow-hidden">
                  <span
                    className={`absolute top-0 h-3 ${s.status === "ERROR" ? "bg-alarm" : "bg-phosphor"}`}
                    style={{ left: `${left}%`, width: `${width}%` }}
                  />
                </span>
                <span className="text-right text-[10px] tabular-nums">{s.duration_ms}MS</span>
              </Button>
              {isOpen && (
                <div className="my-1 ml-4 border-l border-phosphor-dim pl-2">
                  {Object.entries(s.attributes)
                    .filter(([k]) => !k.startsWith("gauge."))
                    .map(([k, v]) => (
                      <div key={k} className="flex flex-wrap gap-2 break-all">
                        <span className="opacity-70">{k.toUpperCase()}</span>
                        <span>= {String(v).toUpperCase()}</span>
                      </div>
                    ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export type { GaugeReadings };
