"use client";

import { useMemo, useState } from "react";
import type { SliceRow } from "@/lib/report";

type Col = {
  key: keyof SliceRow;
  label: string;
  hint: string;
  num?: boolean;
};

const COLS: Col[] = [
  { key: "weather", label: "Weather", hint: "driving conditions" },
  { key: "time_of_day", label: "Time", hint: "day or night" },
  { key: "category", label: "Object type", hint: "what was labeled" },
  { key: "total_annotations", label: "Labels", hint: "annotations in this slice", num: true },
  { key: "ghost_labels_count", label: "Phantoms", hint: "labels with zero lidar points", num: true },
  { key: "kinematic_outliers_count", label: "Teleports", hint: "impossible motion", num: true },
  { key: "avg_lidar_points", label: "Avg points", hint: "lidar hits per box", num: true },
  { key: "failure_rate_pct", label: "% broken", hint: "share flagged as bad", num: true },
];

function heat(pct: number) {
  // transparent cyan → amber → red ramp
  const t = Math.min(pct / 40, 1);
  return {
    background: `rgba(${t > 0.5 ? "248,113,113" : "251,191,36"}, ${0.08 + t * 0.3})`,
    color: t > 0.5 ? "var(--bad)" : t > 0.15 ? "var(--warn)" : "var(--fg)",
  };
}

export function SliceTable({ rows }: { rows: SliceRow[] }) {
  const [sortKey, setSortKey] = useState<keyof SliceRow>("failure_rate_pct");
  const [desc, setDesc] = useState(true);
  const [q, setQ] = useState("");

  const sorted = useMemo(() => {
    const filtered = q
      ? rows.filter((r) =>
          `${r.weather} ${r.time_of_day} ${r.category}`
            .toLowerCase()
            .includes(q.toLowerCase()),
        )
      : rows;
    return [...filtered].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      const cmp =
        typeof av === "number" && typeof bv === "number"
          ? av - bv
          : String(av).localeCompare(String(bv));
      return desc ? -cmp : cmp;
    });
  }, [rows, sortKey, desc, q]);

  return (
    <>
      <div className="table-tools">
        <input
          placeholder="Filter — try 'night' or 'pedestrian'"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <span className="kbd">{sorted.length} rows · click a column to sort</span>
      </div>
      <table>
        <thead>
          <tr>
            {COLS.map((c) => (
              <th
                key={c.key}
                title={c.hint}
                onClick={() => {
                  if (sortKey === c.key) setDesc(!desc);
                  else {
                    setSortKey(c.key);
                    setDesc(true);
                  }
                }}
              >
                {c.label}
                {sortKey === c.key && <span className="arrow"> {desc ? "↓" : "↑"}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={i}>
              <td>{r.weather}</td>
              <td>{r.time_of_day}</td>
              <td>{r.category}</td>
              <td className="num">{r.total_annotations}</td>
              <td className="num">{r.ghost_labels_count}</td>
              <td className="num">{r.kinematic_outliers_count}</td>
              <td className="num">{r.avg_lidar_points}</td>
              <td className="num pct-cell" style={heat(r.failure_rate_pct)}>
                {r.failure_rate_pct}%
              </td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={8} style={{ color: "var(--dim)" }}>
                Nothing matches that filter.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </>
  );
}
