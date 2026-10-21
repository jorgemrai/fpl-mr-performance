"use client";

import { useEffect, useMemo, useState } from "react";
import { withBase } from "./base";
import type { CaptainCandidate, CaptainDiscard } from "./captain";

export const METRICS = [
  "ppm",
  "pts90",
  "xgi90",
  "min_pct",
  "bps90",
  "form",
  "ict",
  "defcon90",
  "defcon_freq",
  "ease",
  "own",
] as const;
export type Metric = (typeof METRICS)[number];

export const METRIC_LABELS: Record<Metric, string> = {
  ppm: "PPM",
  pts90: "Pts/90",
  xgi90: "xGI/90",
  min_pct: "% Minutos",
  bps90: "BPS/90",
  form: "Forma (30d)",
  ict: "ICT",
  defcon90: "DefCon/90",
  defcon_freq: "Frec. DefCon",
  ease: "Rival (próx. 3)",
  own: "Ownership",
};

/** Métricas que no aplican a porteros (se ocultan del radar si hay uno seleccionado). */
export const DEFCON_METRICS: readonly Metric[] = ["defcon90", "defcon_freq"];
export const OWNERSHIP_HINT = "Alto = más popular, no necesariamente mejor";

export const POSITIONS = ["GKP", "DEF", "MID", "FWD"] as const;
export type Position = (typeof POSITIONS)[number];

export interface Player {
  id: number;
  name: string;
  fullName: string;
  team: string;
  pos: Position;
  price: number;
  pts: number;
  min: number;
  status: string;
  news: string | null;
  /** Probabilidad de jugar (next_round si hay próxima GW, si no this_round). null = sin alerta. */
  chance: number | null;
  m: Record<Metric, number | null>;
  /** Percentiles 0-100 dentro del grupo (posición, no "u", minutos ≥ umbral); null fuera del grupo. */
  p: Record<Metric, number | null> | null;
  /** Tamaño del grupo de su posición. */
  n: number;
  ictRank: number | null;
  defcon: { hits: number; starts: number } | null;
  next: { gw: number; opp: string; home: boolean; d: number }[];
  /** Solo existe si hay un snapshot anterior. Puntos porcentuales. */
  ownDelta?: number | null;
  form3?: number | null;
}

export interface Meta {
  gw: number;
  gwsFinished: number;
  minMinutes: number;
  players: number;
  hasHistory: boolean;
  dataFetchedAt: string;
  generatedAt: string;
  deadlines: { gw: number; deadline: string | null }[];
  groupN: Partial<Record<Position, number>>;
  smallGroup: number;
  rivalGws: number;
  nextGw: number | null;
  prevSnapshotGw: number | null;
  defconThresholds: Partial<Record<Position, number>>;
  radar: { default: Metric[]; optional: Metric[]; max: number };
}

export interface CaptainFixture {
  gw: number;
  opp: string;
  home: boolean;
  difficulty: number;
}

export interface CaptainPick {
  rank: number;
  id: number;
  name: string;
  team: string;
  pos: Position;
  price: number;
  role: "C" | "V" | null;
  score: number;
  form: number | null;
  xgi90: number | null;
  fdr: number;
  ease: number;
  dgw: boolean;
  fixtures: CaptainFixture[];
  pct: { form: number; xgi90: number; ease: number };
}

export interface Captain {
  gw: number | null;
  deadline: string | null;
  horizonGws: number;
  weights: { form: number; xgi90: number; ease: number };
  minMinutesPct: number;
  minChanceOfPlaying: number;
  /** Todos los candidatos, en orden global (puesto = índice + 1). */
  candidates: CaptainCandidate[];
  excluded: number;
  top: CaptainPick[];
  discarded: CaptainDiscard[];
  discardedByReason: Record<string, number>;
}

type State<T> = { data: T | null; error: string | null };

function useJson<T>(path: string): State<T> {
  const [state, setState] = useState<State<T>>({ data: null, error: null });
  useEffect(() => {
    let alive = true;
    fetch(withBase(path))
      .then((r) => {
        if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
        return r.json() as Promise<T>;
      })
      .then((data) => alive && setState({ data, error: null }))
      .catch((e: Error) => alive && setState({ data: null, error: e.message }));
    return () => {
      alive = false;
    };
  }, [path]);
  return state;
}

/** Defaults para JSON generados con un esquema anterior (hasta que update.yml los regenere). */
function normalizePlayer(p: Partial<Player> & Pick<Player, "id" | "name">): Player {
  return {
    fullName: p.name,
    team: "",
    pos: "MID",
    price: 0,
    pts: 0,
    min: 0,
    status: "a",
    news: null,
    chance: null,
    p: null,
    n: 0,
    ictRank: null,
    defcon: null,
    next: [],
    ...p,
    m: { ...(Object.fromEntries(METRICS.map((m) => [m, null])) as Record<Metric, number | null>), ...(p.m ?? {}) },
  } as Player;
}

export function usePlayers(): State<Player[]> {
  const { data, error } = useJson<Player[]>("/data/players.json");
  const normalized = useMemo(() => data?.map(normalizePlayer) ?? null, [data]);
  return { data: normalized, error };
}
export const useMeta = () => useJson<Meta>("/data/meta.json");
export const useCaptain = () => useJson<Captain>("/data/captain.json");
