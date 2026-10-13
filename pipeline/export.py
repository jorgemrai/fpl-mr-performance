"""Último snapshot → web/public/data/players.json + meta.json (métricas y percentiles ya calculados)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from pipeline.metrics import METRICS, add_metrics, add_percentiles, min_minutes
from pipeline.metrics.core import form_last_n

SNAPSHOT_DIR = Path("data/snapshots")
OUT_DIR = Path("web/public/data")
MAX_BYTES = 2 * 1024 * 1024
DECIMALS = {"ppm": 2, "pts90": 2, "xgi90": 2, "min_pct": 1, "bps": 0, "form": 1}


def latest_gw(snapshot_dir: Path) -> int:
    gws = [int(m.group(1)) for p in snapshot_dir.glob("gw*.parquet") if (m := re.fullmatch(r"gw(\d+)\.parquet", p.name))]
    if not gws:
        raise SystemExit(f"No hay snapshots en {snapshot_dir}; ejecuta `make ingest` primero.")
    return max(gws)


def build_table(players: pl.DataFrame, fixtures: pl.DataFrame, history: pl.DataFrame | None) -> pl.DataFrame:
    gws = int(players["gws_finished"][0])
    df = add_percentiles(add_metrics(players, fixtures), METRICS, gws).with_columns(
        min_pct=pl.col("min_pct") * 100  # en %, para mostrar
    )
    if history is not None and history.height:
        df = df.join(form_last_n(history, 3), on="id", how="left")
    return df


def _round(v: float | None, nd: int) -> float | int | None:
    if v is None:
        return None
    return int(round(v)) if nd == 0 else round(float(v), nd)


def to_records(df: pl.DataFrame) -> list[dict]:
    has_form3 = "form3" in df.columns
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
            "m": {m: _round(r[m], DECIMALS[m]) for m in METRICS},
            "p": {m: r[f"p_{m}"] for m in METRICS} if r["eligible"] else None,
        }
        if has_form3:
            rec["form3"] = None if r["form3"] is None else round(r["form3"], 1)
        out.append(rec)
    return out


def build_meta(players: pl.DataFrame, n: int, has_history: bool) -> dict:
    gws = int(players["gws_finished"][0])
    return {
        "gw": int(players["gw"][0]),
        "gwsFinished": gws,
        "minMinutes": min_minutes(gws),
        "players": n,
        "hasHistory": has_history,
        "dataFetchedAt": players["fetched_at"][0],
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def run(snapshot_dir: Path = SNAPSHOT_DIR, out_dir: Path = OUT_DIR) -> tuple[Path, Path]:
    gw = latest_gw(snapshot_dir)
    players = pl.read_parquet(snapshot_dir / f"gw{gw}.parquet")
    fixtures = pl.read_parquet(snapshot_dir / f"gw{gw}.fixtures.parquet")
    hist_path = snapshot_dir / f"gw{gw}.history.parquet"
    history = pl.read_parquet(hist_path) if hist_path.exists() else None

    records = to_records(build_table(players, fixtures, history))
    payload = dumps(records)
    if len(payload.encode()) > MAX_BYTES:
        raise SystemExit(f"players.json ocupa {len(payload) / 1e6:.2f} MB (> 2 MB)")

    out_dir.mkdir(parents=True, exist_ok=True)
    players_path, meta_path = out_dir / "players.json", out_dir / "meta.json"
    players_path.write_text(payload)
    meta_path.write_text(dumps(build_meta(players, len(records), history is not None)))
    print(f"GW{gw}: {len(records)} jugadores → {players_path} ({len(payload) / 1024:.0f} KB)")
    return players_path, meta_path


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot-dir", type=Path, default=SNAPSHOT_DIR)
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)
    run(args.snapshot_dir, args.out_dir)


if __name__ == "__main__":
    main()
