# BACKLOG (fuera del MVP — no implementar todavía)

## Fase 2 — Más contexto
- Dificultad de calendario (FDR) de las próximas 5 GW por jugador.
- Evolución por GW (sparklines) a partir de los snapshots históricos.
- Forma real de 3 GW usando `--history` (element-summary) como eje opcional del radar.
- Métricas defensivas (CS/90, goles encajados/90, saves/90 para GKP).

## Fase 3 — Producto
- Import de equipo por ID de manager (vía JSON pre-generado, sigue sin backend).
- Optimizador de transferencias / plantilla.
- Comparador por posición con presets ("mejores MID < 7.0").

## Fase 4 — Plataforma
- DuckDB-WASM para consultas en cliente sobre Parquet.
- Almacenamiento en AWS / base de datos externa.
- Auth y preferencias de usuario.
