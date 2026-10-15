"""Capitán sugerido. Base = JSON reales de tests/fixtures/; los escenarios (DGW, blank,
lesión) se derivan modificando esos datos reales, no inventando jugadores."""

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
import yaml

from pipeline import captain, export, ingest

CONFIG = Path(__file__).parents[1] / "config" / "captain.yml"


@pytest.fixture(scope="module")
def cfg() -> captain.CaptainConfig:
    return captain.load_config(CONFIG)


@pytest.fixture(scope="module")
def real(bootstrap, fixtures_json):
    """(tabla de export, fixtures, GW objetivo) a partir de los JSON reales."""
    gw = ingest.next_gw(bootstrap["events"])
    if gw is None:
        pytest.skip("los fixtures son de una temporada terminada (no hay is_next)")
    players = ingest.build_snapshot(bootstrap, datetime.now(UTC))
    fixtures = ingest.build_fixtures(fixtures_json)
    return export.build_table(players, fixtures, None), fixtures, gw


def _team_with_target_fixture(fixtures: pl.DataFrame, gw: int) -> tuple[int, dict]:
    fx = fixtures.filter((pl.col("event") == gw) & ~pl.col("finished")).row(0, named=True)
    return fx["team_h"], fx


# ---------------------------------------------------------------- titularidad


def test_top5_only_available_players(real, cfg):
    table, fixtures, gw = real
    out = captain.build_captain(table, fixtures, gw, None, cfg)
    statuses = dict(table.select("id", "status").iter_rows())
    assert len([t for t in out["top"] if t["rank"] <= cfg.top_n]) == min(cfg.top_n, out["candidates"])
    assert all(statuses[t["id"]] == "a" for t in out["top"])


@pytest.mark.parametrize("status, reason", [("i", "lesión"), ("d", "duda")])
def test_injured_or_doubtful_never_in_top5(real, cfg, status, reason):
    table, fixtures, gw = real
    before = captain.build_captain(table, fixtures, gw, None, cfg)
    targets = [t["id"] for t in before["top"]]
    # Los mismos jugadores reales pasan a lesionados/dudosos: ninguno puede seguir arriba.
    hurt = table.with_columns(
        status=pl.when(pl.col("id").is_in(targets)).then(pl.lit(status)).otherwise(pl.col("status"))
    )
    after = captain.build_captain(hurt, fixtures, gw, None, cfg)
    assert not {t["id"] for t in after["top"]} & set(targets)
    reasons = {d["id"]: d["reason"] for d in after["discarded"]}
    assert all(reasons.get(pid) == reason for pid in targets if pid in reasons)


def test_low_chance_of_playing_is_discarded_as_doubt(real, cfg):
    table, fixtures, gw = real
    top_id = captain.build_captain(table, fixtures, gw, None, cfg)["top"][0]["id"]
    doubt = table.with_columns(
        chance_of_playing_next_round=pl.when(pl.col("id") == top_id).then(50).otherwise(
            pl.col("chance_of_playing_next_round")
        )
    )
    after = captain.build_captain(doubt, fixtures, gw, None, cfg)
    assert top_id not in {t["id"] for t in after["top"]}
    ranked, discarded = captain.rank(doubt, fixtures, gw, cfg)
    row = discarded.filter(pl.col("id") == top_id).row(0, named=True)
    assert row["reason"] == "duda"
    assert row["reason_detail"] == "50% de jugar" or row["news"]


# ------------------------------------------------------------------- DGW / blank


def test_double_gameweek_sums_fdr(real, cfg):
    table, fixtures, gw = real
    team, fx = _team_with_target_fixture(fixtures, gw)
    later = fixtures.filter(
        (pl.col("event") > gw) & ~pl.col("finished") & ((pl.col("team_h") == team) | (pl.col("team_a") == team))
    ).row(0, named=True)
    # Adelantamos un partido real posterior a la GW objetivo → doble jornada.
    dgw = fixtures.with_columns(event=pl.when(pl.col("id") == later["id"]).then(gw).otherwise(pl.col("event")))
    d1 = fx["team_h_difficulty"]
    d2 = later["team_h_difficulty"] if later["team_h"] == team else later["team_a_difficulty"]

    row = captain.team_fdr(captain.team_fixtures(dgw, gw, 1), gw).filter(pl.col("team") == team).row(0, named=True)
    assert row["fdr"] == d1 + d2
    assert row["ease"] == (5 - d1) + (5 - d2)
    assert row["dgw"] is True
    assert sorted(row["target_fixtures"]) == sorted([fx["id"], later["id"]])

    ranked, _ = captain.rank(table, dgw, gw, cfg)
    assert ranked.filter(pl.col("team") == team)["fdr"].unique().to_list() in ([], [d1 + d2])


