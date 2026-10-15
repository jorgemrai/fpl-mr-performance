"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { RivalChips, StatusBadge } from "@/components/Badges";
import {
  METRIC_LABELS,
  OWNERSHIP_HINT,
  POSITIONS,
  type Meta,
  type Metric,
  type Player,
  type Position,
} from "@/lib/data";
import { fmtDefconFreq, fmtDelta, fmtMetric, fmtPrice, pctTitle } from "@/lib/format";

type SortKey = "name" | "team" | "pos" | "status" | "price" | "pts" | "min" | Metric;
const MAX_COMPARE = 4;
const STATUS_ORDER: Record<string, number> = { a: 0, d: 1, s: 2, i: 3, n: 4, u: 5 };

const METRIC_COLUMNS: Metric[] = ["ppm", "pts90", "xgi90", "min_pct", "bps90", "form", "defcon90"];

function sortValue(p: Player, key: SortKey): string | number | null {
  switch (key) {
    case "name":
    case "team":
    case "pos":
    case "price":
    case "pts":
    case "min":
      return p[key];
    case "status":
      return -(STATUS_ORDER[p.status] ?? 9); // desc = disponibles primero
    case "ict":
      return p.ictRank === null ? null : -p.ictRank; // desc = #1 primero
    default:
      return p.m[key];
  }
}

export default function PlayerTable({ players, meta }: { players: Player[]; meta: Meta | null }) {
  const teams = useMemo(() => [...new Set(players.map((p) => p.team))].sort(), [players]);
  const [q, setQ] = useState("");
  const [pos, setPos] = useState<Position | "ALL">("ALL");
  const [team, setTeam] = useState("ALL");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [showUnavailable, setShowUnavailable] = useState(false);
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "pts", desc: true });
  const [selected, setSelected] = useState<number[]>([]);
  const small = meta?.smallGroup ?? 30;
  const hasDelta = meta?.prevSnapshotGw != null;

  const rows = useMemo(() => {
    const query = q.trim().toLowerCase();
    const lo = minPrice === "" ? -Infinity : Number(minPrice);
    const hi = maxPrice === "" ? Infinity : Number(maxPrice);
    const filtered = players.filter(
      (p) =>
        (showUnavailable || p.status !== "u") &&
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
  }, [players, q, pos, team, minPrice, maxPrice, showUnavailable, sort]);

  const toggleSort = (key: SortKey) =>
    setSort((s) => (s.key === key ? { key, desc: !s.desc } : { key, desc: key !== "name" && key !== "team" && key !== "pos" }));

  const toggleSelected = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length < MAX_COMPARE ? [...s, id] : s));

  const canCompare = selected.length >= 2;

  const Th = ({ k, label, num, title, className }: { k: SortKey; label: string; num?: boolean; title?: string; className?: string }) => (
    <th
      className={[num ? "num" : "", className ?? ""].join(" ").trim() || undefined}
      aria-sort={sort.key === k ? (sort.desc ? "descending" : "ascending") : "none"}
      title={title}
    >
      <button onClick={() => toggleSort(k)}>
        {label}
        {sort.key === k ? (sort.desc ? " ▼" : " ▲") : ""}
      </button>
    </th>
  );

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
        <label className="check">
          <input type="checkbox" checked={showUnavailable} onChange={(e) => setShowUnavailable(e.target.checked)} />
          Mostrar no disponibles
        </label>
        <Link className="btn" aria-disabled={!canCompare} href={`/compare/?ids=${selected.join(",")}`}>
          Comparar ({selected.length}/{MAX_COMPARE})
        </Link>
      </div>
      <p className="muted small">
        {rows.length} jugadores. Marca de 2 a {MAX_COMPARE} para compararlos en el radar. Pasa el ratón por una métrica
        para ver su percentil y el tamaño del grupo (n).
      </p>
      <div className="table-wrap">
        <table className="players">
          <thead>
            <tr>
              <Th k="name" label="Jugador" className="sticky" />
              <Th k="team" label="Equipo" />
              <Th k="pos" label="Pos" />
              <Th k="status" label="Estado" />
              <Th k="price" label="Precio" num />
              <Th k="pts" label="Pts" num />
              <Th k="min" label="Min" num />
              {METRIC_COLUMNS.map((m) => (
                <Th key={m} k={m} label={METRIC_LABELS[m]} num />
              ))}
              <Th k="defcon_freq" label="Frec. DefCon" num title="Partidos con DefCon ≥ umbral / partidos de titular (aprox., tope 100%)" />
              <Th k="own" label="Ownership" num title={OWNERSHIP_HINT} />
              <Th k="ict" label="ICT" num title="Puesto por ICT dentro de su posición (grupo con minutos suficientes)" />
              <Th k="ease" label="Rival (próx. 3)" title="Dificultad oficial FPL: 1 fácil – 5 difícil. Ordena por facilidad media" />
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const checked = selected.includes(p.id);
              return (
                <tr key={p.id}>
                  <td className="sticky">
                    <label className="name-cell" title={p.fullName}>
                      <input
                        type="checkbox"
                        aria-label={`Comparar ${p.name}`}
                        checked={checked}
                        disabled={!checked && selected.length >= MAX_COMPARE}
                        onChange={() => toggleSelected(p.id)}
                      />
                      {p.name}
                    </label>
                  </td>
                  <td>{p.team}</td>
                  <td>{p.pos}</td>
                  <td>
                    <StatusBadge p={p} />
                  </td>
                  <td className="num">{fmtPrice(p.price)}</td>
                  <td className="num">{p.pts}</td>
                  <td className="num">{p.min}</td>
                  {METRIC_COLUMNS.map((m) => (
                    <td key={m} className="num" title={pctTitle(p, m, small)}>
                      {fmtMetric(m, p.m[m])}
                    </td>
                  ))}
                  <td className="num" title={pctTitle(p, "defcon_freq", small)}>
                    {fmtDefconFreq(p)}
                  </td>
                  <td className="num" title={pctTitle(p, "own", small)}>
                    {fmtMetric("own", p.m.own)}
                    {hasDelta && p.ownDelta != null && <span className="muted small"> ({fmtDelta(p.ownDelta)})</span>}
                  </td>
                  <td className="num" title={pctTitle(p, "ict", small)}>
                    {p.ictRank !== null ? `#${p.ictRank} de ${p.n}` : "—"}
                  </td>
                  <td title={pctTitle(p, "ease", small)}>
                    <RivalChips p={p} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
