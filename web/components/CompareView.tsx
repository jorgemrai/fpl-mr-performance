"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import PlayerRadar from "@/components/Radar";
import { METRIC_LABELS, METRICS, useMeta, usePlayers, type Player } from "@/lib/data";
import { fmtMetric, fmtPrice } from "@/lib/format";
import { seriesVar } from "@/lib/theme";

const MAX = 4;

export function parseIds(raw: string | null): number[] {
  const ids = (raw ?? "")
    .split(",")
    .map((s) => Number.parseInt(s, 10))
    .filter((n) => Number.isInteger(n) && n > 0);
  return [...new Set(ids)].slice(0, MAX);
}

export default function CompareView() {
  const { data: players, error } = usePlayers();
  const { data: meta } = useMeta();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [q, setQ] = useState("");

  const byId = useMemo(() => new Map((players ?? []).map((p) => [p.id, p])), [players]);
  const ids = parseIds(params.get("ids"));
  const selected = ids.map((id) => byId.get(id)).filter((p): p is Player => !!p);

  // La URL es la fuente de verdad: ?ids=1,2,3
  const setIds = (next: number[]) => {
    const qs = next.length ? `?ids=${next.join(",")}` : "";
    router.replace(`${pathname}${qs}`, { scroll: false });
  };

  const suggestions = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!players || !query) return [];
    return players
      .filter((p) => !ids.includes(p.id) && (p.name.toLowerCase().includes(query) || p.fullName.toLowerCase().includes(query)))
      .slice(0, 8);
  }, [players, q, ids]);

  if (error) return <p className="alert">No se pudieron cargar los datos ({error}).</p>;
  if (!players) return <p className="muted">Cargando…</p>;

  const plotted = selected.filter((p) => p.p);
  const skipped = selected.filter((p) => !p.p);
  const mixedPositions = new Set(plotted.map((p) => p.pos)).size > 1;

  return (
    <>
      <div className="filters">
        <label className="field" style={{ flex: "1 1 280px" }}>
          Añadir jugador ({selected.length}/{MAX})
          <input
            type="search"
            value={q}
            disabled={selected.length >= MAX}
            onChange={(e) => setQ(e.target.value)}
            placeholder={selected.length >= MAX ? "Máximo 4 jugadores" : "Busca por nombre, p. ej. Haaland"}
          />
          {suggestions.length > 0 && (
            <ul className="suggestions">
              {suggestions.map((p) => (
                <li key={p.id}>
                  <button
                    onClick={() => {
                      setIds([...ids, p.id]);
                      setQ("");
                    }}
                  >
                    {p.name} <span className="muted small">· {p.team} · {p.pos} · {fmtPrice(p.price)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </label>
        {selected.length > 0 && (
          <button className="btn btn-ghost" onClick={() => setIds([])}>
            Limpiar
          </button>
        )}
      </div>

      <div className="chips">
        {selected.map((p, i) => (
          <span key={p.id} className="chip" style={{ "--chip-color": seriesVar(i) } as React.CSSProperties}>
            {p.name} <span className="muted small">{p.team} · {p.pos}</span>
            <button aria-label={`Quitar ${p.name}`} onClick={() => setIds(ids.filter((x) => x !== p.id))}>
              ×
            </button>
          </span>
        ))}
      </div>

      {selected.length < 2 && <p className="muted">Selecciona al menos 2 jugadores para compararlos.</p>}
      {skipped.length > 0 && (
        <p className="alert">
          {skipped.map((p) => p.name).join(", ")}: menos de {meta?.minMinutes ?? 270} minutos, sin percentiles (fuera del
          radar).
        </p>
      )}

      {plotted.length > 0 && (
        <div className="compare-grid">
          <div className="card">
            <PlayerRadar players={plotted} />
            <p className="muted small">
              Ejes = percentil (0-100) dentro de la posición de cada jugador.
              {mixedPositions && " Ojo: comparas posiciones distintas; cada uno se mide contra los de su posición."}
            </p>
          </div>
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>
                    <span style={{ display: "block", padding: "10px 12px" }}>Métrica</span>
                  </th>
                  {selected.map((p) => (
                    <th key={p.id} className="num">
                      <span style={{ display: "block", padding: "10px 12px" }}>{p.name}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Precio</td>
                  {selected.map((p) => (
                    <td key={p.id} className="num">
                      {fmtPrice(p.price)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Puntos</td>
                  {selected.map((p) => (
                    <td key={p.id} className="num">
                      {p.pts}
                    </td>
                  ))}
                </tr>
                {METRICS.map((m) => (
                  <tr key={m}>
                    <td>{METRIC_LABELS[m]}</td>
                    {selected.map((p) => (
                      <td key={p.id} className="num">
                        {fmtMetric(m, p.m[m])}
                        {p.p?.[m] != null && <span className="muted small"> · p{p.p[m]}</span>}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
