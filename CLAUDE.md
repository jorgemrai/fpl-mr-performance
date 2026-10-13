# CLAUDE.md — FPL Radar

App estática (GitHub Pages) que compara jugadores de la FPL con radares de percentiles.
**Sin backend.** Proyecto no oficial, sin afiliación con la Premier League ni con Fantasy Premier League.

## Arquitectura (no cambiar)

```
GitHub Actions (cron) ──> pipeline/ (Python) ──> web/public/data/*.json ──> Next.js export ──> Pages
                          ingest → metrics → export
```

- Python (ingesta + métricas) corre **solo** en GitHub Actions o en local.
- Next.js con `output: 'export'` + Recharts. Lee JSON estáticos de `/data/*.json`.
- No hay API ni servidor. El navegador **nunca** llama a la API de la FPL (CORS).
- Los snapshots Parquet (`data/snapshots/`) se versionan en el repo pero **no** se publican en Pages.

## Estructura

```
pipeline/
  ingest.py          # bootstrap-static + fixtures → data/snapshots/gw{N}*.parquet  (--force, --history)
  export.py          # snapshot → web/public/data/players.json + meta.json
  metrics/
    core.py          # funciones puras: ppm, per90, minutes_pct, team_games_finished, form
    percentiles.py   # umbral de minutos + percentil dentro de la posición (GKP/DEF/MID/FWD)
tests/
  fixtures/          # JSON reales de la API subidos por el usuario (tests sin red)
data/snapshots/      # gw{N}.parquet, gw{N}.fixtures.parquet, gw{N}.history.parquet (no se despliega)
web/
  styles/theme.css   # ÚNICO sitio con colores (variables CSS)
  app/               # page.tsx (tabla), compare/page.tsx (radar)
  components/
  lib/
  public/data/       # players.json, meta.json (generados)
.github/workflows/   # update.yml (cron), deploy.yml (Pages)
Makefile
BACKLOG.md           # fases 2-4, no se implementan
```

## Convenciones

### Python
- Python 3.12, gestionado con `uv` (`pyproject.toml` en la raíz, `uv.lock` versionado). HTTP con `httpx`.
- Polars para transformaciones; DuckDB para exploración ad-hoc de snapshots (`make sql`). No pandas.
- Métricas = **funciones puras** sobre `pl.Expr`/`pl.DataFrame`, sin I/O, cada una con test.
- Red solo en `ingest.py`. Reintentos con backoff exponencial ante 429/5xx (503 incluido).
- Idempotencia: si `gw{N}.parquet` existe, no se sobrescribe salvo `--force`.
- `pytest` sin red: usa los JSON **reales** de `tests/fixtures/` (no se inventan datos;
  los unit tests de métricas usan DataFrames mínimos inline).
- Divisiones por cero → `null`, nunca `inf`. Jugadores con < 90 min → métricas /90 `null`.

### Métricas (por jugador, temporada actual)
| Métrica      | Definición                                                         |
|--------------|--------------------------------------------------------------------|
| `ppm`        | `total_points / (now_cost / 10)`                                   |
| `pts90`      | `total_points / minutes * 90`                                      |
| `xgi90`      | `expected_goal_involvements / minutes * 90`                        |
| `min_pct`    | `minutes / (90 * GWs jugadas por su equipo)`                       |
| `bps`        | `bps` total de la temporada                                        |
| `form`       | campo `form` de la FPL. Etiqueta en UI: **"Forma (30d)"**          |

- "GWs jugadas por su equipo" = fixtures con `finished == true` donde el equipo es local o visitante.
- `--history` (off por defecto) descarga `element-summary/{id}` con concurrencia 6 y reintentos →
  `gw{N}.history.parquet`. Si existe, export añade `form3` (media de las 3 últimas GW). No es eje del radar.

Percentiles: rango 0-100 **dentro de la posición**, solo entre jugadores con
`minutes >= max(270, 0.25 * 90 * GW_jugadas)` (constantes en `metrics/percentiles.py`;
`GW_jugadas` = eventos con `finished == true`). Se calculan en Python y se exportan ya hechos.

