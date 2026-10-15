"use client";

import PlayerTable from "@/components/PlayerTable";
import { useMeta, usePlayers } from "@/lib/data";

export default function Home() {
  const { data: players, error } = usePlayers();
  const { data: meta } = useMeta();
  return (
    <>
      <h1>Jugadores</h1>
      <p className="muted">Métricas de la temporada actual. Ordena por cualquier columna y filtra por posición, equipo o precio.</p>
      {error && <p className="alert">No se pudieron cargar los datos ({error}). ¿Has ejecutado `make ingest export`?</p>}
      {!players && !error && <p className="muted">Cargando…</p>}
      {players && <PlayerTable players={players} meta={meta} />}
    </>
  );
}
