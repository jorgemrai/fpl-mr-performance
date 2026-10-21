"""Construye el ranking del capitán sobre los fixtures reales GW6 igual que `export.run`.

Uso: `uv run python -m tests.golden_captain` regenera tests/fixtures/golden/captain_gw6.json.
Solo debe regenerarse cuando un cambio de fórmula o de filtros sea intencionado.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from pipeline import captain, export, ingest
from pipeline.metrics.defcon import defcon_thresholds

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = FIXTURES / "golden" / "captain_gw6.json"


def real_inputs():
    bootstrap = json.loads((FIXTURES / "bootstrap-static.json").read_text())
    fixtures_json = json.loads((FIXTURES / "fixtures.json").read_text())
    players = ingest.build_snapshot(bootstrap, datetime(2026, 10, 15, tzinfo=UTC))
    fixtures = ingest.build_fixtures(fixtures_json)
    nxt = ingest.next_gw(bootstrap["events"])
    thresholds, _ = defcon_thresholds(bootstrap.get("game_config") or {}, ROOT / "config" / "metrics.yml")
    table = export.build_table(
        players, fixtures, stats=ingest.build_fixture_stats(fixtures_json), next_gw=nxt, thresholds=thresholds
    )
    return table, fixtures, nxt


def snapshot() -> dict:
    table, fixtures, gw = real_inputs()
    cfg = captain.load_config(ROOT / "config" / "captain.yml")
    ranked, discarded = captain.rank(table, fixtures, gw, cfg)
    cap, vice = captain.pick_captain_vice(ranked)
    return {
        "gw": gw,
        "ranked": [[pid, round(s, 6)] for pid, s in ranked.select("id", "score").rows()],
        "captain": cap,
        "vice": vice,
        "discarded": sorted(discarded["id"].to_list()),
    }


if __name__ == "__main__":
    GOLDEN.write_text(json.dumps(snapshot(), separators=(",", ":")))
    print(f"golden → {GOLDEN}")
