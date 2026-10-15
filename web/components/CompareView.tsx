"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { RivalChips, StatusBadge } from "@/components/Badges";
import PlayerRadar from "@/components/Radar";
import {
  DEFCON_METRICS,
  METRIC_LABELS,
  METRICS,
  OWNERSHIP_HINT,
  useMeta,
  usePlayers,
  type Metric,
  type Player,
} from "@/lib/data";
import { fmtDefconFreq, fmtDelta, fmtMetric, fmtPrice } from "@/lib/format";
import { seriesVar } from "@/lib/theme";

const MAX = 4;
const MIN_AXES = 3;

export function parseIds(raw: string | null): number[] {
  const ids = (raw ?? "")
    .split(",")
    .map((s) => Number.parseInt(s, 10))
    .filter((n) => Number.isInteger(n) && n > 0);
  return [...new Set(ids)].slice(0, MAX);
}

export function parseAxes(raw: string | null, allowed: readonly Metric[], max: number): Metric[] | null {
  if (!raw) return null;
  const axes = [...new Set(raw.split(","))].filter((a): a is Metric => allowed.includes(a as Metric));
  return axes.length >= MIN_AXES ? axes.slice(0, max) : null;
}

function cell(p: Player, m: Metric, hasDelta: boolean) {
  if (m === "defcon_freq") return fmtDefconFreq(p);
  if (m === "own" && hasDelta && p.ownDelta != null) return `${fmtMetric(m, p.m[m])} (${fmtDelta(p.ownDelta)})`;
  return fmtMetric(m, p.m[m]);
}

