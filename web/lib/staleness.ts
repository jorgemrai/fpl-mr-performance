import type { Meta } from "./data";

/** GW en curso en `now`: la última cuyo deadline ya pasó (0 antes del primer deadline). */
export function gwAt(deadlines: Meta["deadlines"], now: Date): number {
  return deadlines.reduce((gw, d) => (d.deadline && new Date(d.deadline) <= now && d.gw > gw ? d.gw : gw), 0);
}

/** Datos desactualizados = la GW actual supera en más de 1 a la GW de los datos. */
export function isStale(meta: Meta, now: Date = new Date()): boolean {
  if (!meta.deadlines?.length) return true;
  return gwAt(meta.deadlines, now) - meta.gw > 1;
}
