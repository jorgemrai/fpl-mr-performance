import asyncio

import httpx
import polars as pl
import pytest

from pipeline import ingest


def _flaky(failures: int, status: int = 503):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= failures:
            return httpx.Response(status)
        return httpx.Response(200, json={"ok": True})

    return httpx.MockTransport(handler), calls


def test_get_json_retries_on_503_with_exponential_backoff():
    transport, calls = _flaky(failures=2)
    sleeps: list[float] = []
    with httpx.Client(transport=transport) as client:
        assert ingest.get_json(client, "https://x/api", backoff=1.0, sleep=sleeps.append) == {"ok": True}
    assert calls["n"] == 3
    assert sleeps == [1.0, 2.0]


def test_get_json_gives_up_after_max_attempts():
    transport, calls = _flaky(failures=99)
    with httpx.Client(transport=transport) as client, pytest.raises(httpx.HTTPStatusError):
        ingest.get_json(client, "https://x/api", attempts=3, sleep=lambda _: None)
    assert calls["n"] == 3


def test_get_json_does_not_retry_on_404():
    transport, calls = _flaky(failures=99, status=404)
    with httpx.Client(transport=transport) as client, pytest.raises(httpx.HTTPStatusError):
        ingest.get_json(client, "https://x/api", sleep=lambda _: None)
    assert calls["n"] == 1


def test_current_gw_prefers_is_current_then_last_finished():
    assert ingest.current_gw([{"id": 1, "finished": True}, {"id": 2, "is_current": True}]) == 2
    assert ingest.current_gw([{"id": 1, "finished": True}, {"id": 2, "finished": False}]) == 1
    assert ingest.current_gw([{"id": 1, "finished": False}]) == 0


def test_fetch_histories_bounded_concurrency_and_retries():
    state = {"inflight": 0, "peak": 0, "seen": set()}

    async def handler(request: httpx.Request) -> httpx.Response:
        pid = int(request.url.path.rstrip("/").split("/")[-1])
        if pid not in state["seen"]:  # primer intento de cada id: 503
            state["seen"].add(pid)
            return httpx.Response(503)
        state["inflight"] += 1
        state["peak"] = max(state["peak"], state["inflight"])
        await asyncio.sleep(0.001)
        state["inflight"] -= 1
        return httpx.Response(200, json={"history": [{"element": pid, "round": 1, "total_points": pid}]})

    ids = list(range(1, 21))
    out = asyncio.run(ingest.fetch_histories(ids, concurrency=5, transport=httpx.MockTransport(handler), backoff=0))
    assert sorted(out) == ids
    assert state["peak"] <= 5
    hist = ingest.build_history(out)
    assert hist.height == 20


def test_build_snapshot_from_real_bootstrap(bootstrap):
    from datetime import UTC, datetime

    df = ingest.build_snapshot(bootstrap, datetime.now(UTC))
    assert df.height == len(bootstrap["elements"])
    assert df["id"].is_unique().all()
    assert set(df["position"].unique()) <= {"GKP", "DEF", "MID", "FWD"}
    assert df["team_short"].null_count() == 0
    assert df.schema["expected_goal_involvements"] == pl.Float64
    assert df.schema["form"] == pl.Float64
    assert df["gw"][0] == ingest.current_gw(bootstrap["events"])
    assert df.schema["chance_of_playing_next_round"] == pl.Int32


def test_build_fixtures_keeps_official_difficulty(fixtures_json):
    fx = ingest.build_fixtures(fixtures_json)
    for col in ["team_h_difficulty", "team_a_difficulty"]:
        assert fx[col].drop_nulls().is_between(1, 5).all()


def test_run_is_idempotent_without_force(tmp_path, fpl_transport, bootstrap):
    gw = ingest.current_gw(bootstrap["events"])
    first = ingest.run(tmp_path, transport=fpl_transport)
    assert first == tmp_path / f"gw{gw}.parquet"
    assert (tmp_path / f"gw{gw}.fixtures.parquet").exists()
    assert (tmp_path / f"gw{gw}.events.parquet").exists()
    assert (tmp_path / f"gw{gw}.stats.parquet").exists()
    assert (tmp_path / f"gw{gw}.game_config.json").exists()
    mtime = first.stat().st_mtime_ns

    assert ingest.run(tmp_path, transport=fpl_transport) is None
    assert first.stat().st_mtime_ns == mtime

    assert ingest.run(tmp_path, force=True, transport=fpl_transport) == first


def test_fixture_stats_long_format_only_finished(fixtures_json):
    stats = ingest.build_fixture_stats(fixtures_json)
    finished = {fx["id"] for fx in fixtures_json if fx["finished"]}
    assert set(stats["fixture"].unique()) <= finished
    assert "defensive_contribution" in set(stats["identifier"])


def test_defcon_per_match_sums_to_bootstrap_total(bootstrap, fixtures_json):
    """Consistencia: Σ defensive_contribution por partido (fixtures) == total de bootstrap-static."""
    per_match = (
        ingest.build_fixture_stats(fixtures_json)
        .filter(pl.col("identifier") == "defensive_contribution")
        .group_by("element")
        .agg(pl.col("value").sum())
    )
    totals = pl.DataFrame(
        [{"element": e["id"], "total": e["defensive_contribution"]} for e in bootstrap["elements"]]
    )
    diff = totals.join(per_match, on="element", how="left").with_columns(pl.col("value").fill_null(0)).filter(
        pl.col("total") != pl.col("value")
    )
    assert diff.is_empty(), f"diferencias DefCon fixtures vs bootstrap:\n{diff}"
