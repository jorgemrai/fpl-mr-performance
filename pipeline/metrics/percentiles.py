"""Percentiles dentro del grupo: misma posición, status != "u" y minutos >= umbral."""

import polars as pl

MIN_MINUTES_FLOOR = 270
MIN_MINUTES_SHARE = 0.25  # fracción de los minutos posibles (90 * GW jugadas)
SMALL_GROUP = 30  # por debajo, el front avisa "grupo pequeño: percentiles aproximados"


def min_minutes(gws_finished: int) -> float:
    """Umbral de elegibilidad: max(270, 0.25 * 90 * GW_jugadas)."""
    return max(MIN_MINUTES_FLOOR, MIN_MINUTES_SHARE * 90 * gws_finished)


def in_group(gws_finished: int) -> pl.Expr:
    return (pl.col("minutes") >= min_minutes(gws_finished)) & (pl.col("status") != "u")


def percentile(col: str, eligible: pl.Expr, by: str = "position") -> pl.Expr:
    """Percentil 0-100 (rank medio / n) dentro de `by`. Null si no elegible o métrica null."""
    masked = pl.when(eligible).then(pl.col(col))
    return (masked.rank("average").over(by) / masked.count().over(by) * 100).round(0).cast(pl.Int32)


def group_rank(col: str, eligible: pl.Expr, by: str = "position") -> pl.Expr:
    """Puesto (1 = mejor) dentro del grupo, p. ej. ICT "#12 de 91". Null fuera del grupo."""
    masked = pl.when(eligible).then(pl.col(col))
    return masked.rank("min", descending=True).over(by).cast(pl.Int32)


def add_percentiles(df: pl.DataFrame, metrics: list[str], gws_finished: int) -> pl.DataFrame:
    """Añade `eligible`, `group_n` (tamaño del grupo de su posición) y `p_{métrica}` (mayor = mejor)."""
    df = df.with_columns(eligible=in_group(gws_finished))
    return df.with_columns(
        group_n=pl.col("eligible").sum().over("position").cast(pl.Int32),
        ict_rank=group_rank("ict", pl.col("eligible")),
        *[percentile(m, pl.col("eligible")).alias(f"p_{m}") for m in metrics if m in df.columns],
    )
