"""Métricas de la revisión GW6: BPS/90, DefCon, estado, ICT de grupo, rival próx. 3, ownership Δ."""

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from pipeline import export, ingest
from pipeline.metrics.core import availability_chance, per90
from pipeline.metrics.defcon import defcon_frequency, defcon_thresholds
from pipeline.metrics.fixtures import team_ease
from pipeline.metrics.ownership import ownership_delta
from pipeline.metrics.percentiles import min_minutes

METRICS_YML = Path(__file__).parents[1] / "config" / "metrics.yml"
THRESHOLDS = {"DEF": 10, "MID": 12, "FWD": 12}


@pytest.fixture(scope="module")
def real(bootstrap, fixtures_json):
    players = ingest.build_snapshot(bootstrap, datetime.now(UTC))
    fixtures = ingest.build_fixtures(fixtures_json)
    stats = ingest.build_fixture_stats(fixtures_json)
    nxt = ingest.next_gw(bootstrap["events"])
    table = export.build_table(players, fixtures, stats=stats, next_gw=nxt, thresholds=THRESHOLDS)
    return players, fixtures, stats, nxt, table


def _team_id(bootstrap, short):
    return next(t["id"] for t in bootstrap["teams"] if t["short_name"] == short)


# ------------------------------------------------------------------- BPS/90


def test_bps90_zero_minutes_is_null():
    df = pl.DataFrame({"bps": [0, 30, 45], "minutes": [0, 90, 180]})
    assert df.select(per90("bps")).to_series().to_list() == [None, 30.0, 22.5]


def test_bps90_real_zero_minutes_null(real):
    *_, table = real
    assert table.filter(pl.col("minutes") == 0)["bps90"].null_count() == table.filter(pl.col("minutes") == 0).height


# ------------------------------------------------------------------- DefCon


def test_defcon_thresholds_fall_back_to_yml_when_game_config_lacks_them(bootstrap):
    thr, source = defcon_thresholds(bootstrap["game_config"], METRICS_YML)
    assert thr == THRESHOLDS and source.endswith("metrics.yml")


def test_defcon_thresholds_prefer_game_config():
    gc = {"scoring": {"defensive_contribution_threshold": {"DEF": 9, "MID": 11, "FWD": 11, "GKP": 0}}}
    assert defcon_thresholds(gc, METRICS_YML) == ({"DEF": 9, "MID": 11, "FWD": 11}, "game_config")


def test_defcon_frequency_known_values_threshold_by_position_and_gk_null():
    players = pl.DataFrame(
        {"id": [1, 2, 3, 4, 5], "position": ["DEF", "MID", "GKP", "FWD", "DEF"], "starts": [5, 4, 6, 0, 1]}
    )
    values = {1: [10, 9, 12, 3, 11], 2: [11, 12, 13], 3: [15], 4: [12], 5: [10, 10]}
    stats = pl.DataFrame(
        [{"identifier": "defensive_contribution", "element": pid, "value": v} for pid, vs in values.items() for v in vs]
    )
    out = {r["id"]: (r["defcon_hits"], r["defcon_freq"]) for r in defcon_frequency(players, stats, THRESHOLDS).iter_rows(named=True)}
    assert out[1] == (3, 0.6)  # DEF: 10, 12, 11 cruzan el umbral de 10
    assert out[2] == (2, 0.5)  # MID: 11 NO cuenta (umbral 12), 12 y 13 sí
    assert out[3] == (None, None)  # portero
    assert out[4] == (1, None)  # 0 titularidades → sin frecuencia
    assert out[5] == (2, 1.0)  # suplente que cruza el umbral: se topa en 100%


def test_defcon_frequency_real_matches_manual_count(real, fixtures_json, bootstrap):
    players, _, stats, _, table = real
    gabriel = next(e for e in bootstrap["elements"] if e["web_name"] == "Gabriel")
    manual = sum(
        v["value"] >= THRESHOLDS["DEF"]
        for fx in fixtures_json
        if fx["finished"]
        for st in fx["stats"]
        if st["identifier"] == "defensive_contribution"
        for side in "ha"
        for v in st[side]
        if v["element"] == gabriel["id"]
    )
    row = table.filter(pl.col("id") == gabriel["id"]).row(0, named=True)
    assert row["defcon_hits"] == manual
    assert row["defcon_freq"] == pytest.approx(min(manual / gabriel["starts"], 1) * 100)
    assert table.filter(pl.col("position") == "GKP")["defcon90"].null_count() == table.filter(pl.col("position") == "GKP").height


# ------------------------------------------------------------------- estado


def test_status_chance_uses_next_round_when_is_next_exists():
    df = pl.DataFrame({"chance_of_playing_this_round": [25, None], "chance_of_playing_next_round": [75, None]})
    assert df.select(availability_chance(True)).to_series().to_list() == [75, None]
    assert df.select(availability_chance(False)).to_series().to_list() == [25, None]


