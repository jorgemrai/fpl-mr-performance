# Cómo contribuir a Mr FPL Performance

¡Gracias por querer aportar! Este proyecto es una app **100% estática** (GitHub Pages) que compara
jugadores de la Fantasy Premier League. Antes de abrir un PR, lee estas reglas: son pocas y existen
para que el sitio siga siendo simple, gratis y seguro.

> Proyecto no oficial, sin afiliación con la Premier League ni con Fantasy Premier League.

## Arquitectura (no se negocia)

```
GitHub Actions (cron) → pipeline/ (Python) → web/public/data/*.json → Next.js export → GitHub Pages
```

- **Sin backend, sin API propia, sin base de datos.** El navegador solo lee JSON estáticos.
- El navegador **nunca** llama a la API de la FPL (CORS). Solo el pipeline de Python, en Actions o en local.
- Todo lo que quede fuera de esto (optimizador, login, import de equipo, bases de datos, nubes de pago…)
  va como propuesta a [`BACKLOG.md`](BACKLOG.md) o a un issue, no a un PR.

Las convenciones completas (métricas, percentiles, diseño) están en [`CLAUDE.md`](CLAUDE.md).

## Puesta en marcha

Requisitos: Python 3.12 con [uv](https://docs.astral.sh/uv/) y Node 22.

```bash
make install          # uv sync + npm ci
make test             # pytest, sin red (usa tests/fixtures/)
make ingest export    # baja datos reales de la FPL y genera web/public/data/*.json
make dev              # http://localhost:3000
```

## Antes de abrir un PR

1. **Abre un issue primero** si el cambio es grande (métrica nueva, página nueva, cambio de diseño).
2. **Tests en verde:** `make test`, `make test-web` y `cd web && npm run build` (incluye el chequeo de
   tipos). El workflow **CI** los ejecuta en cada PR.
3. **Métricas nuevas = función pura + test.** Van en `pipeline/metrics/`, sin I/O, con un test que use
   los JSON **reales** de `tests/fixtures/` o un DataFrame mínimo inline. No inventes datos de jugadores.
4. **Divisiones por cero → `null`**, nunca `inf`. Menos de 90 minutos → métricas /90 en `null`.
5. **PRs pequeños y enfocados**, un tema por PR, con commits en imperativo.

### No incluyas en tu PR

- **Datos generados:** `data/snapshots/*` ni `web/public/data/*.json`. Los regenera el bot cada día;
  si los tocas, habrá conflictos. Si necesitas datos para probar, genéralos en local y no los commitees.
- **Secretos de ningún tipo:** API keys, tokens, contraseñas, `.env`. El proyecto no los necesita.
- **Datos personales:** nada de IDs de managers, nombres de equipos de usuarios ni emails.
- **Logos, escudos o la fuente oficial de la Premier League.** Solo se usan los colores de `theme.css`.

## Diseño

- Todos los colores son variables CSS en [`web/styles/theme.css`](web/styles/theme.css). **Nunca** un hex
  dentro de un componente.
- El texto tiene que cumplir contraste **WCAG AA (≥ 4.5:1)**. El rosa no sirve como color de texto sobre
  el morado: úsalo solo como fondo o acento.
- Tipografía: Inter (Google Fonts).

## Cambios en `.github/workflows/`

Los workflows corren con permiso de escritura sobre el repo y sobre Pages **después del merge**.
Cualquier PR que los modifique recibe una revisión más estricta. No añadas triggers `pull_request_target`
ni `workflow_run`, ni pasos que descarguen y ejecuten scripts de terceros.

## Seguridad

Si encuentras una vulnerabilidad, **no abras un issue público**: usa
[*Report a vulnerability*](../../security/advisories/new) en la pestaña *Security* del repositorio.

## Licencia

El repositorio todavía no tiene un archivo `LICENSE`. Hasta que lo tenga, abre un issue antes de
contribuir código de cierto tamaño.
