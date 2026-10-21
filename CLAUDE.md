# CLAUDE.md — Mr FPL Performance

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
  export.py          # snapshot → web/public/data/players.json + meta.json + captain.json
  captain.py         # capitán sugerido: FDR, filtro de titularidad, score, capitán/vice (puro)
  metrics/
    core.py          # funciones puras: ppm, per90, minutes_pct, defcon90, availability_chance…
    defcon.py        # umbral DefCon (game_config → config/metrics.yml) y frecuencia DefCon
    fixtures.py      # facilidad del rival en las próximas 3 GW
    ownership.py     # Δ ownership vs snapshot anterior
    percentiles.py   # grupo (posición, status != "u", minutos ≥ umbral), percentil, n, ICT rank
tests/
  fixtures/          # JSON reales de la API subidos por el usuario (tests sin red)
config/
  captain.yml        # pesos (arbitrarios) y umbrales del capitán sugerido
  metrics.yml        # umbral DefCon por posición si game_config no lo trae
  radar.yml          # ejes por defecto / opcionales / máximo del radar
data/snapshots/      # gw{N}.parquet, gw{N}.{fixtures,events,stats,history}.parquet, gw{N}.game_config.json
web/
  styles/theme.css   # ÚNICO sitio con colores (variables CSS)
  app/               # page.tsx (tabla), compare/page.tsx (radar), captain/page.tsx
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
| `bps90`      | `bps / minutes * 90` (sustituye al BPS acumulado)                  |
| `form`       | campo `form` de la FPL. Etiqueta en UI: **"Forma (30d)"**          |
| `ict`        | `ict_index`; en tabla se muestra el puesto dentro del grupo ("#12 de 91"), no el ranking de la API |
| `defcon90`   | `defensive_contribution / minutes * 90` (== `defensive_contribution_per_90`). Portero: null |
| `defcon_freq`| partidos con DefCon ≥ umbral (fixtures[].stats) / `starts`, tope 100%. Portero: null. Aproximación: un suplente que cruza el umbral suma arriba y no abajo |
| `ease`       | promedio de (5 - dificultad oficial) de sus partidos en las próximas 3 GW; blank no cuenta |
| `own`        | `selected_by_percent`; Δ en p.p. vs el snapshot anterior solo si existe |

- "GWs jugadas por su equipo" = fixtures con `finished == true` donde el equipo es local o visitante.
- `--history` (off por defecto) descarga `element-summary/{id}` con concurrencia 6 y reintentos →
  `gw{N}.history.parquet`. Si existe, export añade `form3` (media de las 3 últimas GW). No es eje del radar.

Percentiles: rango 0-100 **dentro del grupo** = misma posición, `status != "u"` y
`minutes >= max(270, 0.25 * 90 * GW_jugadas)` (constantes en `metrics/percentiles.py`;
`GW_jugadas` = eventos con `finished == true`). Se exporta `n` (tamaño del grupo); si n < 30 el
front avisa "grupo pequeño: percentiles aproximados". Se calculan en Python y se exportan ya hechos.
Estado: `chance` = `chance_of_playing_next_round` si hay evento `is_next`, si no `this_round`; null = sin alerta.

### Capitán sugerido (`/captain`, `captain.json`)
- GW objetivo = evento con `is_next`. Rival en las próximas `horizon_gws` (1-3) GW con la dificultad
  oficial (`team_h_difficulty` / `team_a_difficulty`). DGW: `fdr` = suma de dificultades,
  `ease` = Σ(5 - dificultad), se marca `dgw`. Blank en la GW objetivo → fuera.
- Filtro de titularidad obligatorio: no portero, `status == "a"`, `chance_of_playing_next_round` null o ≥ umbral,
  `% minutos` ≥ umbral. Todos los que no pasan van a `discarded` con motivo (portero, lesión, duda,
  sanción, no disponible, pocos minutos, sin partido) y `discardedByReason` suma exactamente los excluidos.
- Score = media ponderada de percentiles **dentro de los candidatos** de forma, xGI/90 y `ease`.
  Pesos en `config/captain.yml`, iguales por defecto y **arbitrarios** (sin calibrar).
- Capitán = #1; vice = siguiente que no comparte ningún partido de la GW objetivo.
- Front: si la GW actual (según `meta.deadlines`) supera `meta.gw` en más de 1 → banner
  "Datos desactualizados" y no se muestra el ranking. Deadline en hora de Ecuador (UTC-5).

### Capitán filtrado por "mis jugadores" (`/captain`)
- Buscador en `/captain` para elegir jugadores (por `id`, nunca por `web_name`: hay 18 nombres repetidos).
  Con al menos uno elegido, el ranking muestra solo esos; con el filtro vacío, `/captain` se ve igual que siempre.
- **Misma fórmula y mismos filtros**: el score de un jugador es idéntico con o sin filtro, y los percentiles
  se calculan contra todo el universo de candidatos, nunca contra los elegidos.
- C/V entre los elegidos (el vice no comparte partido; si no hay alternativa se dice). Los elegidos que no son
  candidatos se listan con su motivo (porteros: "no aplica a capitán"; id inexistente: "sin datos").
  Línea "Tu mejor vs. el mejor global" con puesto y diferencia de score.
- **Privacidad:** la selección vive solo en el navegador (`localStorage` clave `mrp.captainFilter.v1`, en
  try/catch; si falla, estado en memoria). Nunca en el repo, la URL, logs ni analítica. Los enlaces a
  `/compare` solo llevan los 2-4 jugadores comparados.
- `captain.json` publica **todos** los candidatos (id, score, valor y percentil de forma / xGI/90 / ease,
  partidos `[fixture_id, opp, ha, diff]`, DGW) y **todos** los descartados (id, motivos, `news`, `chance`).
  `top` (top 5 + vice) no cambia. Claves cortas; < 150 KB sin comprimir.
- Lógica del cliente en un módulo puro (`web/lib/myCaptain.ts`) con tests `node --test`.

### Front
- Next.js (App Router) + TypeScript estricto + Recharts. `output: 'export'`, `images.unoptimized = true`,
  `basePath` = `/<repo>` vía env `NEXT_PUBLIC_BASE_PATH` (vacío en local).
- Todo `fetch` de JSON pasa por `withBase()` (`web/lib/base.ts`). Nunca rutas absolutas a mano.
- Estado de comparación en la URL: `/compare?ids=1,2,3&axes=ppm,form,…` (2-4 ids, 3-8 ejes de
  `config/radar.yml`). La URL es la fuente de verdad. Con un portero se ocultan los ejes DefCon con aviso.
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
7. **CI/CD** — `update.yml` (cron diario + dispatch: ingest + export + commit). Hace push a `main` con la
   deploy key (`secrets.DEPLOY_KEY`, bypass del ruleset); ese push dispara `deploy.yml` (on: push a `main`),
   que publica solo `web/out`.

## Notas del entorno
- El sandbox de desarrollo de Claude no tiene salida a `fantasy.premierleague.com` (proxy 403).
  Los datos reales los genera `update.yml` en GitHub Actions; en local de Claude se valida con fixtures.
