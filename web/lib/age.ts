// Edad de un jugador en una fecha de referencia (lógica pura, se testea con `node --test`).

export const U23_MAX_AGE = 23;

/** Años cumplidos en `ref` (UTC). null si la fecha de nacimiento falta o no es válida. */
export function ageAt(born: string | null | undefined, ref: Date): number | null {
  if (!born || !/^\d{4}-\d{2}-\d{2}$/.test(born)) return null;
  const [y, m, d] = born.split("-").map(Number);
  let age = ref.getUTCFullYear() - y;
  const beforeBirthday = ref.getUTCMonth() + 1 < m || (ref.getUTCMonth() + 1 === m && ref.getUTCDate() < d);
  if (beforeBirthday) age -= 1;
  return age;
}

/** Regla "Wonderkids": 23 años o menos en el deadline. Sin fecha de nacimiento → false (no se puede saber). */
export function isU23(born: string | null | undefined, deadline: Date): boolean {
  const age = ageAt(born, deadline);
  return age !== null && age <= U23_MAX_AGE;
}

/** Deadline de referencia: el de la próxima GW; si no hay (fin de temporada), hoy. */
export function referenceDeadline(
  deadlines: { gw: number; deadline: string | null }[] | undefined,
  nextGw: number | null | undefined,
  now: Date = new Date(),
): { date: Date; gw: number | null } {
  const d = deadlines?.find((x) => x.gw === nextGw)?.deadline;
  return d ? { date: new Date(d), gw: nextGw ?? null } : { date: now, gw: null };
}

/** Deja el primero de cada club, respetando el orden recibido (el orden de la tabla). */
export function onePerClub<T extends { team: string }>(rows: T[]): T[] {
  const seen = new Set<string>();
  return rows.filter((r) => (seen.has(r.team) ? false : (seen.add(r.team), true)));
}
