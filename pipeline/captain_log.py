"""Registro de la recomendación de capitán congelada en el deadline (para backtesting bajo demanda).

`data/captain_log/gw{N}.json` se sobrescribe en cada export mientras el deadline de la GW N no haya
pasado; después queda fijo = lo último que se publicó antes del deadline. No se despliega en Pages.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

LOG_COLS = ["id", "score", "form", "xgi90", "ease", "own"]


def is_before_deadline(deadline: str | None, now: datetime) -> bool:
    if not deadline:
        return False
    return now < datetime.fromisoformat(deadline.replace("Z", "+00:00"))


def build_log(cap: dict, table: pl.DataFrame, data_fetched_at: str | None) -> dict:
    """Ranking completo + lo necesario para comparar luego contra referencias simples (ownership, forma)."""
    own = dict(table.select("id", "own").iter_rows())
    xgi = dict(table.select("id", "xgi90").iter_rows())
    top = sorted(cap["top"], key=lambda t: t["rank"])
    role = {t["id"]: t["role"] for t in top}
    return {
        "gw": cap["gw"],
        "deadline": cap["deadline"],
        "dataFetchedAt": data_fetched_at,
        "weights": cap["weights"],
        "horizonGws": cap["horizonGws"],
        "minMinutesPct": cap["minMinutesPct"],
        "minChanceOfPlaying": cap["minChanceOfPlaying"],
        "captain": next((i for i, r in role.items() if r == "C"), None),
        "vice": next((i for i, r in role.items() if r == "V"), None),
        "top": [t["id"] for t in top],
        "cols": LOG_COLS,
        "candidates": [
            [c["i"], c["s"], c["f"][0], None if xgi.get(c["i"]) is None else round(xgi[c["i"]], 2), c["e"][0], own.get(c["i"])]
            for c in cap["candidates"]
        ],
        "discarded": [[d["i"], d["r"][0]] for d in cap["discarded"]],
    }


def write_log(
    cap: dict, table: pl.DataFrame, data_fetched_at: str | None, log_dir: Path, now: datetime | None = None
) -> Path | None:
    """Escribe gw{N}.json si aún no pasó el deadline de la GW objetivo; si pasó, no toca nada."""
    now = now or datetime.now(UTC)
    if cap.get("gw") is None or not is_before_deadline(cap.get("deadline"), now):
        return None
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"gw{cap['gw']}.json"
    path.write_text(json.dumps(build_log(cap, table, data_fetched_at), ensure_ascii=False, separators=(",", ":")))
    return path
