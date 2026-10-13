# FPL Radar

Compara jugadores de la Fantasy Premier League con radares de percentiles por posición.
App 100% estática (Next.js `output: 'export'`) hosteada en GitHub Pages. Sin backend.

```
GitHub Actions (cron) → Python (ingest + métricas) → JSON estáticos → Next.js → GitHub Pages
```

## Uso local

```bash
make install          # uv sync + npm ci
make ingest export    # baja datos de la FPL y genera web/public/data/*.json
make dev              # http://localhost:3000
make test             # pytest (sin red, con fixtures en tests/fixtures/)
```

Flags de ingesta: `make ingest FORCE=1` (sobrescribe el snapshot de la GW) y
`make ingest HISTORY=1` (descarga además `element-summary` de cada jugador).

Más detalle de convenciones y arquitectura en [CLAUDE.md](CLAUDE.md). Siguientes fases en [BACKLOG.md](BACKLOG.md).

---

Proyecto no oficial, sin afiliación con la Premier League ni con Fantasy Premier League.
