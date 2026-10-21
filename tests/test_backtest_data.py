"""Datos para backtesting: recomendación congelada en el deadline y puntos reales por GW."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import polars as pl
import pytest

from pipeline import captain_log, export, ingest

CFG = Path(__file__).parents[1] / "config" / "captain.yml"


# ------------------------------------------------------------ captain_log


@pytest.fixture
def snap(tmp_path, fpl_transport):
    d = tmp_path / "data" / "snapshots"
    ingest.run(d, transport=fpl_transport, results_dir=tmp_path / "data" / "results")
    return d


def _deadline(bootstrap) -> datetime:
    nxt = next(e for e in bootstrap["events"] if e.get("is_next"))
    return datetime.fromisoformat(nxt["deadline_time"].replace("Z", "+00:00"))


def test_log_written_before_deadline_with_full_ranking(snap, tmp_path, bootstrap):
    before = _deadline(bootstrap) - timedelta(hours=3)
    export.run(snap, tmp_path / "out", CFG, now=before)
    cap = json.loads((tmp_path / "out" / "captain.json").read_text())
    log_path = tmp_path / "data" / "captain_log" / f"gw{cap['gw']}.json"
    log = json.loads(log_path.read_text())
    assert log["gw"] == cap["gw"] and log["deadline"] == cap["deadline"]
    assert [row[0] for row in log["candidates"]] == [c["i"] for c in cap["candidates"]]
    assert [row[1] for row in log["candidates"]] == [c["s"] for c in cap["candidates"]]
    assert log["cols"] == ["id", "score", "form", "xgi90", "ease", "own"]
    assert log["captain"] == next(t["id"] for t in cap["top"] if t["role"] == "C")
    assert len(log["discarded"]) == len(cap["discarded"])
    assert all(row[5] is not None for row in log["candidates"]), "ownership para la referencia 'más poseído'"


def test_log_frozen_after_deadline(snap, tmp_path, bootstrap):
    dl = _deadline(bootstrap)
    export.run(snap, tmp_path / "out", CFG, now=dl - timedelta(minutes=5))
    log_path = next((tmp_path / "data" / "captain_log").glob("gw*.json"))
    frozen = log_path.read_text()
    mtime = log_path.stat().st_mtime_ns
    export.run(snap, tmp_path / "out", CFG, now=dl + timedelta(minutes=1))
    assert log_path.read_text() == frozen and log_path.stat().st_mtime_ns == mtime


def test_log_not_written_when_deadline_already_passed(snap, tmp_path, bootstrap):
    export.run(snap, tmp_path / "out", CFG, now=_deadline(bootstrap) + timedelta(days=1))
    assert not list((tmp_path / "data" / "captain_log").glob("gw*.json"))


def test_is_before_deadline():
    now = datetime(2026, 10, 17, 9, 59, tzinfo=UTC)
    assert captain_log.is_before_deadline("2026-10-17T10:00:00Z", now)
    assert not captain_log.is_before_deadline("2026-10-17T10:00:00Z", now + timedelta(minutes=2))
    assert not captain_log.is_before_deadline(None, now)


# ---------------------------------------------------------------- results


def _live(ids_points: dict[int, int]) -> dict:
    # Forma mínima de GET /api/event/{gw}/live/ (solo los campos que usamos).
    return {"elements": [{"id": i, "stats": {"minutes": 90, "total_points": p}} for i, p in ids_points.items()]}


def test_build_results_and_reject_unexpected_shape():
    df = ingest.build_results(_live({411: 13, 165: 2}), 7)
    assert df.to_dicts() == [
        {"gw": 7, "id": 411, "minutes": 90, "total_points": 13},
        {"gw": 7, "id": 165, "minutes": 90, "total_points": 2},
    ]
    with pytest.raises(ValueError):
        ingest.build_results({"oops": []}, 7)
    with pytest.raises(ValueError):
        ingest.build_results({"elements": [{"stats": {}}]}, 7)


def test_fetch_results_only_missing_finished_gws(tmp_path, bootstrap):
    finished = [e["id"] for e in bootstrap["events"] if e["finished"]]
    results = tmp_path / "results"
    results.mkdir()
    pl.DataFrame({"gw": [finished[0]], "id": [1], "minutes": [90], "total_points": [2]}).write_parquet(
        results / f"gw{finished[0]}.parquet"
    )
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        gw = int(request.url.path.strip("/").split("/")[-2])
        calls.append(gw)
        return httpx.Response(200, json=_live({411: gw}))

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        written = ingest.fetch_results(client, bootstrap["events"], results)
    assert calls == finished[1:], "ni la GW ya guardada ni las no terminadas"
    assert {p.name for p in written} == {f"gw{g}.parquet" for g in finished[1:]}
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert ingest.fetch_results(client, bootstrap["events"], results) == []


def test_results_failure_does_not_break_snapshot(tmp_path, bootstrap, fixtures_json):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bootstrap-static/"):
            return httpx.Response(200, json=bootstrap)
        if request.url.path.endswith("/fixtures/"):
            return httpx.Response(200, json=fixtures_json)
        return httpx.Response(200, json={"unexpected": True})  # live con forma rara

    path = ingest.run(tmp_path / "snap", transport=httpx.MockTransport(handler), results_dir=tmp_path / "results")
    assert path is not None and path.exists()
    assert not list((tmp_path / "results").glob("*.parquet"))
