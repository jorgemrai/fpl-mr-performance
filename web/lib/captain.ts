// Lógica pura del capitán en el cliente (sin React): se testea con `node --test`.
// Solo imports relativos y `import type` para que funcione con --experimental-strip-types.
import type { Player, Position } from "./data.ts";

/** Candidato en captain.json (compacto). El orden del array es el ranking global (puesto = índice + 1). */
export interface CaptainCandidate {
  i: number; // id
  s: number; // score
  f: [number | null, number]; // forma (30d): [valor, percentil entre candidatos]
  x: [number | null, number]; // xGI/90
  e: [number, number]; // facilidad del rival
  m: [number, string, "H" | "A", number, number][]; // [fixture_id, rival, H/A, dificultad, gw]
  d?: 1; // doble jornada en la GW objetivo
}

/** Descartado en captain.json: motivos (principal primero), news de la FPL y chance_of_playing. */
export interface CaptainDiscard {
  i: number;
  r: string[];
  n?: string;
  c?: number;
}

export const REASON_LABELS: Record<string, string> = {
  portero: "Portero",
  "lesión": "Lesión",
  duda: "Duda",
  "sanción": "Sanción",
  "no disponible": "No disponible",
  "pocos minutos": "Pocos minutos",
  "sin partido": "Sin partido",
};

const STATUS_REASONS = new Set(["lesión", "duda", "sanción", "no disponible"]);

/** Contexto del motivo principal: news de la FPL, % de probabilidad o % de minutos. */
export function discardDetail(d: CaptainDiscard, player?: Pick<Player, "m"> | null): string | null {
  const main = d.r[0];
  if (STATUS_REASONS.has(main) && d.n) return d.n;
  if (main === "duda" && d.c != null) return `${d.c}% de jugar`;
  if (main === "pocos minutos" && player?.m.min_pct != null) return `${Math.round(player.m.min_pct)}% de minutos`;
  return null;
}

export interface PlayerLite {
  id: number;
  name: string;
  team: string;
  pos: Position;
  pts: number;
}
