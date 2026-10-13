"use client";

import { useEffect, useState } from "react";

const R = 56;
const CIRC = 2 * Math.PI * R;

/** Animated health ring: shows (100 - failure %) as an arc, grade letter inside. */
export function Gauge({ failurePct, grade }: { failurePct: number; grade: string }) {
  const score = Math.max(0, Math.min(100, 100 - failurePct));
  const [offset, setOffset] = useState(CIRC);
  useEffect(() => {
    const t = requestAnimationFrame(() => setOffset(CIRC * (1 - score / 100)));
    return () => cancelAnimationFrame(t);
  }, [score]);

  const color =
    grade === "A" || grade === "B"
      ? "var(--good)"
      : grade === "C"
        ? "var(--warn)"
        : "var(--bad)";

  return (
    <div className="gauge" role="img" aria-label={`Dataset health grade ${grade}`}>
      <svg width="132" height="132" viewBox="0 0 132 132">
        <circle className="track" cx="66" cy="66" r={R} fill="none" strokeWidth="11" />
        <circle
          className="val"
          cx="66"
          cy="66"
          r={R}
          fill="none"
          stroke={color}
          strokeWidth="11"
          strokeLinecap="round"
          strokeDasharray={CIRC}
          strokeDashoffset={offset}
        />
      </svg>
      <div className={`letter grade-${grade}`}>{grade}</div>
    </div>
  );
}
