"""Regresión: el ranking global del capitán sobre GW6 no cambia (orden, scores, C/V, descartados)."""

import json

import pytest

from tests.golden_captain import GOLDEN, snapshot


def test_captain_ranking_matches_golden_gw6():
    golden = json.loads(GOLDEN.read_text())
    now = snapshot()
    assert now["gw"] == golden["gw"]
    assert [pid for pid, _ in now["ranked"]] == [pid for pid, _ in golden["ranked"]], "cambió el orden global"
    for (pid, s), (_, g) in zip(now["ranked"], golden["ranked"]):
        assert s == pytest.approx(g, abs=1e-6), f"cambió el score de {pid}: {g} → {s}"
    assert (now["captain"], now["vice"]) == (golden["captain"], golden["vice"])
    assert now["discarded"] == golden["discarded"]
