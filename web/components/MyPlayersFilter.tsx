"use client";

import { useMemo, useState } from "react";
import type { Player } from "@/lib/data";
import { fmtPrice } from "@/lib/format";

/** Buscador de "mis jugadores". Identifica por id (hay nombres repetidos): muestra equipo, posición y precio. */
export default function MyPlayersFilter({
  players,
  selected,
  onChange,
  saveFailed,
}: {
  players: Player[];
  selected: number[];
  onChange: (ids: number[]) => void;
  saveFailed: boolean;
}) {
  const [q, setQ] = useState("");
  const byId = useMemo(() => new Map(players.map((p) => [p.id, p])), [players]);
  const suggestions = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return [];
    return players
      .filter((p) => !selected.includes(p.id) && (p.name.toLowerCase().includes(query) || p.fullName.toLowerCase().includes(query)))
      .slice(0, 8);
  }, [players, q, selected]);

  return (
    <section className="card my-filter" aria-labelledby="my-filter-title">
      <h2 id="my-filter-title">Filtrar por mis jugadores</h2>
      <p className="muted small">
        Elige tus jugadores y el ranking se ordena solo entre ellos, con el mismo score. Tu selección se guarda solo en
        este navegador: no se sube a ningún servidor ni al repositorio.
      </p>
      <label className="field">
        Añadir jugador ({selected.length})
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Busca por nombre, p. ej. Haaland" />
      </label>
      {suggestions.length > 0 && (
        <ul className="suggestions">
          {suggestions.map((p) => (
            <li key={p.id}>
              <button
                onClick={() => {
                  onChange([...selected, p.id]);
                  setQ("");
                }}
              >
                {p.name} <span className="muted small">· {p.team} · {p.pos} · {fmtPrice(p.price)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {selected.length > 0 && (
        <>
          <div className="chips">
            {selected.map((id) => {
              const p = byId.get(id);
              return (
                <span key={id} className="chip">
                  {p ? p.name : `#${id}`} <span className="muted small">{p ? `${p.team} · ${p.pos}` : "sin datos"}</span>
                  <button aria-label={`Quitar ${p?.name ?? id}`} onClick={() => onChange(selected.filter((x) => x !== id))}>
                    ×
                  </button>
                </span>
              );
            })}
          </div>
          <button className="btn btn-ghost" onClick={() => onChange([])}>
            Quitar filtro
          </button>
        </>
      )}
      {saveFailed && (
        <p className="small warn">Este navegador no permite guardar: tu selección se perderá al recargar.</p>
      )}
    </section>
  );
}
