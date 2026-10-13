"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Report } from "@/lib/report";

const GRID = "#232b3d";
const DIM = "#8b94a7";
const ACCENT = "#22d3ee";
const BAD = "#f87171";

const tipStyle = {
  backgroundColor: "#1a2030",
  border: "1px solid #232b3d",
  borderRadius: 8,
  fontSize: 13,
} as const;

function shortCategory(c: string) {
  return c.split(".").pop() ?? c;
}

export function Charts({ charts }: { charts: Report["charts"] }) {
  const cats = charts.categories
    .filter((c) => c.flagged > 0)
    .slice(0, 10)
    .map((c) => ({ ...c, name: shortCategory(c.category) }));
  const scenes = charts.scenes.map((s) => ({
    ...s,
    fail_pct: s.total ? +((100 * s.flagged) / s.total).toFixed(1) : 0,
  }));

  return (
    <div className="charts">
      <div className="chart-card">
        <h3>How bad are the problems?</h3>
        <div className="sub">
          Annotations by severity — 0 means fine, closer to 1 means definitely broken
        </div>
        <ResponsiveContainer width="100%" height={190}>
          <BarChart data={charts.severity_hist}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="bucket" stroke={DIM} fontSize={11} tickLine={false} />
            <YAxis stroke={DIM} fontSize={11} tickLine={false} width={44} />
            <Tooltip contentStyle={tipStyle} cursor={{ fill: "rgba(96,165,250,0.08)" }} />
            <Bar dataKey="n" name="annotations" radius={[4, 4, 0, 0]}>
              {charts.severity_hist.map((b) => (
                <Cell key={b.bucket} fill={b.bucket >= 0.5 ? BAD : b.bucket >= 0.3 ? "#fbbf24" : ACCENT} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h3>What kind of objects are mislabeled?</h3>
        <div className="sub">Flagged annotations per category</div>
        <ResponsiveContainer width="100%" height={190}>
          <BarChart data={cats} layout="vertical">
            <CartesianGrid stroke={GRID} horizontal={false} />
            <XAxis type="number" stroke={DIM} fontSize={11} tickLine={false} />
            <YAxis
              type="category"
              dataKey="name"
              stroke={DIM}
              fontSize={11}
              tickLine={false}
              width={88}
            />
            <Tooltip contentStyle={tipStyle} cursor={{ fill: "rgba(96,165,250,0.08)" }} />
            <Bar dataKey="flagged" name="flagged" fill={BAD} radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h3>Which scenes are the messiest?</h3>
        <div className="sub">% of annotations flagged, per scene</div>
        <ResponsiveContainer width="100%" height={190}>
          <BarChart data={scenes}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="name" stroke={DIM} fontSize={10} tickLine={false} interval="preserveStartEnd" />
            <YAxis stroke={DIM} fontSize={11} tickLine={false} width={38} unit="%" />
            <Tooltip
              contentStyle={tipStyle}
              cursor={{ fill: "rgba(96,165,250,0.08)" }}
              formatter={(v) => [`${v}%`, "flagged"]}
            />
            <Bar dataKey="fail_pct" name="flagged" radius={[4, 4, 0, 0]}>
              {scenes.map((s) => (
                <Cell key={s.name} fill={s.fail_pct >= 15 ? BAD : s.fail_pct >= 5 ? "#fbbf24" : ACCENT} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