def test_status_real_next_round_and_null_means_no_alert(real, bootstrap):
    *_, nxt, table = real
    assert nxt is not None
    els = {e["id"]: e for e in bootstrap["elements"]}
    records = {r["id"]: r for r in export.to_records(table)}
    for pid, rec in records.items():
        assert rec["chance"] == els[pid]["chance_of_playing_next_round"]
    available_no_news = [r for r in records.values() if r["status"] == "a" and r["chance"] is None]
    assert available_no_news, "debe haber jugadores sin alerta (chance null)"


# ---------------------------------------------------------------------- ICT


def test_ict_rank_is_within_our_group_not_api_rank(real, bootstrap):
    *_, table = real
    group = table.filter(pl.col("eligible"))
    assert table.filter(~pl.col("eligible"))["ict_rank"].null_count() == table.filter(~pl.col("eligible")).height
    for pos, sub in group.group_by("position"):
        ranks = sub.sort("ict", descending=True)["ict_rank"].to_list()
        assert ranks[0] == 1 and max(ranks) <= sub.height
    # El ranking de la API cuenta los 667 (o toda la posición): al menos un jugador queda distinto.
    api = {e["id"]: e["ict_index_rank_type"] for e in bootstrap["elements"]}
    assert any(api[r["id"]] != r["ict_rank"] for r in group.iter_rows(named=True))
    assert group["group_n"].max() < len(bootstrap["elements"])


def test_group_excludes_unavailable_and_low_minutes(real, bootstrap):
    *_, table = real
    thr = min_minutes(ingest.gws_finished(bootstrap["events"]))
    assert table.filter(pl.col("status") == "u")["p_ppm"].null_count() == table.filter(pl.col("status") == "u").height
    expected = table.filter((pl.col("status") != "u") & (pl.col("minutes") >= thr)).group_by("position").len()
    for pos, n in expected.iter_rows():
        assert table.filter(pl.col("position") == pos)["group_n"].unique().to_list() == [n]


# -------------------------------------------------------------------- rival


def test_rival_ease_average_next_three(bootstrap, fixtures_json):
    mci = _team_id(bootstrap, "MCI")
    nxt = ingest.next_gw(bootstrap["events"])
    row = team_ease(ingest.build_fixtures(fixtures_json), nxt).filter(pl.col("team") == mci).row(0, named=True)
    # GW7 IPS (L) 2 · GW8 AVL (V) 3 · GW9 BHA (L) 3 → (3 + 2 + 2) / 3
    assert row["ease"] == pytest.approx(7 / 3)
    assert [m["gw"] for m in row["next_matches"]] == [7, 8, 9]


def test_rival_ease_blank_in_the_middle_does_not_count(bootstrap, fixtures_blank_json):
    mci = _team_id(bootstrap, "MCI")
    nxt = ingest.next_gw(bootstrap["events"])
    row = team_ease(ingest.build_fixtures(fixtures_blank_json), nxt).filter(pl.col("team") == mci).row(0, named=True)
    assert row["ease"] == pytest.approx((3 + 2) / 2)  # GW8 en blanco: solo GW7 y GW9
    assert [m["gw"] for m in row["next_matches"]] == [7, 9]


def test_rival_no_matches_no_axis():
    fx = pl.DataFrame(
        {"event": [7], "finished": [False], "team_h": [1], "team_a": [2], "team_h_difficulty": [2], "team_a_difficulty": [4]}
    )
    out = team_ease(fx, 7)
    assert set(out["team"]) == {1, 2}  # el equipo 3 no juega → sin fila → sin eje
    assert team_ease(fx, None).is_empty()


# ---------------------------------------------------------------- ownership


def test_ownership_delta_only_with_previous_snapshot():
    cur = pl.DataFrame({"id": [1, 2, 3], "selected_by_percent": [43.7, 5.0, 1.0]})
    prev = pl.DataFrame({"id": [1, 2], "selected_by_percent": [40.2, 6.5]})
    assert ownership_delta(cur, None)["own_delta"].null_count() == 3
    assert ownership_delta(cur, prev)["own_delta"].to_list() == [3.5, -1.5, None]


def test_ownership_delta_absent_from_json_without_previous(real):
    *_, table = real
    assert all("ownDelta" not in r for r in export.to_records(table, has_previous=False))


def test_ownership_delta_gw05_vs_gw06(bootstrap_gw05, bootstrap, fixtures_json, tmp_path):
    """Con un snapshot previo real (GW5) el JSON lleva ownDelta = own(GW6) - own(GW5)."""
    snap = tmp_path / "snap"
    snap.mkdir()
    ingest.build_snapshot(bootstrap_gw05, datetime.now(UTC)).write_parquet(snap / "gw5.parquet")
    players = ingest.build_snapshot(bootstrap, datetime.now(UTC))
    prev = pl.read_parquet(snap / "gw5.parquet")
    table = export.build_table(players, ingest.build_fixtures(fixtures_json), previous=prev, thresholds=THRESHOLDS)
    recs = {r["id"]: r for r in export.to_records(table, has_previous=True)}
    old = {e["id"]: float(e["selected_by_percent"]) for e in bootstrap_gw05["elements"]}
    for e in bootstrap["elements"][:50]:
        if e["id"] in old:
            assert recs[e["id"]]["ownDelta"] == pytest.approx(float(e["selected_by_percent"]) - old[e["id"]], abs=0.051)
