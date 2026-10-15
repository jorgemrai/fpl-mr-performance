"""Último snapshot → web/public/data/players.json + meta.json (métricas y percentiles ya calculados)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import yaml

from pipeline import captain
from pipeline.metrics import METRICS, add_metrics, add_percentiles, min_minutes
from pipeline.metrics.core import availability_chance, form_last_n
from pipeline.metrics.defcon import defcon_frequency, defcon_thresholds
from pipeline.metrics.fixtures import team_ease
from pipeline.metrics.ownership import ownership_delta
from pipeline.metrics.percentiles import SMALL_GROUP

SNAPSHOT_DIR = Path("data/snapshots")
OUT_DIR = Path("web/public/data")
RADAR_CONFIG = Path("config/radar.yml")
METRICS_CONFIG = Path("config/metrics.yml")
MAX_BYTES = 2 * 1024 * 1024
RIVAL_GWS = 3
DECIMALS = {
    "ppm": 2, "pts90": 2, "xgi90": 2, "min_pct": 1, "bps90": 1, "form": 1,
    "ict": 1, "defcon90": 1, "defcon_freq": 0, "ease": 2, "own": 1,
}


def snapshot_gws(snapshot_dir: Path) -> list[int]:
    return sorted(
        int(m.group(1)) for p in snapshot_dir.glob("gw*.parquet") if (m := re.fullmatch(r"gw(\d+)\.parquet", p.name))
    )


def latest_gw(snapshot_dir: Path) -> int:
    gws = snapshot_gws(snapshot_dir)
    if not gws:
        raise SystemExit(f"No hay snapshots en {snapshot_dir}; ejecuta `make ingest` primero.")
    return gws[-1]


def previous_gw(snapshot_dir: Path, gw: int) -> int | None:
    """Snapshot anterior más reciente (para el Δ de ownership)."""
    return max((g for g in snapshot_gws(snapshot_dir) if g < gw), default=None)


def build_table(
    players: pl.DataFrame,
    fixtures: pl.DataFrame,
    history: pl.DataFrame | None = None,
    *,
    stats: pl.DataFrame | None = None,
    next_gw: int | None = None,
    thresholds: dict[str, int] | None = None,
    previous: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Snapshot → tabla con métricas, percentiles de grupo, ICT rank, rival próx. 3 y Δ ownership."""
    gws = int(players["gws_finished"][0])
    if thresholds is None:
        thresholds, _ = defcon_thresholds({}, METRICS_CONFIG)
    if stats is None:
        stats = pl.DataFrame(schema={"fixture": pl.Int64, "identifier": pl.String, "element": pl.Int64, "value": pl.Int64})

    df = add_metrics(players, fixtures)
    df = (
        df.join(defcon_frequency(df, stats, thresholds), on="id", how="left")
        .join(team_ease(fixtures, next_gw, RIVAL_GWS), on="team", how="left")
        .join(ownership_delta(df, previous), on="id", how="left")
        .with_columns(chance=availability_chance(next_gw is not None))
    )
    df = add_percentiles(df, METRICS, gws).with_columns(
        min_pct=pl.col("min_pct") * 100,  # en %, para mostrar
        defcon_freq=pl.col("defcon_freq") * 100,
    )
    if history is not None and history.height:
        df = df.join(form_last_n(history, 3), on="id", how="left")
    return df


def _round(v: float | None, nd: int) -> float | int | None:
    if v is None:
        return None
    return int(round(v)) if nd == 0 else round(float(v), nd)


def to_records(df: pl.DataFrame, has_previous: bool = False) -> list[dict]:
    has_form3 = "form3" in df.columns
    teams = dict(df.select("team", "team_short").unique().iter_rows())
    out = []
    for r in df.sort("total_points", descending=True).iter_rows(named=True):
        rec = {
            "id": r["id"],
            "name": r["web_name"],
            "fullName": f"{r['first_name']} {r['second_name']}",
            "team": r["team_short"],
            "pos": r["position"],
            "price": round(r["price"], 1),
            "pts": r["total_points"],
            "min": r["minutes"],
            "status": r["status"],
            "news": r["news"] or None,
            "chance": r["chance"],
            "m": {m: _round(r[m], DECIMALS[m]) for m in METRICS},
            "p": {m: r[f"p_{m}"] for m in METRICS} if r["eligible"] else None,
            "n": r["group_n"],
            "ictRank": r["ict_rank"],
            "defcon": None if r["defcon_hits"] is None else {"hits": r["defcon_hits"], "starts": r["starts"]},
            "next": [
                {"gw": x["gw"], "opp": teams.get(x["opp"], "?"), "home": x["home"], "d": x["difficulty"]}
                for x in (r["next_matches"] or [])
            ],
        }
        if has_previous:
            rec["ownDelta"] = r["own_delta"]
        if has_form3:
            rec["form3"] = None if r["form3"] is None else round(r["form3"], 1)
        out.append(rec)
    return out


