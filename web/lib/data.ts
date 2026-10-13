"use client";

import { useEffect, useState } from "react";
import { withBase } from "./base";

export const METRICS = ["ppm", "pts90", "xgi90", "min_pct", "bps", "form"] as const;
export type Metric = (typeof METRICS)[number];

export const METRIC_LABELS: Record<Metric, string> = {
  ppm: "PPM",
  pts90: "Pts/90",
  xgi90: "xGI/90",
  min_pct: "% Minutos",
  bps: "BPS",
  form: "Forma (30d)",
};

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
  m: Record<Metric, number | null>;
  /** Percentiles 0-100 dentro de la posición; null si no llega al mínimo de minutos. */
  p: Record<Metric, number | null> | null;
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

export const usePlayers = () => useJson<Player[]>("/data/players.json");
export const useMeta = () => useJson<Meta>("/data/meta.json");
