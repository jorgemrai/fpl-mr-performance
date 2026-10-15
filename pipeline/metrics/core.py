"""Métricas por jugador. Funciones puras: reciben columnas/DataFrames, no hacen I/O.

Divisiones por cero → null (nunca inf).
"""

import polars as pl

MIN_MINUTES_PER90 = 90  # por debajo, las métricas /90 no son representativas

# Ejes del radar, en orden. form = campo `form` de la FPL ("Forma (30d)").
METRICS = ["ppm", "pts90", "xgi90", "min_pct", "bps", "form"]


def ppm(points: str = "total_points", cost: str = "now_cost") -> pl.Expr:
    """Puntos por millón. `now_cost` viene en décimas (55 = 5.5M)."""
    return pl.when(pl.col(cost) > 0).then(pl.col(points) / (pl.col(cost) / 10))


def per90(stat: str, minutes: str = "minutes") -> pl.Expr:
    """Stat por 90 minutos; null con menos de MIN_MINUTES_PER90 minutos."""
    return pl.when(pl.col(minutes) >= MIN_MINUTES_PER90).then(pl.col(stat) / pl.col(minutes) * 90)


def minutes_pct(minutes: str = "minutes", games: str = "team_games") -> pl.Expr:
    """Fracción (0-1) de los minutos posibles según partidos terminados de su equipo."""
    return pl.when(pl.col(games) > 0).then(pl.col(minutes) / (pl.col(games) * 90))


def team_games_finished(fixtures: pl.DataFrame) -> pl.DataFrame:
    """Partidos con finished=true por equipo (local + visitante) → [team, team_games]."""
    done = fixtures.filter(pl.col("finished"))
    return (
        pl.concat([done.select(team="team_h"), done.select(team="team_a")])
        .group_by("team")
        .agg(team_games=pl.len().cast(pl.Int32))
    )


def form_last_n(history: pl.DataFrame, n: int = 3) -> pl.DataFrame:
    """Media de puntos en las últimas n GW con partido (dobles GW suman) → [id, form{n}]."""
    return (
        history.group_by("element", "round")
        .agg(pl.col("total_points").sum())
        .sort("element", "round")
        .group_by("element")
        .agg(pl.col("total_points").tail(n).mean().alias(f"form{n}"))
        .rename({"element": "id"})
    )


def add_metrics(players: pl.DataFrame, fixtures: pl.DataFrame) -> pl.DataFrame:
    """Añade las columnas de METRICS (+ price, team_games) al snapshot de jugadores."""
    return (
        players.join(team_games_finished(fixtures), on="team", how="left")
        .with_columns(pl.col("team_games").fill_null(0))
        .with_columns(
            price=pl.col("now_cost") / 10,
            ppm=ppm(),
            pts90=per90("total_points"),
            xgi90=per90("expected_goal_involvements"),
            min_pct=minutes_pct(),
            bps=pl.col("bps"),
            form=pl.col("form"),
        )
    )
