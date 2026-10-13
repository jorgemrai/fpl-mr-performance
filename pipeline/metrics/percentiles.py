"""Percentiles dentro de la posición (GKP/DEF/MID/FWD), solo entre jugadores elegibles."""

import polars as pl

MIN_MINUTES_FLOOR = 270
MIN_MINUTES_SHARE = 0.25  # fracción de los minutos posibles (90 * GW jugadas)


def min_minutes(gws_finished: int) -> float:
    """Umbral de elegibilidad: max(270, 0.25 * 90 * GW_jugadas)."""
    return max(MIN_MINUTES_FLOOR, MIN_MINUTES_SHARE * 90 * gws_finished)


def percentile(col: str, eligible: pl.Expr, by: str = "position") -> pl.Expr:
    """Percentil 0-100 (rank medio / n) dentro de `by`. Null si no elegible o métrica null."""
    masked = pl.when(eligible).then(pl.col(col))
    return (masked.rank("average").over(by) / masked.count().over(by) * 100).round(0).cast(pl.Int32)


def add_percentiles(df: pl.DataFrame, metrics: list[str], gws_finished: int) -> pl.DataFrame:
    """Añade `eligible` y `p_{métrica}` para cada métrica (mayor = mejor)."""
    eligible = pl.col("minutes") >= min_minutes(gws_finished)
    return df.with_columns(eligible=eligible).with_columns(
        percentile(m, pl.col("eligible")).alias(f"p_{m}") for m in metrics
    )
