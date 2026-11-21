import { useEffect, useId, useRef, useState } from "react";

const SWEEP = 240; // degrees, from -120 to +120
const toAngle = (v: number) => -SWEEP / 2 + (Math.max(0, Math.min(100, v)) / 100) * SWEEP;

/** Damped spring needle: critically under-damped so it overshoots and settles like a real movement. */
function useSpring(target: number, wobble = 0) {
  const [pos, setPos] = useState(target);
  const st = useRef({ x: target, v: 0, target });
  st.current.target = target;
  useEffect(() => {
    let raf = 0,
      last = performance.now();
    const k = 90,
      c = 9;
    const step = (now: number) => {
      const dt = Math.min(0.033, (now - last) / 1000);
      last = now;
      const s = st.current;
      const goal =
        s.target + (wobble ? Math.sin(now / 140) * wobble + Math.sin(now / 53) * wobble * 0.4 : 0);
      s.v += (k * (goal - s.x) - c * s.v) * dt;
      s.x += s.v * dt;
      setPos(s.x);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [wobble]);
  return pos;
}

export function Gauge({
  label,
  value,
  wobble = 0,
}: {
  label: string;
  value: number;
  wobble?: number;
}) {
  const pos = useSpring(value, wobble);
  const id = useId().replace(/:/g, "");
  const ticks = Array.from({ length: 41 }, (_, i) => i);
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        className="bezel gauge-bezel rounded-full p-[6px]"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(value)}
      >
        <svg viewBox="0 0 120 120" className="gauge-dial block">
          <defs>
            <radialGradient id={`${id}-dialface`} cx="40%" cy="35%">
              <stop offset="0%" stopColor="var(--color-paper-500)" />
              <stop offset="68%" stopColor="var(--color-paper-700)" />
              <stop offset="88%" stopColor="var(--color-paper-800)" />
              <stop offset="100%" stopColor="var(--color-ink-700)" />
            </radialGradient>
            <clipPath id={`${id}-clip`}>
              <circle cx="60" cy="60" r="55" />
            </clipPath>
          </defs>
          <circle cx="60" cy="60" r="56" fill={`url(#${id}-dialface)`} />
          <g clipPath={`url(#${id}-clip)`}>
            {Array.from({ length: 65 }, (_, i) => (
              <ellipse
                key={i}
                cx={(i * 37 + 11) % 117}
                cy={(i * 53 + 9) % 119}
                rx={0.4 + (i % 4) * 0.55}
                ry={0.5 + (i % 3) * 0.4}
                fill="var(--color-foxing)"
                opacity={0.12 + (i % 5) * 0.06}
              />
            ))}
            <path
              d="M16 80 Q35 70 50 78 M78 22 L84 36 M27 30 L31 49 M75 98 Q89 85 95 67"
              fill="none"
              stroke="var(--color-foxing)"
              strokeWidth="0.7"
              opacity="0.4"
            />
          </g>
          <circle
            cx="60"
            cy="60"
            r="56"
            fill="none"
            stroke="var(--color-steel-950)"
            strokeWidth="2"
          />
          {ticks.map((i) => {
            const a = ((-SWEEP / 2 + (i / 40) * SWEEP) * Math.PI) / 180;
            const major = i % 10 === 0,
              mid = i % 5 === 0;
            const r1 = 50,
              r2 = major ? 40 : mid ? 43 : 46;
            return (
              <line
                key={i}
                x1={60 + r1 * Math.sin(a)}
                y1={60 - r1 * Math.cos(a)}
                x2={60 + r2 * Math.sin(a)}
                y2={60 - r2 * Math.cos(a)}
                stroke="var(--color-ink-950)"
                strokeWidth={major ? 1.6 : 0.5 + (i % 3) * 0.2}
                opacity={0.4 + (i % 5) * 0.1}
                strokeDasharray={i % 7 === 0 ? "2 1 3" : undefined}
                strokeLinecap="round"
              />
            );
          })}
          <path
            d={arc(52, 0.8 * SWEEP - SWEEP / 2, SWEEP / 2)}
            stroke="var(--color-ink-500)"
            strokeWidth="3"
            fill="none"
          />
          <g transform={`rotate(${toAngle(pos)} 60 60)`}>
            <path d="M60 14 L62.5 60 L60 70 L57.5 60 Z" fill="var(--color-ink-950)" />
          </g>
          <circle
            cx="60"
            cy="60"
            r="6"
            fill="var(--color-brass-500)"
            stroke="var(--color-brass-900)"
          />
          <ellipse cx="45" cy="35" rx="30" ry="14" fill="var(--color-paper-300)" opacity="0.18" />
        </svg>
      </div>
      <div className="nameplate gauge-name whitespace-nowrap px-1.5 py-1 text-[9px] font-semibold">
        {label}
      </div>
    </div>
  );
}

function arc(r: number, a0: number, a1: number) {
  const p = (a: number) => {
    const t = (a * Math.PI) / 180;
    return `${60 + r * Math.sin(t)} ${60 - r * Math.cos(t)}`;
  };
  return `M ${p(a0)} A ${r} ${r} 0 0 1 ${p(a1)}`;
}
