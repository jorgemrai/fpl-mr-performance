"""Frecuencia DefCon: partidos en que el jugador cruzó el umbral de su posición / partidos de titular."""

from pathlib import Path

import polars as pl
import yaml

from pipeline.metrics.core import NO_DEFCON_POSITIONS

CONFIG_PATH = Path("config/metrics.yml")
# Claves donde buscaríamos el umbral oficial en game_config (hoy la API no lo publica).
GAME_CONFIG_KEYS = ("defensive_contribution_threshold", "defensive_contribution_thresholds", "defcon_threshold")


def defcon_thresholds(game_config: dict, config_path: Path = CONFIG_PATH) -> tuple[dict[str, int], str]:
    """Umbral por posición y su origen ("game_config" o el yml)."""
    for section in (game_config.get("scoring") or {}, game_config.get("rules") or {}, game_config):
        for key in GAME_CONFIG_KEYS:
            val = section.get(key)
            if isinstance(val, dict) and val:
                return {k: int(v) for k, v in val.items() if k not in NO_DEFCON_POSITIONS}, "game_config"
    raw = yaml.safe_load(Path(config_path).read_text()) or {}
    return {k: int(v) for k, v in raw["defcon_threshold"].items()}, str(config_path)


def defcon_frequency(players: pl.DataFrame, stats: pl.DataFrame, thresholds: dict[str, int]) -> pl.DataFrame:
    """→ [id, defcon_hits, defcon_freq].

    Numerador: partidos terminados con defensive_contribution >= umbral de su posición.
    Denominador: `starts` (aproximación: un suplente que cruza el umbral suma arriba pero no abajo),
    por eso se topa en 1.0. Portero o 0 titularidades → null.
    """
    thr = pl.DataFrame({"position": list(thresholds), "threshold": list(thresholds.values())})
    per_match = stats.filter(pl.col("identifier") == "defensive_contribution").select(
        id="element", value="value"
    )
    hits = (
        players.select("id", "position")
        .join(thr, on="position", how="inner")
        .join(per_match, on="id", how="inner")
        .group_by("id")
        .agg(defcon_hits=(pl.col("value") >= pl.col("threshold")).sum().cast(pl.Int32))
    )
    out = players.select("id", "position", "starts").join(hits, on="id", how="left")
    no_defcon = pl.col("position").is_in(NO_DEFCON_POSITIONS) | ~pl.col("position").is_in(list(thresholds))
    return out.select(
        "id",
        defcon_hits=pl.when(no_defcon).then(None).otherwise(pl.col("defcon_hits").fill_null(0)),
        defcon_freq=pl.when(no_defcon | (pl.col("starts") == 0))
        .then(None)
        .otherwise(pl.min_horizontal(pl.col("defcon_hits").fill_null(0) / pl.col("starts"), pl.lit(1.0))),
    )
