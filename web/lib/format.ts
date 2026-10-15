import type { Metric } from "./data";

export function fmtMetric(metric: Metric, v: number | null | undefined): string {
  if (v === null || v === undefined) return "–";
  if (metric === "bps") return String(v);
  if (metric === "min_pct") return `${v.toFixed(0)}%`;
  if (metric === "form") return v.toFixed(1);
  return v.toFixed(2);
}

export const fmtPrice = (v: number) => `£${v.toFixed(1)}m`;
