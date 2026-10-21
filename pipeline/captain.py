"""Capitán sugerido: ranking por proceso (rival + forma + titularidad), sin plantilla.

Funciones puras sobre DataFrames salvo `load_config`. Lo invoca export.py → captain.json.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl
import yaml

CONFIG_PATH = Path("config/captain.yml")
FACTORS = ["form", "xgi90", "ease"]
MAX_DIFFICULTY = 5  # FDR oficial va de 1 (fácil) a 5 (difícil)

STATUS_REASONS = {"d": "duda", "i": "lesión", "s": "sanción", "u": "no disponible", "n": "no disponible"}
EXCLUDED_POSITIONS = {"GKP"}  # el capitán nunca es portero: fuera de candidatos y de sus percentiles
REASONS = ["portero", "lesión", "duda", "sanción", "no disponible", "pocos minutos", "sin partido"]


@dataclass(frozen=True)
class CaptainConfig:
    weights: dict[str, float]
    horizon_gws: int = 1
    min_minutes_pct: float = 60.0
    min_chance_of_playing: int = 75
    top_n: int = 5


def load_config(path: Path = CONFIG_PATH) -> CaptainConfig:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    weights = {k: float(v) for k, v in (raw.get("weights") or {}).items()}
    if set(weights) != set(FACTORS):
        raise ValueError(f"{path}: weights debe tener exactamente {FACTORS}, tiene {sorted(weights)}")
    if any(w < 0 for w in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError(f"{path}: los pesos deben ser >= 0 y sumar > 0")
    cfg = CaptainConfig(weights=weights, **{k: v for k, v in raw.items() if k != "weights"})
    if not 1 <= cfg.horizon_gws <= 3:
        raise ValueError(f"{path}: horizon_gws debe estar entre 1 y 3")
    return cfg


# --------------------------------------------------------------------------- FDR


def team_fixtures(fixtures: pl.DataFrame, target_gw: int, horizon: int) -> pl.DataFrame:
    """Una fila por (equipo, partido) en las GW [target_gw, target_gw + horizon)."""
    upcoming = fixtures.filter(
        pl.col("event").is_between(target_gw, target_gw + horizon - 1) & ~pl.col("finished")
    )
    side = lambda team, opp, diff, home: upcoming.select(  # noqa: E731
        team=pl.col(team),
        opp=pl.col(opp),
        home=pl.lit(home),
        difficulty=pl.col(diff),
        fixture=pl.col("id"),
        gw=pl.col("event"),
    )
    return pl.concat(
        [side("team_h", "team_a", "team_h_difficulty", True), side("team_a", "team_h", "team_a_difficulty", False)]
    ).sort("team", "gw", "fixture")


def team_fdr(tf: pl.DataFrame, target_gw: int) -> pl.DataFrame:
    """Por equipo: FDR sumado (doble jornada suma ambos), facilidad, DGW y partidos de la GW objetivo.

    Equipos sin partido en la GW objetivo (blank) no aparecen.
    """
    in_target = pl.col("gw") == target_gw
    return (
        tf.group_by("team")
        .agg(
            fdr=pl.col("difficulty").sum(),
            ease=(MAX_DIFFICULTY - pl.col("difficulty")).sum(),
            n_target=in_target.sum(),
            target_fixtures=pl.col("fixture").filter(in_target),
            matches=pl.struct("gw", "opp", "home", "difficulty"),
            match_fixtures=pl.col("fixture"),
        )
        .filter(pl.col("n_target") > 0)
        .with_columns(dgw=pl.col("n_target") >= 2)
    )


# ------------------------------------------------------------------- titularidad


def discard_reason(cfg: CaptainConfig) -> pl.Expr:
    """Motivo de descarte, uno de REASONS (null = pasa el filtro).

    Orden: portero, estado, probabilidad de jugar, minutos, sin partido. Cuenta el primero que aplica.
    """
    chance = pl.col("chance_of_playing_next_round")
    return (
        pl.when(pl.col("position").is_in(EXCLUDED_POSITIONS))
        .then(pl.lit("portero"))
        .when(pl.col("status") != "a")
        .then(pl.col("status").replace_strict(STATUS_REASONS, default="no disponible"))
        .when(chance.is_not_null() & (chance < cfg.min_chance_of_playing))
        .then(pl.lit("duda"))
        .when(pl.col("min_pct").fill_null(0) < cfg.min_minutes_pct)
        .then(pl.lit("pocos minutos"))
        .when(pl.col("fdr").is_null())
        .then(pl.lit("sin partido"))
        .otherwise(None)
    )


def discard_reasons(cfg: CaptainConfig) -> pl.Expr:
    """Todos los motivos que aplican, en el mismo orden que `discard_reason` (el primero = principal).

    Lista vacía = pasa el filtro. No cambia quién es candidato: solo añade información.
    """
    chance = pl.col("chance_of_playing_next_round")
    checks = [
        pl.when(pl.col("position").is_in(EXCLUDED_POSITIONS)).then(pl.lit("portero")),
        pl.when(pl.col("status") != "a").then(
            pl.col("status").replace_strict(STATUS_REASONS, default="no disponible")
        ),
        pl.when(chance.is_not_null() & (chance < cfg.min_chance_of_playing)).then(pl.lit("duda")),
        pl.when(pl.col("min_pct").fill_null(0) < cfg.min_minutes_pct).then(pl.lit("pocos minutos")),
        pl.when(pl.col("fdr").is_null()).then(pl.lit("sin partido")),
    ]
    return pl.concat_list(checks).list.drop_nulls().list.unique(maintain_order=True)


def discard_detail() -> pl.Expr:
    """Contexto del motivo: news de la FPL, % de probabilidad o % de minutos."""
    chance = pl.col("chance_of_playing_next_round")
    news = pl.col("news").fill_null("")
    return (
        pl.when(pl.col("reason").is_in(["lesión", "duda", "sanción", "no disponible"]) & (news != ""))
        .then(news)
        .when(pl.col("reason") == "duda")
        .then(pl.format("{}% de jugar", chance))
        .when(pl.col("reason") == "pocos minutos")
        .then(pl.format("{}% de minutos", pl.col("min_pct").fill_null(0).round(0).cast(pl.Int32)))
        .otherwise(None)
    )


# ------------------------------------------------------------------------ score


def candidate_pct(col: str) -> pl.Expr:
    """Percentil 0-100 dentro de todos los candidatos (null cuenta como el peor valor)."""
    v = pl.col(col).fill_null(float("-inf"))
    return v.rank("average") / pl.len() * 100


def score(candidates: pl.DataFrame, weights: dict[str, float]) -> pl.DataFrame:
    total = sum(weights.values())
    return (
        candidates.with_columns(candidate_pct(f).alias(f"pct_{f}") for f in FACTORS)
        .with_columns(score=pl.sum_horizontal(pl.col(f"pct_{f}") * w for f, w in weights.items()) / total)
        .sort(["score", "form", "id"], descending=[True, True, False])
    )


def pick_captain_vice(ranked: pl.DataFrame) -> tuple[int | None, int | None]:
    """Capitán = primero. Vice = el siguiente que no comparte ningún partido de la GW objetivo."""
    if ranked.is_empty():
        return None, None
    rows = ranked.select("id", "target_fixtures").rows()
    cap_id, cap_fx = rows[0][0], set(rows[0][1])
    vice = next((pid for pid, fx in rows[1:] if not cap_fx & set(fx)), None)
    return cap_id, vice


# ------------------------------------------------------------------------- build


def rank(df: pl.DataFrame, fixtures: pl.DataFrame, target_gw: int, cfg: CaptainConfig):
    """→ (ranking de candidatos, descartados con motivo). `df` = tabla de export.build_table."""
    fdr = team_fdr(team_fixtures(fixtures, target_gw, cfg.horizon_gws), target_gw)
    # La tabla ya trae su propio `ease` (rival próx. 3, promedio): el capitán usa el suyo (horizonte del yml).
    df = df.drop([c for c in fdr.columns if c != "team" and c in df.columns])
    pool = (
        df.join(fdr, on="team", how="left")
        .with_columns(reason=discard_reason(cfg), reasons=discard_reasons(cfg))
        .with_columns(reason_detail=discard_detail())
    )
    candidates = pool.filter(pl.col("reason").is_null())
    discarded = pool.filter(pl.col("reason").is_not_null())
    return score(candidates, cfg.weights), discarded


def _r(v, nd=2):
    return None if v is None else round(float(v), nd)


def build_captain(
    df: pl.DataFrame, fixtures: pl.DataFrame, target_gw: int | None, deadline: str | None, cfg: CaptainConfig
) -> dict:
    base = {
        "gw": target_gw,
        "deadline": deadline,
        "horizonGws": cfg.horizon_gws,
        "weights": cfg.weights,
        "minMinutesPct": cfg.min_minutes_pct,
        "minChanceOfPlaying": cfg.min_chance_of_playing,
    }
    if target_gw is None:
        return base | {"candidates": [], "top": [], "discarded": [], "discardedByReason": {}, "excluded": 0}

    ranked, discarded = rank(df, fixtures, target_gw, cfg)
    cap, vice = pick_captain_vice(ranked)
    teams = dict(df.select("team", "team_short").unique().iter_rows())

    top_ids = ranked["id"].head(cfg.top_n).to_list()
    if vice is not None and vice not in top_ids:
        top_ids.append(vice)  # el vice puede venir de más abajo si el top comparte partido
    top = []
    for r in ranked.filter(pl.col("id").is_in(top_ids)).iter_rows(named=True):
        top.append(
            {
                "rank": top_ids.index(r["id"]) + 1,
                "id": r["id"],
                "name": r["web_name"],
                "team": r["team_short"],
                "pos": r["position"],
                "price": round(r["price"], 1),
                "role": "C" if r["id"] == cap else "V" if r["id"] == vice else None,
                "score": _r(r["score"], 1),
                "form": _r(r["form"], 1),
                "xgi90": _r(r["xgi90"]),
                "fdr": r["fdr"],
                "ease": r["ease"],
                "dgw": r["dgw"],
                "fixtures": [
                    {"gw": m["gw"], "opp": teams.get(m["opp"], "?"), "home": m["home"], "difficulty": m["difficulty"]}
                    for m in r["matches"]
                ],
                "pct": {f: round(r[f"pct_{f}"]) for f in FACTORS},
            }
        )
    top.sort(key=lambda x: x["rank"])

    counts = dict(discarded.group_by("reason").len().iter_rows())
    by_reason = {k: counts.get(k, 0) for k in REASONS} | {k: v for k, v in counts.items() if k not in REASONS}
    return base | {
        # Todos los candidatos en orden global (puesto = índice + 1), para filtrar en el cliente
        # sin recalcular nada: mismo score, mismos percentiles (contra el universo).
        "candidates": candidate_records(ranked, teams),
        "top": top,
        # Todos los descartados (los de más puntos primero) con todos sus motivos; el conteo por motivo
        # usa el principal y suma exactamente `excluded`. Nombre/equipo se cruzan con players.json por id.
        "discarded": discard_records(discarded),
        "discardedByReason": by_reason,
        "excluded": discarded.height,
    }


def candidate_records(ranked: pl.DataFrame, teams: dict[int, str]) -> list[dict]:
    """Compacto: i=id, s=score, f/x/e=[valor, percentil] de forma, xGI/90 y ease,
    m=[[fixture_id, rival, "H"|"A", dificultad, gw], ...] en el horizonte, d=1 si doble jornada en la GW objetivo."""
    out = []
    for r in ranked.iter_rows(named=True):
        rec = {
            "i": r["id"],
            "s": _r(r["score"], 1),
            "f": [_r(r["form"], 1), round(r["pct_form"])],
            "x": [_r(r["xgi90"]), round(r["pct_xgi90"])],
            "e": [r["ease"], round(r["pct_ease"])],
            "m": [
                [fx, teams.get(m["opp"], "?"), "H" if m["home"] else "A", m["difficulty"], m["gw"]]
                for fx, m in zip(r["match_fixtures"], r["matches"])
            ],
        }
        if r["dgw"]:
            rec["d"] = 1
        out.append(rec)
    return out


def discard_records(discarded: pl.DataFrame) -> list[dict]:
    """Compacto: i=id, r=motivos (principal primero), n=news de la FPL, c=chance_of_playing_next_round."""
    out = []
    for r in discarded.sort(["total_points", "id"], descending=[True, False]).iter_rows(named=True):
        rec = {"i": r["id"], "r": r["reasons"]}
        if r["news"]:
            rec["n"] = r["news"]
        if r["chance_of_playing_next_round"] is not None:
            rec["c"] = r["chance_of_playing_next_round"]
        out.append(rec)
    return out