def build_meta(
    players: pl.DataFrame,
    n: int,
    has_history: bool,
    events: pl.DataFrame,
    table: pl.DataFrame | None = None,
    extra: dict | None = None,
) -> dict:
    gws = int(players["gws_finished"][0])
    group_n = {}
    if table is not None:
        group_n = dict(table.group_by("position").agg(pl.col("eligible").sum()).iter_rows())
    return {
        "gw": int(players["gw"][0]),
        "gwsFinished": gws,
        "minMinutes": min_minutes(gws),
        "players": n,
        "hasHistory": has_history,
        "dataFetchedAt": players["fetched_at"][0],
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        # Para que el cliente sepa en qué GW está "hoy" y detecte datos desactualizados.
        "deadlines": [{"gw": gw, "deadline": d} for gw, d in events.select("id", "deadline_time").rows()],
        "groupN": group_n,
        "smallGroup": SMALL_GROUP,
        "rivalGws": RIVAL_GWS,
    } | (extra or {})


def target_gw(events: pl.DataFrame) -> tuple[int | None, str | None]:
    """GW del próximo deadline y su fecha; (None, None) si la temporada ha terminado."""
    nxt = events.filter(pl.col("is_next"))
    if nxt.is_empty():
        return None, None
    return int(nxt["id"][0]), nxt["deadline_time"][0]


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def run(
    snapshot_dir: Path = SNAPSHOT_DIR, out_dir: Path = OUT_DIR, captain_config: Path = captain.CONFIG_PATH
) -> tuple[Path, Path]:
    gw = latest_gw(snapshot_dir)
    players = pl.read_parquet(snapshot_dir / f"gw{gw}.parquet")
    fixtures = pl.read_parquet(snapshot_dir / f"gw{gw}.fixtures.parquet")
    hist_path = snapshot_dir / f"gw{gw}.history.parquet"
    history = pl.read_parquet(hist_path) if hist_path.exists() else None
    events_path = snapshot_dir / f"gw{gw}.events.parquet"
    if not events_path.exists():
        raise SystemExit(f"Falta {events_path}: vuelve a ejecutar `make ingest FORCE=1`.")
    events = pl.read_parquet(events_path)
    stats_path = snapshot_dir / f"gw{gw}.stats.parquet"
    stats = pl.read_parquet(stats_path) if stats_path.exists() else None
    gc_path = snapshot_dir / f"gw{gw}.game_config.json"
    game_config = json.loads(gc_path.read_text()) if gc_path.exists() else {}
    thresholds, thr_source = defcon_thresholds(game_config, METRICS_CONFIG)
    prev_gw = previous_gw(snapshot_dir, gw)
    previous = pl.read_parquet(snapshot_dir / f"gw{prev_gw}.parquet") if prev_gw is not None else None
    next_gw, deadline = target_gw(events)

    table = build_table(
        players, fixtures, history, stats=stats, next_gw=next_gw, thresholds=thresholds, previous=previous
    )
    records = to_records(table, has_previous=previous is not None)
    payload = dumps(records)
    if len(payload.encode()) > MAX_BYTES:
        raise SystemExit(f"players.json ocupa {len(payload) / 1e6:.2f} MB (> 2 MB)")

    out_dir.mkdir(parents=True, exist_ok=True)
    players_path, meta_path = out_dir / "players.json", out_dir / "meta.json"
    players_path.write_text(payload)
    radar = yaml.safe_load(RADAR_CONFIG.read_text())
    extra = {
        "nextGw": next_gw,
        "prevSnapshotGw": prev_gw,
        "defconThresholds": thresholds,
        "defconThresholdSource": thr_source,
        "radar": {"default": radar["default_axes"], "optional": radar["optional_axes"], "max": radar["max_axes"]},
    }
    meta_path.write_text(dumps(build_meta(players, len(records), history is not None, events, table, extra)))
    print(f"GW{gw}: {len(records)} jugadores → {players_path} ({len(payload) / 1024:.0f} KB)")

    cap = captain.build_captain(table, fixtures, next_gw, deadline, captain.load_config(captain_config))
    (out_dir / "captain.json").write_text(dumps(cap))
    print(f"Capitán GW{next_gw}: {cap['candidates']} candidatos → {out_dir / 'captain.json'}")
    return players_path, meta_path


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot-dir", type=Path, default=SNAPSHOT_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--captain-config", type=Path, default=captain.CONFIG_PATH)
    args = ap.parse_args(argv)
    run(args.snapshot_dir, args.out_dir, args.captain_config)


if __name__ == "__main__":
    main()