export default function CompareView() {
  const { data: players, error } = usePlayers();
  const { data: meta } = useMeta();
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [q, setQ] = useState("");

  const radarCfg = meta?.radar ?? { default: ["ppm", "form", "ict", "defcon90", "ease", "own"] as Metric[], optional: [] as Metric[], max: 8 };
  const allowedAxes = useMemo(
    () => [...radarCfg.default, ...radarCfg.optional].filter((m) => METRICS.includes(m)),
    [radarCfg.default, radarCfg.optional],
  );

  const byId = useMemo(() => new Map((players ?? []).map((p) => [p.id, p])), [players]);
  const ids = parseIds(params.get("ids"));
  const axesParam = params.get("axes");
  const axes = parseAxes(axesParam, allowedAxes, radarCfg.max) ?? radarCfg.default;
  const selected = ids.map((id) => byId.get(id)).filter((p): p is Player => !!p);

  // La URL es la fuente de verdad: ?ids=1,2&axes=ppm,form,...
  const setUrl = (nextIds: number[], nextAxes: Metric[]) => {
    const parts = [];
    if (nextIds.length) parts.push(`ids=${nextIds.join(",")}`);
    parts.push(`axes=${nextAxes.join(",")}`);
    router.replace(`${pathname}?${parts.join("&")}`, { scroll: false });
  };

  // Al llegar sin ejes (p. ej. desde la tabla), se escriben los ejes por defecto en la URL.
  useEffect(() => {
    if (meta && !parseAxes(axesParam, allowedAxes, radarCfg.max)) setUrl(ids, radarCfg.default);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta, axesParam]);

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
  const hasGk = selected.some((p) => p.pos === "GKP");
  const shownAxes = hasGk ? axes.filter((m) => !DEFCON_METRICS.includes(m)) : axes;
  const hiddenDefcon = hasGk && shownAxes.length !== axes.length;
  const mixedPositions = new Set(plotted.map((p) => p.pos)).size > 1;
  const small = meta?.smallGroup ?? 30;
  const smallGroups = plotted.filter((p) => p.n < small);
  const hasDelta = meta?.prevSnapshotGw != null;

  const toggleAxis = (m: Metric) => {
    const next = axes.includes(m) ? axes.filter((a) => a !== m) : [...axes, m];
    if (next.length < MIN_AXES || next.length > radarCfg.max) return;
    setUrl(ids, allowedAxes.filter((a) => next.includes(a)));
  };

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
                      setUrl([...ids, p.id], axes);
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
          <button className="btn btn-ghost" onClick={() => setUrl([], axes)}>
            Limpiar
          </button>
        )}
      </div>

      <div className="chips">
        {selected.map((p, i) => (
          <span key={p.id} className="chip" style={{ "--chip-color": seriesVar(i) } as React.CSSProperties}>
            {p.name}{" "}
            <span className="muted small">
              {p.team} · {p.pos} · n={p.n}
            </span>
            <button aria-label={`Quitar ${p.name}`} onClick={() => setUrl(ids.filter((x) => x !== p.id), axes)}>
              ×
            </button>
          </span>
        ))}
      </div>

      <fieldset className="axes">
        <legend>
          Ejes del radar ({axes.length}/{radarCfg.max}, mínimo {MIN_AXES})
          {hiddenDefcon && ` · ${shownAxes.length} visibles (DefCon oculto por portero)`}
        </legend>
        {allowedAxes.map((m) => {
          const on = axes.includes(m);
          const disabled = (on && axes.length <= MIN_AXES) || (!on && axes.length >= radarCfg.max);
          return (
            <label key={m} className={`axis-toggle${on ? " on" : ""}`} title={m === "own" ? OWNERSHIP_HINT : undefined}>
              <input type="checkbox" checked={on} disabled={disabled} onChange={() => toggleAxis(m)} />
              {METRIC_LABELS[m]}
            </label>
          );
        })}
      </fieldset>

      {selected.length < 2 && <p className="muted">Selecciona al menos 2 jugadores para compararlos.</p>}
      {hiddenDefcon && (
        <p className="alert" role="status">
          Hay un portero en la selección: se ocultan los ejes DefCon (no aplican a porteros).
        </p>
      )}
      {skipped.length > 0 && (
        <p className="alert">
          {skipped.map((p) => p.name).join(", ")}: fuera del grupo de percentiles (menos de {meta?.minMinutes ?? 270} minutos o
          no disponible), no aparece en el radar.
        </p>
      )}

      {plotted.length > 0 && (
        <div className="compare-grid">
          <div className="card">
            <PlayerRadar players={plotted} axes={shownAxes} />
            <p className="muted small">
              Ejes = percentil (0-100) dentro de su posición; grupo = jugadores no &quot;no disponibles&quot; con ≥{" "}
              {meta?.minMinutes ?? 270} minutos.{" "}
              {plotted.map((p) => `${p.name}: n=${p.n} (${p.pos})`).join(" · ")}.
              {mixedPositions && " Ojo: comparas posiciones distintas; cada uno se mide contra los de su posición."}
            </p>
            {smallGroups.length > 0 && (
              <p className="small warn">
                Grupo pequeño ({smallGroups.map((p) => `${p.pos} n=${p.n}`).filter((v, i, a) => a.indexOf(v) === i).join(", ")}):
                percentiles aproximados.
              </p>
            )}
            {shownAxes.includes("own") && <p className="muted small">Ownership: {OWNERSHIP_HINT.toLowerCase()}.</p>}
          </div>
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>
                    <span className="th-label">Métrica</span>
                  </th>
                  {selected.map((p) => (
                    <th key={p.id} className="num">
                      <span className="th-label">{p.name}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Estado</td>
                  {selected.map((p) => (
                    <td key={p.id} className="num">
                      <StatusBadge p={p} />
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Precio · Pts</td>
                  {selected.map((p) => (
                    <td key={p.id} className="num">
                      {fmtPrice(p.price)} · {p.pts}
                    </td>
                  ))}
                </tr>
                {shownAxes.map((m) => (
                  <tr key={m}>
                    <td title={m === "own" ? OWNERSHIP_HINT : undefined}>{METRIC_LABELS[m]}</td>
                    {selected.map((p) => (
                      <td key={p.id} className="num">
                        {m === "ease" ? <RivalChips p={p} /> : cell(p, m, hasDelta)}
                        {p.p?.[m] != null && <span className="muted small"> · p{p.p[m]}</span>}
                      </td>
                    ))}
                  </tr>
                ))}
                <tr>
                  <td>n (grupo)</td>
                  {selected.map((p) => (
                    <td key={p.id} className="num">
                      {p.n} {p.pos}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
