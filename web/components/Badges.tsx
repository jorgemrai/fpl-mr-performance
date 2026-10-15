import type { Player } from "@/lib/data";
import { STATUS_LABELS } from "@/lib/format";

const SHORT: Record<string, string> = { a: "OK", d: "Duda", i: "Les.", s: "Sanc.", u: "No disp.", n: "No disp." };

/** Badge por status FPL con news en el tooltip. "a" sin probabilidad (null) = sin alerta. */
export function StatusBadge({ p }: { p: Player }) {
  const alert = p.status !== "a" || (p.chance !== null && p.chance < 100);
  const title = [STATUS_LABELS[p.status] ?? p.status, p.chance !== null ? `${p.chance}% de jugar` : null, p.news]
    .filter(Boolean)
    .join(" · ");
  if (!alert) {
    return (
      <span className="status status-a" title={title}>
        {SHORT.a}
      </span>
    );
  }
  const cls = p.status === "a" ? "d" : p.status;
  return (
    <span className={`status status-${cls}`} title={title}>
      {SHORT[cls] ?? cls}
      {p.chance !== null && p.chance < 100 ? ` ${p.chance}%` : ""}
    </span>
  );
}

/** Próximos partidos coloreados por dificultad oficial (1 fácil – 5 difícil). */
export function RivalChips({ p }: { p: Player }) {
  if (p.next.length === 0) return <span className="muted">—</span>;
  return (
    <span className="rivals">
      {p.next.map((f) => (
        <span
          key={`${f.gw}-${f.opp}`}
          className={`fdr fdr-${f.d}`}
          title={`GW${f.gw} · ${f.opp} ${f.home ? "local" : "visitante"} · dificultad ${f.d}`}
        >
          {f.opp}
          <small>{f.home ? "L" : "V"}</small>
        </span>
      ))}
    </span>
  );
}
