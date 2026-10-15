"use client";

import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { METRIC_LABELS, type Metric, type Player } from "@/lib/data";
import { SERIES, useCssVars } from "@/lib/theme";

const VARS = [...SERIES, "text", "text-muted", "grid", "bg", "border"] as const;

export default function PlayerRadar({ players, axes }: { players: Player[]; axes: Metric[] }) {
  const c = useCssVars(VARS);
  if (!c) return <div className="radar-box" />;

  // Una fila por eje; una columna por jugador (percentil dentro del grupo de su posición).
  const data = axes.map((m) => ({
    axis: METRIC_LABELS[m],
    ...Object.fromEntries(players.map((p) => [String(p.id), p.p?.[m] ?? 0])),
  }));

  return (
    <div className="radar-box">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="62%">
          <PolarGrid stroke={c.grid} />
          <PolarAngleAxis dataKey="axis" tick={{ fill: c.text, fontSize: 12, fontWeight: 600 }} />
          <PolarRadiusAxis domain={[0, 100]} ticks={[25, 50, 75]} angle={90} tick={{ fill: c["text-muted"], fontSize: 11 }} axisLine={false} />
          {players.map((p, i) => (
            <Radar
              key={p.id}
              name={`${p.name} (${p.pos}, n=${p.n})`}
              dataKey={String(p.id)}
              stroke={c[SERIES[i]]}
              fill={c[SERIES[i]]}
              fillOpacity={0.25}
              strokeWidth={2}
              isAnimationActive={false}
            />
          ))}
          <Tooltip
            contentStyle={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: 8, color: c.text }}
            labelStyle={{ color: c.text, fontWeight: 700 }}
            formatter={(v) => [`p${v}`]}
          />
          {/* Texto de leyenda en color de texto: el rosa no da 4.5:1 sobre morado. */}
          <Legend itemSorter={null} formatter={(value) => <span style={{ color: c.text }}>{value}</span>} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
