import json

import pytest

from pipeline import export, ingest
from pipeline.metrics import METRICS


@pytest.fixture
def exported(tmp_path, fpl_transport):
    snap = tmp_path / "snapshots"
    ingest.run(snap, transport=fpl_transport)
    players_path, meta_path = export.run(snap, tmp_path / "out")
    return players_path, json.loads(players_path.read_text()), json.loads(meta_path.read_text())


def test_players_json_schema_and_size(exported, bootstrap):
    path, players, _ = exported
    assert path.stat().st_size < export.MAX_BYTES
    assert len(players) == len(bootstrap["elements"])
    p = players[0]
    assert {"id", "name", "fullName", "team", "pos", "price", "pts", "min", "m", "p"} <= p.keys()
    assert list(p["m"]) == METRICS
    assert all(r["pos"] in {"GKP", "DEF", "MID", "FWD"} for r in players)


def test_percentiles_only_for_eligible(exported):
    _, players, meta = exported
    for r in players:
        if r["min"] < meta["minMinutes"]:
            assert r["p"] is None
        elif r["p"] is not None:
            assert all(v is None or 0 <= v <= 100 for v in r["p"].values())
    assert any(r["p"] is not None for r in players)


def test_meta_json(exported, bootstrap):
    _, players, meta = exported
    assert meta["gw"] == ingest.current_gw(bootstrap["events"])
    assert meta["players"] == len(players)
    assert meta["minMinutes"] >= 270
    assert meta["hasHistory"] is False
    assert meta["dataFetchedAt"] and meta["generatedAt"]


def test_latest_gw_ignores_side_files(tmp_path):
    for name in ["gw3.parquet", "gw12.parquet", "gw12.fixtures.parquet", "gw15.history.parquet"]:
        (tmp_path / name).touch()
    assert export.latest_gw(tmp_path) == 12
