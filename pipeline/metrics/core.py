"""Métricas por jugador. Funciones puras: reciben columnas/DataFrames, no hacen I/O.

Divisiones por cero → null (nunca inf).
"""

import polars as pl

MIN_MINUTES_PER90 = 90  # por debajo, las métricas /90 no son representativas

# Métricas con percentil dentro del grupo (posición). form = campo `form` de la FPL ("Forma (30d)").
METRICS = [
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
]
NO_DEFCON_POSITIONS = {"GKP"}


def ppm(points: str = "total_points", cost: str = "now_cost") -> pl.Expr:
    """Puntos por millón. `now_cost` viene en décimas (55 = 5.5M)."""
    return pl.when(pl.col(cost) > 0).then(pl.col(points) / (pl.col(cost) / 10))


def per90(stat: str, minutes: str = "minutes") -> pl.Expr:
    """Stat por 90 minutos; null con menos de MIN_MINUTES_PER90 minutos."""
    return pl.when(pl.col(minutes) >= MIN_MINUTES_PER90).then(pl.col(stat) / pl.col(minutes) * 90)


def minutes_pct(minutes: str = "minutes", games: str = "team_games") -> pl.Expr:
    """Fracción (0-1) de los minutos posibles según partidos terminados de su equipo."""
    return pl.when(pl.col(games) > 0).then(pl.col(minutes) / (pl.col(games) * 90))


def defcon90(minutes: str = "minutes") -> pl.Expr:
    """DefCon por 90 (== defensive_contribution_per_90 de la API). Portero: null."""
    return pl.when(~pl.col("position").is_in(NO_DEFCON_POSITIONS)).then(per90("defensive_contribution", minutes))


def availability_chance(has_next_event: bool) -> pl.Expr:
    """Probabilidad de jugar a mostrar: next_round si hay evento is_next, si no this_round. Null = sin alerta."""
    return pl.col("chance_of_playing_next_round" if has_next_event else "chance_of_playing_this_round")


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
    """Añade las métricas simples (+ price, team_games). DefCon freq, ease y Δ ownership van aparte."""
    return (
        players.join(team_games_finished(fixtures), on="team", how="left")
        .with_columns(pl.col("team_games").fill_null(0))
        .with_columns(
            price=pl.col("now_cost") / 10,
            ppm=ppm(),
            pts90=per90("total_points"),
            xgi90=per90("expected_goal_involvements"),
            min_pct=minutes_pct(),
            bps90=per90("bps"),
            form=pl.col("form"),
            ict=pl.col("ict_index"),
            defcon90=defcon90(),
            own=pl.col("selected_by_percent"),
        )
    )
