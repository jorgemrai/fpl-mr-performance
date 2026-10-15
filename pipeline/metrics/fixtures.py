"""Facilidad del rival en las próximas GW (dificultad oficial FPL)."""

import polars as pl

MAX_DIFFICULTY = 5


def upcoming_matches(fixtures: pl.DataFrame, next_gw: int, gws: int = 3) -> pl.DataFrame:
    """Una fila por (equipo, partido) en las GW [next_gw, next_gw + gws). Dificultad del lado que juega."""
    up = fixtures.filter(pl.col("event").is_between(next_gw, next_gw + gws - 1) & ~pl.col("finished"))
    home = up.select(team="team_h", opp="team_a", home=pl.lit(True), difficulty="team_h_difficulty", gw="event")
    away = up.select(team="team_a", opp="team_h", home=pl.lit(False), difficulty="team_a_difficulty", gw="event")
    return pl.concat([home, away]).sort("team", "gw")


def team_ease(fixtures: pl.DataFrame, next_gw: int | None, gws: int = 3) -> pl.DataFrame:
    """→ [team, ease, next_matches]: ease = promedio de (5 - dificultad) de sus partidos en las próximas `gws` GW.

    Una GW sin partido (blank) no cuenta; un equipo sin ningún partido no aparece (sin eje).
    """
    schema = {"team": pl.Int64, "ease": pl.Float64}
    if next_gw is None:
        return pl.DataFrame(schema=schema).with_columns(next_matches=pl.lit(None))
    return (
        upcoming_matches(fixtures, next_gw, gws)
        .group_by("team")
        .agg(
            ease=(MAX_DIFFICULTY - pl.col("difficulty")).mean(),
            next_matches=pl.struct("gw", "opp", "home", "difficulty"),
        )
    )
