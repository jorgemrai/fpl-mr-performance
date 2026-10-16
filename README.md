# Mr FPL Performance

Compara jugadores de la Fantasy Premier League con radares de percentiles por posición.
Páginas: tabla de jugadores, `/compare` (radar de 2-4 jugadores) y `/captain` (capitán sugerido:
rival + forma + titularidad, pesos arbitrarios en `config/captain.yml`; no garantiza resultado).

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

## Despliegue (GitHub Pages)

1. *Settings → Pages → Source: **GitHub Actions***.
2. Lanza **Update FPL data** (`update.yml`) a mano la primera vez. Hace ingest + export, commitea
   `data/snapshots/` y `web/public/data/` y llama a **Deploy to GitHub Pages** (`deploy.yml`) al terminar.
3. A partir de ahí corre a diario (06:17 UTC). `deploy.yml` también se ejecuta en cada push a `main`.

Solo se publica `web/out` (HTML + JSON). Los snapshots Parquet se quedan en el repo.
El `basePath` se calcula a partir del nombre del repo (`/<repo>`).

¿Quieres aportar? Lee [CONTRIBUTING.md](CONTRIBUTING.md).

Más detalle de convenciones y arquitectura en [CLAUDE.md](CLAUDE.md). Siguientes fases en [BACKLOG.md](BACKLOG.md).

---

Proyecto no oficial, sin afiliación con la Premier League ni con Fantasy Premier League.
