"""Fixtures compartidos. Los JSON reales de la API viven en tests/fixtures/:

- bootstrap-static.json   (GET /api/bootstrap-static/)
- fixtures.json           (GET /api/fixtures/)
- element-summary-*.json  (opcional, GET /api/element-summary/{id}/)
- fixtures_blank_gw8.json copia de fixtures.json editada a mano: el partido 72 (AVL-MCI, GW8)
                          pasa a event=null (aplazado) → blank de MCI y AVL en la GW8.
- gw05/bootstrap-static.json (opcional) bootstrap de la GW5 para el Δ de ownership.

Se puede apuntar a otro directorio con FPL_FIXTURES_DIR.
"""

import json
import os
from pathlib import Path

import httpx
import pytest

FIXTURES_DIR = Path(os.environ.get("FPL_FIXTURES_DIR", Path(__file__).parent / "fixtures"))


def _load(name: str):
    path = FIXTURES_DIR / name
    if not path.exists():
        pytest.skip(f"falta {path}: sube el JSON real de la API a tests/fixtures/")
    return json.loads(path.read_text())


@pytest.fixture(scope="session")
def bootstrap() -> dict:
    return _load("bootstrap-static.json")


@pytest.fixture(scope="session")
def fixtures_json() -> list:
    return _load("fixtures.json")


@pytest.fixture(scope="session")
def fixtures_blank_json() -> list:
    return _load("fixtures_blank_gw8.json")


@pytest.fixture(scope="session")
def bootstrap_gw05() -> dict:
    return _load("gw05/bootstrap-static.json")


@pytest.fixture
def fpl_transport(bootstrap, fixtures_json) -> httpx.MockTransport:
    """Simula la API de la FPL sirviendo los JSON guardados."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bootstrap-static/"):
            return httpx.Response(200, json=bootstrap)
        if request.url.path.endswith("/fixtures/"):
            return httpx.Response(200, json=fixtures_json)
        return httpx.Response(404)

    return httpx.MockTransport(handler)
