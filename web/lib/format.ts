import type { Metric, Player } from "./data";

export function fmtMetric(metric: Metric, v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  switch (metric) {
    case "min_pct":
    case "defcon_freq":
      return `${v.toFixed(0)}%`;
    case "own":
      return `${v.toFixed(1)}%`;
    case "form":
    case "bps90":
    case "ict":
    case "defcon90":
      return v.toFixed(1);
    default:
      return v.toFixed(2);
  }
}

export const fmtPrice = (v: number) => `£${v.toFixed(1)}m`;

/** "3/5 (60%)"; portero o sin datos → "—". */
export function fmtDefconFreq(p: Player): string {
  if (!p.defcon || p.m.defcon_freq === null) return "—";
  return `${p.defcon.hits}/${p.defcon.starts} (${p.m.defcon_freq.toFixed(0)}%)`;
}

export function fmtDelta(d: number | null | undefined): string {
  if (d === null || d === undefined) return "";
  return `${d > 0 ? "+" : ""}${d.toFixed(1)}`;
}

export const STATUS_LABELS: Record<string, string> = {
  a: "Disponible",
  d: "Duda",
  i: "Lesión",
  s: "Sanción",
  u: "No disponible",
  n: "No disponible",
};

/** Tooltip de percentil con el tamaño del grupo y aviso si es pequeño. */
export function pctTitle(p: Player, metric: Metric, small: number): string {
  const pct = p.p?.[metric];
  if (pct === null || pct === undefined) return "Fuera del grupo de percentiles (minutos o estado)";
  const warn = p.n < small ? " · grupo pequeño: percentiles aproximados" : "";
  return `p${pct} dentro de ${p.pos} · n=${p.n}${warn}`;
}
