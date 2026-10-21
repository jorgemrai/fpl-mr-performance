import assert from "node:assert/strict";
import { test } from "node:test";
import type { CaptainCandidate, CaptainDiscard } from "./captain.ts";
import {
  STORAGE_KEY,
  filterCaptain,
  loadSelection,
  pickCaptainVice,
  saveSelection,
  scoreGap,
  type CaptainData,
  type KeyValueStore,
} from "./myCaptain.ts";

const GW = 7;
// [fixture_id, rival, H/A, dificultad, gw]
const cand = (i: number, s: number, fixtures: number[], extra: Partial<CaptainCandidate> = {}): CaptainCandidate => ({
  i,
  s,
  f: [5, 50],
  x: [0.3, 50],
  e: [3, 50],
  m: fixtures.map((fx) => [fx, "OPP", "H", 2, GW]),
  ...extra,
});

// Ranking global sintético (orden = puesto). 10 y 11 son compañeros (partido 100); 12 es su rival.
const CAP: CaptainData = {
  gw: GW,
  candidates: [
    cand(1, 91, [200]),
    cand(2, 88, [201]),
    cand(10, 78, [100]),
    cand(11, 75, [100]),
    cand(12, 70, [100]),
    cand(13, 66, [102, 103], { d: 1 }), // doble jornada
    cand(14, 60, [104]),
  ],
  discarded: [
    { i: 20, r: ["portero"] },
    { i: 21, r: ["duda"], n: "Knock - 50% chance of playing", c: 50 },
    { i: 22, r: ["lesión", "duda"], n: "Knee injury", c: 0 },
    { i: 23, r: ["sin partido"] }, // equipo en blanco
    { i: 24, r: ["no disponible", "pocos minutos"] },
  ],
};

function memoryStore(): KeyValueStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
    removeItem: (k) => void data.delete(k),
  };
}

const throwingStore: KeyValueStore = {
  getItem: () => {
    throw new Error("SecurityError");
  },
  setItem: () => {
    throw new Error("QuotaExceededError");
  },
  removeItem: () => {
    throw new Error("SecurityError");
  },
};

// ---------------------------------------------------------------- persistencia

test("guardar y leer devuelve los mismos ids (ida y vuelta) y solo usa la clave versionada", () => {
  const store = memoryStore();
  assert.equal(saveSelection(store, [411, 165, 411, 7]), true);
  assert.deepEqual(loadSelection(store), [411, 165, 7]);
  assert.deepEqual([...store.data.keys()], [STORAGE_KEY]);
  saveSelection(store, []);
  assert.equal(store.data.size, 0, "vaciar la selección borra la clave");
});

test("un storage que lanza excepción o datos corruptos no rompen nada", () => {
  assert.deepEqual(loadSelection(throwingStore), []);
  assert.equal(saveSelection(throwingStore, [1, 2]), false);
  assert.deepEqual(loadSelection(null), []);
  const store = memoryStore();
  store.data.set(STORAGE_KEY, "{no es json");
  assert.deepEqual(loadSelection(store), []);
  store.data.set(STORAGE_KEY, JSON.stringify(["411", -3, 2.5, 165]));
  assert.deepEqual(loadSelection(store), [165]);
});

// ------------------------------------------------------- mismo score / percentil

test("el score y los percentiles de cada jugador son idénticos con y sin filtro", () => {
  const f = filterCaptain(CAP, [14, 10, 2]);
  for (const r of f.ranking) {
    const global = CAP.candidates.find((c) => c.i === r.candidate.i)!;
    assert.equal(r.candidate.s, global.s);
    assert.deepEqual([r.candidate.f, r.candidate.x, r.candidate.e], [global.f, global.x, global.e]);
    assert.equal(r.globalRank, CAP.candidates.indexOf(global) + 1);
  }
  assert.deepEqual(
    f.ranking.map((r) => r.candidate.i),
    [2, 10, 14],
    "orden global, no el de selección",
  );
});

// ------------------------------------------------------------------------- vice

test("el vice nunca comparte partido con el capitán (compañero ni rival)", () => {
  const f = filterCaptain(CAP, [10, 11, 12, 14]);
  assert.equal(f.captainId, 10);
  assert.equal(f.viceId, 14, "11 (compañero) y 12 (rival) juegan el partido 100");
});

test("si todos comparten partido no se fuerza un vice: se explica", () => {
  const f = filterCaptain(CAP, [10, 11, 12]);
  assert.equal(f.captainId, 10);
  assert.equal(f.viceId, null);
  assert.match(f.viceNote ?? "", /mismo partido/);
  const one = filterCaptain(CAP, [10]);
  assert.equal(one.viceId, null);
  assert.match(one.viceNote ?? "", /un jugador elegible/);
});

test("doble jornada: cualquier partido compartido descarta como vice", () => {
  const dgwCap = cand(30, 99, [500, 501], { d: 1 });
  const shares = cand(31, 90, [501]);
  const free = cand(32, 80, [502]);
  assert.deepEqual(pickCaptainVice([dgwCap, shares, free], GW), { captainId: 30, viceId: 32, viceNote: null });
});

// ------------------------------------------------------------- listas exclusivas

test("cada jugador elegido aparece en exactamente una lista: ranking, descartados o sin datos", () => {
  const selected = [1, 13, 20, 21, 22, 23, 24, 999];
  const f = filterCaptain(CAP, selected);
  const buckets = [
    f.ranking.map((r) => r.candidate.i),
    f.discarded.map((d: CaptainDiscard) => d.i),
    f.noData,
  ];
  const all = buckets.flat();
  assert.equal(all.length, new Set(all).size, "sin solapes");
  assert.deepEqual([...all].sort((a, b) => a - b), [...selected].sort((a, b) => a - b), "sin huecos");
  assert.deepEqual(f.noData, [999]);
  assert.equal(f.discarded.find((d) => d.i === 20)?.r[0], "portero");
  assert.deepEqual(f.discarded.find((d) => d.i === 22)?.r, ["lesión", "duda"]);
});

test("doble jornada y blanco del equipo se reflejan", () => {
  const f = filterCaptain(CAP, [13, 23]);
  assert.equal(f.ranking[0].candidate.d, 1);
  assert.equal(f.ranking[0].candidate.m.length, 2);
  assert.deepEqual(f.discarded.map((d) => d.r[0]), ["sin partido"]);
});

test("dos jugadores con el mismo nombre se distinguen por id", () => {
  // En GW6 hay 18 web_name repetidos: la selección es por id, el nombre no interviene.
  const f = filterCaptain(CAP, [11]);
  assert.deepEqual(f.ranking.map((r) => r.candidate.i), [11]);
});

// ----------------------------------------------------------- mejor vs. global

test("tu mejor vs. el mejor global: puesto y diferencia correctos", () => {
  const f = filterCaptain(CAP, [14, 11, 21]);
  assert.deepEqual(f.best, { id: 11, score: 75, rank: 4 });
  assert.deepEqual(f.globalBest, { id: 1, score: 91 });
  assert.equal(f.totalCandidates, 7);
  assert.equal(scoreGap(f), 16);
  const none = filterCaptain(CAP, [20, 21]);
  assert.equal(none.best, null);
  assert.equal(scoreGap(none), null);
});