### Front
- Next.js (App Router) + TypeScript estricto + Recharts. `output: 'export'`, `images.unoptimized = true`,
  `basePath` = `/<repo>` vía env `NEXT_PUBLIC_BASE_PATH` (vacío en local).
- Todo `fetch` de JSON pasa por `withBase()` (`web/lib/base.ts`). Nunca rutas absolutas a mano.
- Estado de comparación en la URL: `/compare?ids=1,2,3` (2-4 ids). La URL es la fuente de verdad.
- Sin librerías de estado, sin CSS-in-JS. CSS plano + variables.
- `players.json` < 2 MB: claves cortas, números redondeados a 1-2 decimales.

### Diseño
- **Todos** los colores como variables CSS en `web/styles/theme.css`. Nunca hex en componentes.
  - `--pl-purple #37003c` fondo/header · `--pl-purple-mid #5a1a63` tarjetas/hover
  - `--pl-green #00ff85` acento primario · `--pl-pink #e90052` secundario/alertas
  - `--pl-cyan #04f5ff` links · `--pl-white #ffffff` texto
- Tema oscuro por defecto. Contraste texto ≥ 4.5:1 (WCAG AA).
- Radar: series verde, rosa, cian, blanco; relleno 25% opacidad, borde sólido 2px.
- Tabla: header `--pl-purple`, filas alternas `--pl-purple-mid`, hover con borde izquierdo verde.
- Tipografía: Inter (Google Fonts). Prohibido: fuente propietaria PL, logo, león, escudos.
- Footer y README: "Proyecto no oficial, sin afiliación con la Premier League ni con Fantasy Premier League."

### Proceso
- Lo más simple que funcione. Nada fuera de alcance (optimizador, auth, import de equipo,
  DuckDB-WASM, AWS, BBDD externa) → `BACKLOG.md`.
- Commits pequeños, uno por paso del plan. Mensajes en imperativo: `Step N: ...`.
- Antes de commitear: `make test` (pytest) y `npm run build` (front) en verde.

## Comandos

```
make install   # uv sync + npm ci
make ingest    # descarga GW actual → data/snapshots/   (FORCE=1 sobrescribe, HISTORY=1 element-summary)
make export    # genera web/public/data/{players,meta}.json
make test      # pytest
make dev       # next dev en localhost:3000
make build     # next build (export estático a web/out)
make sql       # resumen de snapshots con DuckDB
```

## Plan (MVP)

1. **Scaffold + CLAUDE.md + BACKLOG.md** — `pyproject.toml` (uv), `Makefile`, `.gitignore`, README con disclaimer.
2. **Ingesta** — `ingest.py` con reintentos y `--force`; snapshot `gw{N}.parquet`; fixtures JSON para tests; tests de idempotencia y reintentos (mock HTTP).
3. **Métricas + percentiles** — `metrics/core.py` y `metrics/percentiles.py`, funciones puras con tests unitarios.
4. **Export** — `export.py` → `players.json` + `meta.json`; test de esquema y tamaño < 2 MB.
5. **Front: tema + tabla** — Next.js export, `theme.css`, tabla filtrable (posición, precio, equipo) y ordenable, footer.
6. **Front: /compare** — buscador de 2-4 jugadores, radar Recharts con percentiles, sincronizado con `?ids=`.
7. **CI/CD** — `update.yml` (cron diario + dispatch, `permissions: contents: write`: ingest + export + commit)
   que llama a `deploy.yml` vía `workflow_call` al terminar (un push con `GITHUB_TOKEN` no dispara otros
   workflows). `deploy.yml` también corre en push a `main`; publica solo `web/out`.

## Notas del entorno
- El sandbox de desarrollo de Claude no tiene salida a `fantasy.premierleague.com` (proxy 403).
  Los datos reales los genera `update.yml` en GitHub Actions; en local de Claude se valida con fixtures.
