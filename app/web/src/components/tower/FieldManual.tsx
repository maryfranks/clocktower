import type { FieldManualContent } from "@/api/types";
import { Button } from "@/components/ui/button";

export type ManualTab = "how" | "hints" | "parallel";
const TABS: { id: ManualTab; label: string }[] = [
  { id: "how", label: "How to Play" }, { id: "hints", label: "Stage Hints" }, { id: "parallel", label: "Real-World Parallel" },
];

export function FieldManual({ manual, tab, onTab, completed, stageId, onNextStage, advancing }: { manual: FieldManualContent; tab: ManualTab; onTab: (t: ManualTab) => void; completed: boolean; stageId: number; onNextStage: () => void; advancing: boolean }) {
  return (
    <section aria-label="Engineer's Field Manual" className="relative flex h-full font-serif">
      <div className="binder-spine flex w-7 shrink-0 flex-col items-center justify-around rounded-l-sm py-8">
        {[0, 1, 2, 3].map((i) => <span key={i} className="binder-ring" />)}
      </div>
      <div className="parchment relative flex min-w-0 flex-1 flex-col rounded-r-sm">
        <div className="absolute -right-[2px] top-10 flex translate-x-full flex-col gap-1 max-md:hidden">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => onTab(t.id)}
              className={`rounded-r-sm px-2 py-3 font-mono text-[10px] tracking-[0.08em] [writing-mode:vertical-rl] ${tab === t.id ? "bg-paper-400 text-ink-950" : "bg-paper-700 text-ink-700 hover:bg-paper-600"}`}>
              {t.label.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="flex gap-1 border-b border-paper-700 px-4 pt-3 md:hidden">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => onTab(t.id)} className={`px-2 py-1.5 font-mono text-[10px] tracking-[0.08em] ${tab === t.id ? "border-b-2 border-teak-700 text-ink-950" : "text-ink-500"}`}>{t.label.toUpperCase()}</button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-6 sm:px-10 sm:py-8">
          <p className="font-mono text-[10px] tracking-[0.14em] text-ink-500">ENGINEER'S FIELD MANUAL · VOL. I</p>
          <h2 className="mt-2 text-3xl font-medium leading-tight tracking-tight text-ink-950">{manual.stage_title}</h2>
          <p className="mt-1 text-lg font-light italic text-ink-500">Scale-to-zero cold starts</p>
          <hr className="my-5 border-paper-800" />
          {completed && (
            <div className="mb-6 border-l-4 bg-paper-300/70 px-4 py-3" style={{ borderColor: "var(--color-phosphor-dim)" }}>
              <p className="font-mono text-[10px] tracking-[0.14em] text-ink-500">STAGE LOGGED COMPLETE</p>
              <p className="mt-1 text-[17px] leading-relaxed">{manual.real_world_parallel.completion_takeaway}</p>
            </div>
          )}
          {tab === "how" && <Ordered items={manual.how_to_play} />}
          {tab === "hints" && <Ordered items={manual.stage_hints} hint />}
          {tab === "parallel" && (
            <div className="max-w-[68ch] space-y-4 text-[17px] leading-[1.7]">
              <h3 className="text-xl font-medium text-ink-950">{manual.real_world_parallel.title}</h3>
              <p>{manual.real_world_parallel.summary}</p>
              {!completed && <p className="text-sm italic text-ink-500">Finish the stage to read the closing note.</p>}
            </div>
          )}
        </div>
        {completed && stageId < 5 && (
          <div className="flex justify-end border-t border-paper-700 px-6 py-3">
            <Button variant="hardware" onClick={onNextStage} disabled={advancing} className="h-11 px-6 font-mono text-xs uppercase tracking-[0.16em]">
              {advancing ? "WINDING…" : "NEXT STAGE"}
            </Button>
          </div>
        )}
        <p className="border-t border-paper-700 px-6 py-2 font-mono text-[10px] tracking-[0.12em] text-ink-500">PRESS ESC TO RETURN TO THE CONSOLE</p>
      </div>
    </section>
  );
}

function Ordered({ items, hint }: { items: string[]; hint?: boolean }) {
  return (
    <ol className="max-w-[68ch] space-y-4 text-[17px] leading-[1.7]">
      {items.map((t, i) => (
        <li key={i} className="flex gap-4">
          <span className="font-mono text-xs tabular-nums text-ink-500 pt-1">{hint ? `H${i + 1}` : `§${i + 1}`}</span>
          {hint ? <details className="group"><summary className="cursor-pointer text-ink-500 group-open:hidden">Reveal hint {i + 1}</summary><span>{t}</span></details> : <span>{t}</span>}
        </li>
      ))}
    </ol>
  );
}
