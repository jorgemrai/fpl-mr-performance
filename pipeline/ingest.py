"""Ingesta FPL: bootstrap-static + fixtures → data/snapshots/gw{N}.parquet.

Solo corre en local o en GitHub Actions. Idempotente: no sobrescribe sin --force.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import polars as pl

BASE_URL = "https://fantasy.premierleague.com/api"
SNAPSHOT_DIR = Path("data/snapshots")
HEADERS = {"User-Agent": "mr-fpl-performance/0.1 (+https://github.com/jorgemrai/fpl-mr-performance)"}
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 5
BACKOFF_S = 1.0
TIMEOUT_S = 30.0
DEFAULT_CONCURRENCY = 6

# Campos numéricos que la API devuelve como string ("1.23").
FLOAT_STR_FIELDS = [
    "form",
    "points_per_game",
    "selected_by_percent",
    "expected_goals",
    "expected_assists",
    "expected_goal_involvements",
    "expected_goals_conceded",
]
ELEMENT_FIELDS = [
    "id",
    "web_name",
    "first_name",
    "second_name",
    "team",
    "element_type",
    "status",
    "chance_of_playing_next_round",
    "now_cost",
    "total_points",
    "minutes",
    "goals_scored",
    "assists",
    "clean_sheets",
    "bps",
    *FLOAT_STR_FIELDS,
]
FIXTURE_FIELDS = [
    "id",
    "event",
    "team_h",
    "team_a",
    "finished",
    "kickoff_time",
    "team_h_score",
    "team_a_score",
    "team_h_difficulty",
    "team_a_difficulty",
]
EVENT_FIELDS = ["id", "deadline_time", "finished", "is_current", "is_next"]
HISTORY_FIELDS = ["element", "fixture", "round", "total_points", "minutes", "kickoff_time"]


# --------------------------------------------------------------------------- HTTP


def _backoff(attempt: int, base: float) -> float:
    return base * 2**attempt


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRY_STATUS
    return isinstance(exc, httpx.TransportError)


def get_json(
    client: httpx.Client,
    url: str,
    attempts: int = MAX_ATTEMPTS,
    backoff: float = BACKOFF_S,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """GET con reintentos y backoff exponencial ante 429/5xx y errores de red."""
    for attempt in range(attempts):
        try:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if not _retryable(exc) or attempt == attempts - 1:
                raise
            print(f"  retry {attempt + 1}/{attempts - 1} {url}: {exc}", file=sys.stderr)
            sleep(_backoff(attempt, backoff))
    raise AssertionError("unreachable")


async def get_json_async(
    client: httpx.AsyncClient,
    url: str,
    attempts: int = MAX_ATTEMPTS,
    backoff: float = BACKOFF_S,
) -> Any:
    for attempt in range(attempts):
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            if not _retryable(exc) or attempt == attempts - 1:
                raise
            await asyncio.sleep(_backoff(attempt, backoff))
    raise AssertionError("unreachable")


def fetch_core(client: httpx.Client) -> tuple[dict, list]:
    bootstrap = get_json(client, f"{BASE_URL}/bootstrap-static/")
    fixtures = get_json(client, f"{BASE_URL}/fixtures/")
    return bootstrap, fixtures


async def fetch_histories(
    ids: list[int],
    concurrency: int = DEFAULT_CONCURRENCY,
    transport: httpx.AsyncBaseTransport | None = None,
    backoff: float = BACKOFF_S,
) -> dict[int, dict]:
    """Descarga element-summary/{id} con concurrencia acotada."""
    sem = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT_S, transport=transport) as client:

        async def one(pid: int) -> tuple[int, dict]:
            async with sem:
                return pid, await get_json_async(client, f"{BASE_URL}/element-summary/{pid}/", backoff=backoff)

        results = await asyncio.gather(*(one(pid) for pid in ids))
    return dict(results)


# ------------------------------------------------------------------- transformación


def current_gw(events: list[dict]) -> int:
    """GW en curso; si no hay ninguna marcada, la última terminada; 0 en pretemporada."""
    for ev in events:
        if ev.get("is_current"):
            return int(ev["id"])
    finished = [int(ev["id"]) for ev in events if ev.get("finished")]
    return max(finished, default=0)


def next_gw(events: list[dict]) -> int | None:
    """GW del próximo deadline (is_next); None si la temporada ha terminado."""
    for ev in events:
        if ev.get("is_next"):
            return int(ev["id"])
    return None


def gws_finished(events: list[dict]) -> int:
    return sum(1 for ev in events if ev.get("finished"))


def build_snapshot(bootstrap: dict, fetched_at: datetime) -> pl.DataFrame:
    """Jugadores + equipo + posición, una fila por jugador. Pura (sin I/O)."""
    elements = pl.DataFrame([{k: el.get(k) for k in ELEMENT_FIELDS} for el in bootstrap["elements"]])
    teams = pl.DataFrame(
        [{"team": t["id"], "team_short": t["short_name"], "team_name": t["name"]} for t in bootstrap["teams"]]
    )
    positions = pl.DataFrame(
        [{"element_type": p["id"], "position": p["singular_name_short"]} for p in bootstrap["element_types"]]
    )
    events = bootstrap["events"]
    return (
        elements.with_columns(pl.col(c).cast(pl.Float64, strict=False) for c in FLOAT_STR_FIELDS)
        .with_columns(pl.col("chance_of_playing_next_round").cast(pl.Int32, strict=False))
        .join(teams, on="team", how="left")
        .join(positions, on="element_type", how="left")
        .with_columns(
            gw=pl.lit(current_gw(events), dtype=pl.Int32),
            gws_finished=pl.lit(gws_finished(events), dtype=pl.Int32),
            fetched_at=pl.lit(fetched_at.isoformat()),
        )
        .sort("id")
    )


def build_fixtures(fixtures: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(
        [{k: fx.get(k) for k in FIXTURE_FIELDS} for fx in fixtures],
        schema_overrides={
            "event": pl.Int32,
            "team_h_score": pl.Int32,
            "team_a_score": pl.Int32,
            "team_h_difficulty": pl.Int32,
            "team_a_difficulty": pl.Int32,
        },
    )


def build_events(events: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(
        [{k: ev.get(k) for k in EVENT_FIELDS} for ev in events],
        schema={"id": pl.Int32, "deadline_time": pl.String, "finished": pl.Boolean,
                "is_current": pl.Boolean, "is_next": pl.Boolean},
    )


def build_history(summaries: dict[int, dict]) -> pl.DataFrame:
    rows = [{k: h.get(k) for k in HISTORY_FIELDS} for s in summaries.values() for h in s.get("history", [])]
    if not rows:
        return pl.DataFrame(schema={k: pl.Int64 for k in HISTORY_FIELDS} | {"kickoff_time": pl.String})
    return pl.DataFrame(rows)


# ------------------------------------------------------------------------- CLI


def snapshot_path(out_dir: Path, gw: int, kind: str = "") -> Path:
    return out_dir / f"gw{gw}{'.' + kind if kind else ''}.parquet"


def run(
    out_dir: Path = SNAPSHOT_DIR,
    force: bool = False,
    history: bool = False,
    concurrency: int = DEFAULT_CONCURRENCY,
    transport: httpx.BaseTransport | None = None,
) -> Path | None:
    """Devuelve la ruta del snapshot escrito, o None si ya existía (sin --force)."""
    with httpx.Client(headers=HEADERS, timeout=TIMEOUT_S, transport=transport) as client:
        bootstrap, fixtures = fetch_core(client)

    gw = current_gw(bootstrap["events"])
    path = snapshot_path(out_dir, gw)
    if path.exists() and not force:
        print(f"{path} ya existe; usa --force para sobrescribir.")
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    players = build_snapshot(bootstrap, datetime.now(UTC))
    players.write_parquet(path)
    build_fixtures(fixtures).write_parquet(snapshot_path(out_dir, gw, "fixtures"))
    build_events(bootstrap["events"]).write_parquet(snapshot_path(out_dir, gw, "events"))
    print(f"GW{gw}: {players.height} jugadores → {path}")

    if history:
        summaries = asyncio.run(fetch_histories(players["id"].to_list(), concurrency))
        hist = build_history(summaries)
        hist.write_parquet(snapshot_path(out_dir, gw, "history"))
        print(f"  history: {hist.height} filas")
    return path


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true", help="sobrescribe el snapshot de la GW actual")
    ap.add_argument("--history", action="store_true", help="descarga element-summary de cada jugador")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="peticiones simultáneas (5-8)")
    ap.add_argument("--out-dir", type=Path, default=SNAPSHOT_DIR)
    args = ap.parse_args(argv)
    run(args.out_dir, args.force, args.history, args.concurrency)


if __name__ == "__main__":
    main()
