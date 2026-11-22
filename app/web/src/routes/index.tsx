import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import {
  advanceStage,
  createOrResumeSession,
  executeControlAction,
  getSessionTraces,
} from "@/api/clocktowerClient";
import {
  SUBSYSTEM_TARGETS,
  type ControlAction,
  type GaugeReadings,
  type StageState,
  type SubsystemTarget,
  type TraceWaterfall,
} from "@/api/types";
import { Console } from "@/components/tower/Console";
import { FieldManual, type ManualTab } from "@/components/tower/FieldManual";
import { Button } from "@/components/ui/button";
import { mockCreateSession } from "@/api/mockStage1";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "The Clock Tower — An Observability Puzzle" },
      {
        name: "description",
        content:
          "Wake a sleeping clock tower from its switchboard. Read the traces, find the cold gears, set the mainspring.",
      },
      { property: "og:title", content: "The Clock Tower — An Observability Puzzle" },
      {
        property: "og:description",
        content: "A tactile switchboard puzzle about traces, cold starts and patient diagnosis.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

type Panel = "console" | "manual";
const SESSION_KEY = "clocktower.session";

function Index() {
  const [initial] = useState(() => mockCreateSession());
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [state, setState] = useState<StageState>(initial.state);
  const [gauges, setGauges] = useState<GaugeReadings>(initial.gauges);
  const [traces, setTraces] = useState<TraceWaterfall[]>(initial.recent_traces);
  const [target, setTarget] = useState<SubsystemTarget>(initial.state.selected_target);
  const [value, setValue] = useState(initial.state.slider_value);
  const [busy, setBusy] = useState(false);
  const [focus, setFocus] = useState<Panel>("manual");
  const [tab, setTab] = useState<ManualTab>("how");
  const [warm, setWarm] = useState<Set<SubsystemTarget>>(new Set());
  const [calibrated, setCalibrated] = useState(false);

useEffect(() => {
    const saved = sessionStorage.getItem(SESSION_KEY);
    if (!saved) return;
    createOrResumeSession({ session_id: saved }).then((r) => {
      sessionStorage.setItem(SESSION_KEY, r.session_id);
      setSessionId(r.session_id);
      setState(r.state);
      setGauges(r.gauges);
      setTraces(r.recent_traces);
      setTarget(r.state.selected_target);
      setValue(r.state.slider_value);
      setFocus("manual");
      setTab("how"); // stage start
    });
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFocus((f) => (f === "console" ? "manual" : "console"));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const onAction = useCallback(
    async (action: ControlAction) => {
      setBusy(true);
      try {
        let activeSessionId = sessionId;
        if (!activeSessionId) {
          const session = await createOrResumeSession({
            session_id: sessionStorage.getItem(SESSION_KEY),
          });
          sessionStorage.setItem(SESSION_KEY, session.session_id);
          activeSessionId = session.session_id;
          setSessionId(session.session_id);
        }

        const r = await executeControlAction({
          session_id: activeSessionId,
          stage_id: state.stage_id,
          action,
          target,
          value,
        });
        const wasDone = state.stage_completed;
        setState(r.state);
        setGauges(r.gauges);
        const t = await getSessionTraces(activeSessionId);
        setTraces(t.traces);
        if (action === "RESET") {
          setWarm(new Set());
          setCalibrated(false);
          setFocus("manual");
          setTab("how");
        } else {
          const tick = r.latest_trace.spans.find((s) => s.operation_name.startsWith("tick"));
          if (action === "PROBE" && tick?.status === "OK") setWarm((w) => new Set(w).add(target));
          if (action === "CALIBRATE") setCalibrated(r.latest_trace.status === "OK");
        }
        if (!wasDone && r.state.stage_completed) {
          setFocus("manual");
          setTab("parallel");
        }
      } finally {
        setBusy(false);
      }
    },
    [sessionId, state, target, value],
  );

  const [advancing, setAdvancing] = useState(false);
  const onNextStage = useCallback(async () => {
    if (!sessionId) return;
    setAdvancing(true);
    try {
      const r = await advanceStage(sessionId);
      setSessionId(r.session_id);
      setState(r.state);
      setGauges(r.gauges);
      setTraces(r.recent_traces);
      setTarget(r.state.selected_target);
      setValue(r.state.slider_value);
      setWarm(new Set());
      setCalibrated(false);
      setFocus("manual");
      setTab("how");
    } finally {
      setAdvancing(false);
    }
  }, [sessionId]);

  const cycle = (d: -1 | 1) =>
    setTarget((t) => SUBSYSTEM_TARGETS[(SUBSYSTEM_TARGETS.indexOf(t) + d + 4) % 4]!);

  const panelCls = (p: Panel) =>
    `transition-all duration-500 ease-out md:min-w-0 ${
      focus === p
        ? "md:flex-[6] md:opacity-100"
        : "md:flex-[4] md:scale-[0.94] md:opacity-70 md:cursor-zoom-in md:hover:opacity-90 max-md:hidden"
    }`;

  const consoleEl = (
    <Console
      state={state}
      gauges={gauges}
      traces={traces}
      warm={warm}
      busy={busy}
      target={target}
      value={value}
      calibrated={calibrated}
      onTarget={cycle}
      onValue={setValue}
      onAction={onAction}
    />
  );
  const manualEl = (
    <FieldManual
      manual={state.manual}
      tab={tab}
      onTab={setTab}
      completed={state.stage_completed}
      stageId={state.stage_id}
      onNextStage={onNextStage}
      advancing={advancing}
    />
  );

  return (
    <main className="tower-workspace h-dvh overflow-hidden bg-background">
      <h1 className="sr-only">The Clock Tower</h1>
      <div className="workspace-panels mx-auto flex h-full max-w-[1500px] items-stretch gap-6 p-3 pb-16 md:gap-10 md:p-8 md:pb-8">
        {(["console", "manual"] as Panel[]).map((p) => (
          <div
            key={p}
            className={`${panelCls(p)} max-md:w-full ${p === "manual" ? "md:pr-8" : ""}`}
            onClickCapture={(e) => {
              if (focus !== p) {
                e.stopPropagation();
                e.preventDefault();
                setFocus(p);
              }
            }}
            aria-label={
              focus !== p ? `Focus ${p === "console" ? "switchboard" : "field manual"}` : undefined
            }
          >
            <div className={`h-full min-h-0 ${focus !== p ? "md:pointer-events-none" : ""}`}>
              {p === "console" ? consoleEl : manualEl}
            </div>
          </div>
        ))}
      </div>
      {/* Mobile peek bar */}
      <Button
        variant="instrument"
        onClick={() => setFocus(focus === "console" ? "manual" : "console")}
        className={`fixed inset-x-0 bottom-0 z-10 flex h-12 items-center justify-between px-4 md:hidden ${focus === "console" ? "parchment font-serif" : "faceplate font-mono uppercase text-ink-100"}`}
      >
        <span className="text-sm">
          {focus === "console" ? "Engineer's Field Manual" : "SWITCHBOARD"}
        </span>
        <span className="font-mono text-[10px] tracking-[0.14em]">
          {state.stage_completed ? "✓ " : ""}OPEN ▲
        </span>
      </Button>
    </main>
  );
}
