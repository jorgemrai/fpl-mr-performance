"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { METRIC_LABELS, METRICS, POSITIONS, type Metric, type Player, type Position } from "@/lib/data";
import { fmtMetric, fmtPrice } from "@/lib/format";

type SortKey = "name" | "team" | "pos" | "price" | "pts" | "min" | Metric;
const MAX_COMPARE = 4;

const COLUMNS: { key: SortKey; label: string; num?: boolean }[] = [
  { key: "name", label: "Jugador" },
  { key: "team", label: "Equipo" },
  { key: "pos", label: "Pos" },
  { key: "price", label: "Precio", num: true },
  { key: "pts", label: "Pts", num: true },
  { key: "min", label: "Min", num: true },
  ...METRICS.map((m) => ({ key: m, label: METRIC_LABELS[m], num: true })),
];

function sortValue(p: Player, key: SortKey): string | number | null {
  if (key === "name" || key === "team" || key === "pos") return p[key];
  if (key === "price" || key === "pts" || key === "min") return p[key];
  return p.m[key];
}

export default function PlayerTable({ players }: { players: Player[] }) {
  const teams = useMemo(() => [...new Set(players.map((p) => p.team))].sort(), [players]);
  const [q, setQ] = useState("");
  const [pos, setPos] = useState<Position | "ALL">("ALL");
  const [team, setTeam] = useState("ALL");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "pts", desc: true });
  const [selected, setSelected] = useState<number[]>([]);

  const rows = useMemo(() => {
    const query = q.trim().toLowerCase();
    const lo = minPrice === "" ? -Infinity : Number(minPrice);
    const hi = maxPrice === "" ? Infinity : Number(maxPrice);
    const filtered = players.filter(
      (p) =>
        (pos === "ALL" || p.pos === pos) &&
        (team === "ALL" || p.team === team) &&
        p.price >= lo &&
        p.price <= hi &&
        (!query || p.name.toLowerCase().includes(query) || p.fullName.toLowerCase().includes(query)),
    );
    const dir = sort.desc ? -1 : 1;
    return filtered.sort((a, b) => {
      const va = sortValue(a, sort.key);
      const vb = sortValue(b, sort.key);
      if (va === null) return vb === null ? 0 : 1; // nulls al final
      if (vb === null) return -1;
      return (va < vb ? -1 : va > vb ? 1 : 0) * dir;
    });
  }, [players, q, pos, team, minPrice, maxPrice, sort]);

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, desc: !s.desc } : { key, desc: key !== "name" && key !== "team" && key !== "pos" }));

  const toggleSelected = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length < MAX_COMPARE ? [...s, id] : s));

  const canCompare = selected.length >= 2;

  return (
    <>
      <div className="filters">
        <label className="field">
          Buscar
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nombre" />
        </label>
        <label className="field">
          Posición
          <select value={pos} onChange={(e) => setPos(e.target.value as Position | "ALL")}>
            <option value="ALL">Todas</option>
            {POSITIONS.map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Equipo
          <select value={team} onChange={(e) => setTeam(e.target.value)}>
            <option value="ALL">Todos</option>
            {teams.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="field">
          Precio mín.
          <input type="number" step="0.5" min="3.5" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} />
        </label>
        <label className="field">
          Precio máx.
          <input type="number" step="0.5" min="3.5" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} />
        </label>
        <Link
          className="btn"
          aria-disabled={!canCompare}
          href={`/compare/?ids=${selected.join(",")}`}
        >
          Comparar ({selected.length}/{MAX_COMPARE})
        </Link>
      </div>
      <p className="muted small">
        {rows.length} jugadores. Marca de 2 a {MAX_COMPARE} para compararlos en el radar.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="sel" aria-label="Seleccionar" />
              {COLUMNS.map((c) => (
                <th
                  key={c.key}
                  className={c.num ? "num" : undefined}
                  aria-sort={sort.key === c.key ? (sort.desc ? "descending" : "ascending") : "none"}
                >
                  <button onClick={() => toggleSort(c.key)}>
                    {c.label}
                    {sort.key === c.key ? (sort.desc ? " ▼" : " ▲") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const checked = selected.includes(p.id);
              return (
                <tr key={p.id}>
                  <td className="sel">
                    <input
                      type="checkbox"
                      aria-label={`Comparar ${p.name}`}
                      checked={checked}
                      disabled={!checked && selected.length >= MAX_COMPARE}
                      onChange={() => toggleSelected(p.id)}
                    />
                  </td>
                  <td title={p.fullName}>{p.name}</td>
                  <td>{p.team}</td>
                  <td>{p.pos}</td>
                  <td className="num">{fmtPrice(p.price)}</td>
                  <td className="num">{p.pts}</td>
                  <td className="num">{p.min}</td>
                  {METRICS.map((m) => (
                    <td key={m} className="num">
                      {fmtMetric(m, p.m[m])}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
