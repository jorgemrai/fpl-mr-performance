// "Filtrar por mis jugadores" en /captain: lógica pura, sin React. Se testea con `node --test`.
// No recalcula nada: usa el score y los percentiles de captain.json (calculados contra TODO el
// universo de candidatos), así que el score de un jugador es el mismo con o sin filtro.
import type { CaptainCandidate, CaptainDiscard } from "./captain.ts";

export const STORAGE_KEY = "mrp.captainFilter.v1";
export const MAX_CARDS = 5;

/** Subconjunto de Storage para poder inyectar uno falso en los tests. */
export type KeyValueStore = Pick<Storage, "getItem" | "setItem" | "removeItem">;

/** IDs guardados en este navegador. Cualquier fallo (sin storage, JSON roto, excepción) → []. */
export function loadSelection(store: KeyValueStore | null | undefined): number[] {
  try {
    const raw = store?.getItem(STORAGE_KEY);
    if (!raw) return [];
    return sanitizeIds(JSON.parse(raw));
  } catch {
    return [];
  }
}

/** Guarda la selección; devuelve false si el navegador no deja guardar (la UI sigue en memoria). */
export function saveSelection(store: KeyValueStore | null | undefined, ids: number[]): boolean {
  try {
    if (!store) return false;
    const clean = sanitizeIds(ids);
    if (clean.length === 0) store.removeItem(STORAGE_KEY);
    else store.setItem(STORAGE_KEY, JSON.stringify(clean));
    return true;
  } catch {
    return false;
  }
}

export function sanitizeIds(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  const ids = value.filter((v): v is number => Number.isInteger(v) && v > 0);
  return [...new Set(ids)];
}

export interface CaptainData {
  gw: number | null;
  candidates: CaptainCandidate[];
  discarded: CaptainDiscard[];
}

export interface RankedPick {
  candidate: CaptainCandidate;
  globalRank: number; // 1 = mejor global
  role: "C" | "V" | null;
}

export interface FilteredCaptain {
  ranking: RankedPick[]; // elegibles elegidos, en orden global (todos; la UI muestra MAX_CARDS)
  captainId: number | null;
  viceId: number | null;
  /** Por qué no hay vice (null si lo hay). */
  viceNote: string | null;
  discarded: CaptainDiscard[]; // elegidos que no son candidatos (incluye porteros)
  noData: number[]; // ids elegidos que no existen en los datos de esta GW
  best: { id: number; score: number; rank: number } | null;
  globalBest: { id: number; score: number } | null;
  totalCandidates: number;
}

/** Partidos de la GW objetivo de un candidato (fixture ids). */
export function targetFixtures(c: CaptainCandidate, gw: number | null): number[] {
  return c.m.filter((m) => gw === null || m[4] === gw).map((m) => m[0]);
}

/** Capitán = primero; vice = siguiente que no comparte ningún partido de la GW objetivo. */
export function pickCaptainVice(
  ranked: CaptainCandidate[],
  gw: number | null,
): { captainId: number | null; viceId: number | null; viceNote: string | null } {
  if (ranked.length === 0) return { captainId: null, viceId: null, viceNote: null };
  const [cap, ...rest] = ranked;
  if (rest.length === 0) {
    return { captainId: cap.i, viceId: null, viceNote: "Solo tienes un jugador elegible: no hay vicecapitán." };
  }
  const capFx = new Set(targetFixtures(cap, gw));
  const vice = rest.find((c) => !targetFixtures(c, gw).some((fx) => capFx.has(fx)));
  if (!vice) {
    return {
      captainId: cap.i,
      viceId: null,
      viceNote: "Todos tus otros elegibles juegan el mismo partido que el capitán: no hay vice sin compartir partido.",
    };
  }
  return { captainId: cap.i, viceId: vice.i, viceNote: null };
}

/** Filtra el ranking global por los ids elegidos. Cada id elegido queda en exactamente una lista. */
export function filterCaptain(cap: CaptainData, selected: number[]): FilteredCaptain {
  const ids = sanitizeIds(selected);
  const want = new Set(ids);
  const rankOf = new Map(cap.candidates.map((c, idx) => [c.i, idx + 1]));
  const discardOf = new Map(cap.discarded.map((d) => [d.i, d]));

  const mine = cap.candidates.filter((c) => want.has(c.i)); // ya en orden global
  const { captainId, viceId, viceNote } = pickCaptainVice(mine, cap.gw);
  const ranking: RankedPick[] = mine.map((c) => ({
    candidate: c,
    globalRank: rankOf.get(c.i)!,
    role: c.i === captainId ? "C" : c.i === viceId ? "V" : null,
  }));

  const discarded = ids.filter((id) => !rankOf.has(id) && discardOf.has(id)).map((id) => discardOf.get(id)!);
  const noData = ids.filter((id) => !rankOf.has(id) && !discardOf.has(id));

  const top = cap.candidates[0];
  const first = mine[0];
  return {
    ranking,
    captainId,
    viceId,
    viceNote,
    discarded,
    noData,
    best: first ? { id: first.i, score: first.s, rank: rankOf.get(first.i)! } : null,
    globalBest: top ? { id: top.i, score: top.s } : null,
    totalCandidates: cap.candidates.length,
  };
}

/** Diferencia de score entre el mejor global y tu mejor (≥ 0), con 1 decimal. */
export function scoreGap(f: FilteredCaptain): number | null {
  if (!f.best || !f.globalBest) return null;
  return Math.round((f.globalBest.score - f.best.score) * 10) / 10;
}
