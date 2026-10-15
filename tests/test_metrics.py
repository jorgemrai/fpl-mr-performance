from datetime import UTC, datetime

import polars as pl
import pytest

from pipeline import ingest
from pipeline.metrics import METRICS, add_metrics, add_percentiles, min_minutes
from pipeline.metrics.core import form_last_n, minutes_pct, per90, ppm, team_games_finished
from pipeline.metrics.percentiles import percentile


def test_ppm_uses_cost_in_tenths_and_nulls_zero_cost():
    df = pl.DataFrame({"total_points": [100, 50], "now_cost": [50, 0]})
    assert df.select(ppm()).to_series().to_list() == [20.0, None]


def test_per90_nulls_below_90_minutes():
    df = pl.DataFrame({"total_points": [10, 5, 3], "minutes": [180, 89, 0]})
    assert df.select(per90("total_points")).to_series().to_list() == [5.0, None, None]


def test_minutes_pct_and_zero_games():
    df = pl.DataFrame({"minutes": [450, 90], "team_games": [10, 0]})
    assert df.select(minutes_pct()).to_series().to_list() == [0.5, None]


def test_team_games_counts_only_finished_home_and_away():
    fx = pl.DataFrame(
        {"team_h": [1, 2, 1], "team_a": [2, 3, 3], "finished": [True, True, False]}
    )
    out = dict(team_games_finished(fx).iter_rows())
    assert out == {1: 1, 2: 2, 3: 1}


def test_form_last_n_sums_double_gw_and_takes_last_three():
    hist = pl.DataFrame(
        {
            "element": [7, 7, 7, 7, 7, 8],
            "round": [1, 2, 3, 4, 4, 1],
            "total_points": [10, 2, 4, 3, 3, 5],
        }
    )
    out = dict(form_last_n(hist, 3).iter_rows())
    assert out == {7: pytest.approx((2 + 4 + 6) / 3), 8: 5.0}


def test_min_minutes_threshold():
    assert min_minutes(0) == 270
    assert min_minutes(12) == 270  # 0.25*90*12 = 270
    assert min_minutes(38) == pytest.approx(855)


def test_percentile_within_position_excludes_ineligible():
    df = pl.DataFrame(
        {
            "position": ["MID", "MID", "MID", "MID", "FWD"],
            "x": [1.0, 2.0, 3.0, 100.0, 0.5],
            "ok": [True, True, True, False, True],
        }
    )
    out = df.select(percentile("x", pl.col("ok"))).to_series().to_list()
    assert out == [33, 67, 100, None, 100]


def test_percentile_null_metric_stays_null():
    df = pl.DataFrame({"position": ["DEF", "DEF"], "x": [None, 1.0], "ok": [True, True]})
    assert df.select(percentile("x", pl.col("ok"))).to_series().to_list() == [None, 100]


def test_pipeline_on_real_data(bootstrap, fixtures_json):
    players = ingest.build_snapshot(bootstrap, datetime.now(UTC))
    fixtures = ingest.build_fixtures(fixtures_json)
    gws = ingest.gws_finished(bootstrap["events"])
    df = add_percentiles(add_metrics(players, fixtures), METRICS, gws)

    for m in METRICS:
        p = df[f"p_{m}"].drop_nulls()
        assert p.min() >= 0 and p.max() <= 100
        assert df.filter(~pl.col("eligible"))[f"p_{m}"].null_count() == df.filter(~pl.col("eligible")).height
    assert df["min_pct"].drop_nulls().max() <= 1.0 + 1e-9
    assert not df.select(pl.col(METRICS).is_infinite().any()).row(0)[0]
