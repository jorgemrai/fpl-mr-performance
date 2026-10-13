"use client";

import { useEffect, useState } from "react";

/** Lee tokens de theme.css en runtime (Recharts necesita valores, no var()). */
export function useCssVars<T extends string>(names: readonly T[]): Record<T, string> | null {
  const [vars, setVars] = useState<Record<T, string> | null>(null);
  const key = names.join(",");
  useEffect(() => {
    const style = getComputedStyle(document.documentElement);
    setVars(Object.fromEntries(names.map((n) => [n, style.getPropertyValue(`--${n}`).trim()])) as Record<T, string>);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return vars;
}

export const SERIES = ["series-1", "series-2", "series-3", "series-4"] as const;
export const seriesVar = (i: number) => `var(--${SERIES[i]})`;
