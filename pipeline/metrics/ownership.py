"""Ownership (selected_by_percent) y su cambio respecto al snapshot anterior."""

import polars as pl


def ownership_delta(current: pl.DataFrame, previous: pl.DataFrame | None) -> pl.DataFrame:
    """→ [id, own_delta] en puntos porcentuales. Sin snapshot previo → columna entera null.

    Jugadores nuevos (sin fila en el previo) → null.
    """
    if previous is None:
        return current.select("id", own_delta=pl.lit(None, dtype=pl.Float64))
    prev = previous.select("id", prev_own=pl.col("selected_by_percent").cast(pl.Float64, strict=False))
    return current.join(prev, on="id", how="left").select(
        "id", own_delta=(pl.col("selected_by_percent") - pl.col("prev_own")).round(1)
    )
