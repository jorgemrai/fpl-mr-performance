"use client";

import Link from "next/link";
import { useCaptain, useMeta, type CaptainFixture, type CaptainPick } from "@/lib/data";
import { fmtPrice } from "@/lib/format";
import { isStale } from "@/lib/staleness";

const fmtFixture = (f: CaptainFixture) => `${f.opp} (${f.home ? "L" : "V"}) ${f.difficulty}`;
const fmtNum = (v: number | null, nd: number) => (v === null ? "–" : v.toFixed(nd));

function compareHref(pick: CaptainPick, captainId: number, viceId: number | undefined): string {
  const other = pick.id === captainId ? viceId : captainId;
  return `/compare/?ids=${[pick.id, other].filter(Boolean).join(",")}`;
}

function PickCard({ pick, captainId, viceId }: { pick: CaptainPick; captainId: number; viceId?: number }) {
  return (
    <article className={`card pick${pick.role ? ` pick-${pick.role.toLowerCase()}` : ""}`}>
      <header className="pick-head">
        <span className="pick-rank">#{pick.rank}</span>
        {pick.role && (
          <span className={`badge badge-${pick.role.toLowerCase()}`} title={pick.role === "C" ? "Capitán" : "Vicecapitán"}>
            {pick.role}
          </span>
        )}
        <div>
          <h2 className="pick-name">{pick.name}</h2>
          <p className="muted small">
            {pick.team} · {pick.pos} · {fmtPrice(pick.price)}
          </p>
        </div>
        {pick.dgw && <span className="tag">Doble jornada</span>}
      </header>
      <dl className="pick-stats">
        <div>
          <dt>Forma (30d)</dt>
          <dd>
            {fmtNum(pick.form, 1)} <span className="muted small">p{pick.pct.form}</span>
          </dd>
        </div>
        <div>
          <dt>xGI/90</dt>
          <dd>
            {fmtNum(pick.xgi90, 2)} <span className="muted small">p{pick.pct.xgi90}</span>
          </dd>
        </div>
        <div>
          <dt>Rival · dificultad</dt>
          <dd>
            {pick.fixtures.map(fmtFixture).join(" + ")}
            {pick.fixtures.length > 1 && <span className="muted small"> · FDR {pick.fdr}</span>}
          </dd>
        </div>
      </dl>
      <p className="pick-foot">
        <span className="muted small">Score {pick.score.toFixed(1)}</span>
        <Link href={compareHref(pick, captainId, viceId)}>Comparar en el radar →</Link>
      </p>
    </article>
  );
}

export default function CaptainView() {
  const { data: cap, error } = useCaptain();
  const { data: meta, error: metaError } = useMeta();

  if (error || metaError) return <p className="alert">No se pudieron cargar los datos ({error ?? metaError}).</p>;
  if (!cap || !meta) return <p className="muted">Cargando…</p>;

  if (isStale(meta)) {
    return (
      <p className="alert" role="alert">
        <strong>Datos desactualizados.</strong> Son de la GW {meta.gw} y ya han pasado más de una jornada; el ranking se
        oculta hasta la próxima actualización.
      </p>
    );
  }
  if (cap.gw === null || cap.top.length === 0) {
    return <p className="muted">No hay próxima jornada con candidatos (¿temporada terminada?).</p>;
  }

  const captainPick = cap.top.find((p) => p.role === "C")!;
  const vicePick = cap.top.find((p) => p.role === "V");
  const deadline = cap.deadline
    ? new Date(cap.deadline).toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" })
    : null;

  return (
    <>
      <p>
        <strong>GW {cap.gw}</strong>
        {deadline && <span className="muted"> · deadline {deadline}</span>}
        <span className="muted">
          {" "}
          · {cap.candidates} candidatos · rival en {cap.horizonGws === 1 ? "la próxima GW" : `las próximas ${cap.horizonGws} GW`}
        </span>
      </p>
      {vicePick && (
        <p>
          <Link className="btn" href={`/compare/?ids=${cap.top.slice(0, 4).map((p) => p.id).join(",")}`}>
            Comparar top 4 en el radar
          </Link>
        </p>
      )}
      <div className="picks">
        {cap.top.map((p) => (
          <PickCard key={p.id} pick={p} captainId={captainPick.id} viceId={vicePick?.id} />
        ))}
      </div>

      <h2>Descartados</h2>
      <p className="muted small">
        Filtro de titularidad: estado disponible, probabilidad de jugar ≥ {cap.minChanceOfPlaying}% (o sin aviso) y ≥{" "}
        {cap.minMinutesPct}% de los minutos posibles. Se listan los {cap.discarded.length} con más puntos.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {["Jugador", "Equipo", "Pos", "Motivo"].map((h) => (
                <th key={h}>
                  <span className="th-label">{h}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cap.discarded.map((d) => (
              <tr key={d.id}>
                <td>{d.name}</td>
                <td>{d.team}</td>
                <td>{d.pos}</td>
                <td>{d.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="muted small">
        Score = media ponderada de percentiles dentro de los candidatos (forma {cap.weights.form} · xGI/90{" "}
        {cap.weights.xgi90} · facilidad del rival {cap.weights.ease}). Los pesos son arbitrarios, no están calibrados
        (config/captain.yml). Rival: L = local, V = visitante; dificultad oficial FPL 1 (fácil) – 5 (difícil).
      </p>
    </>
  );
}