def test_blank_gameweek_player_never_appears(real, cfg):
    table, fixtures, gw = real
    team, _ = _team_with_target_fixture(fixtures, gw)
    # Aplazamos (event = null) los partidos reales del equipo en la GW objetivo → blank.
    plays = (pl.col("event") == gw) & ((pl.col("team_h") == team) | (pl.col("team_a") == team))
    blank = fixtures.with_columns(event=pl.when(plays).then(None).otherwise(pl.col("event")))

    ranked, discarded = captain.rank(table, blank, gw, cfg)
    assert ranked.filter(pl.col("team") == team).is_empty()
    out = captain.build_captain(table, blank, gw, None, cfg)
    team_ids = set(table.filter(pl.col("team") == team)["id"])
    assert not {t["id"] for t in out["top"]} & team_ids
    available = discarded.filter(
        (pl.col("team") == team) & (pl.col("status") == "a") & (pl.col("min_pct") >= cfg.min_minutes_pct)
        & (pl.col("position") != "GKP")
    )
    assert set(available["reason"]) <= {"sin partido", "duda"}
    assert "sin partido" in set(available["reason"])


# ------------------------------------------------------------------------ vice


def test_vice_never_shares_match_with_captain_real(real, cfg):
    table, fixtures, gw = real
    ranked, _ = captain.rank(table, fixtures, gw, cfg)
    cap, vice = captain.pick_captain_vice(ranked)
    fx = dict(ranked.select("id", "target_fixtures").iter_rows())
    assert vice is not None and not set(fx[cap]) & set(fx[vice])


def test_vice_skips_teammates_and_opponents_even_in_dgw():
    ranked = pl.DataFrame(
        {"id": [1, 2, 3, 4], "target_fixtures": [[10, 12], [12], [10], [13]]},
    )
    assert captain.pick_captain_vice(ranked) == (1, 4)
    assert captain.pick_captain_vice(ranked.head(3)) == (1, None)


def test_vice_from_outside_top_n_is_appended(real, cfg):
    table, fixtures, gw = real
    out = captain.build_captain(table, fixtures, gw, None, cfg)
    roles = [t["role"] for t in out["top"]]
    assert roles.count("C") == 1 and roles.count("V") == 1
    assert out["top"][0]["role"] == "C"


# ----------------------------------------------------------------------- pesos


def _write_cfg(tmp_path: Path, name: str, weights: dict) -> Path:
    raw = yaml.safe_load(CONFIG.read_text()) | {"weights": weights}
    path = tmp_path / name
    path.write_text(yaml.safe_dump(raw))
    return path


def test_changing_yaml_weights_changes_order(real, tmp_path):
    table, fixtures, gw = real
    orders = []
    for name, w in [("form.yml", {"form": 1, "xgi90": 0, "ease": 0}), ("ease.yml", {"form": 0, "xgi90": 0, "ease": 1})]:
        cfg = captain.load_config(_write_cfg(tmp_path, name, w))
        ranked, _ = captain.rank(table, fixtures, gw, cfg)
        orders.append(ranked["id"].head(10).to_list())
    assert orders[0] != orders[1]


def test_default_weights_are_equal(cfg):
    assert len(set(cfg.weights.values())) == 1


@pytest.mark.parametrize(
    "weights", [{"form": 1, "xgi90": 1}, {"form": -1, "xgi90": 1, "ease": 1}, {"form": 0, "xgi90": 0, "ease": 0}]
)
def test_invalid_weights_rejected(tmp_path, weights):
    with pytest.raises(ValueError):
        captain.load_config(_write_cfg(tmp_path, "bad.yml", weights))


def test_season_over_returns_empty_ranking(cfg):
    out = captain.build_captain(pl.DataFrame(), pl.DataFrame(), None, None, cfg)
    assert out["top"] == [] and out["gw"] is None


# -------------------------------------------------------------------- porteros / transparencia


def test_no_goalkeeper_in_top5_nor_in_candidates(real, cfg):
    table, fixtures, gw = real
    ranked, discarded = captain.rank(table, fixtures, gw, cfg)
    assert ranked.filter(pl.col("position") == "GKP").is_empty()  # tampoco entran en los percentiles
    gks = table.filter(pl.col("position") == "GKP")
    assert set(discarded.filter(pl.col("reason") == "portero")["id"]) == set(gks["id"])
    out = captain.build_captain(table, fixtures, gw, None, cfg)
    assert all(t["pos"] != "GKP" for t in out["top"])


def test_discard_counts_sum_exactly_the_excluded(real, cfg):
    table, fixtures, gw = real
    out = captain.build_captain(table, fixtures, gw, None, cfg)
    assert sum(out["discardedByReason"].values()) == out["excluded"] == len(out["discarded"])
    assert out["excluded"] + out["candidates"] == table.height
    assert all(d["reason"] in captain.REASONS for d in out["discarded"])
    for reason, n in out["discardedByReason"].items():
        assert n == sum(d["reason"] == reason for d in out["discarded"])
