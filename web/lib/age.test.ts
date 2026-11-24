import assert from "node:assert/strict";
import { test } from "node:test";
import { ageAt, isU23, onePerClub, referenceDeadline } from "./age.ts";

const GW12 = new Date("2026-11-28T11:00:00Z");

test("edad en años cumplidos, contando si ya pasó el cumpleaños", () => {
  assert.equal(ageAt("2003-08-17", GW12), 23); // Cherki
  assert.equal(ageAt("2000-07-21", GW12), 26); // Haaland
  assert.equal(ageAt("2002-11-28", GW12), 24, "cumple 24 justo el día del deadline");
  assert.equal(ageAt("2002-11-29", GW12), 23, "cumple 24 al día siguiente");
});

test("U23 = 23 o menos en el deadline; sin fecha no cuenta", () => {
  assert.equal(isU23("2003-08-17", GW12), true);
  assert.equal(isU23("2002-11-29", GW12), true);
  assert.equal(isU23("2002-11-28", GW12), false);
  assert.equal(isU23(null, GW12), false);
  assert.equal(isU23("no-es-fecha", GW12), false);
});

test("el deadline de referencia es el de la próxima GW", () => {
  const deadlines = [
    { gw: 11, deadline: "2026-11-21T11:00:00Z" },
    { gw: 12, deadline: "2026-11-28T11:00:00Z" },
  ];
  assert.deepEqual(referenceDeadline(deadlines, 12), { date: GW12, gw: 12 });
  const now = new Date("2027-06-01T00:00:00Z");
  assert.deepEqual(referenceDeadline(deadlines, null, now), { date: now, gw: null });
});

test("uno por club conserva el mejor según el orden recibido", () => {
  const rows = [
    { id: 1, team: "BHA" },
    { id: 2, team: "MCI" },
    { id: 3, team: "BHA" },
    { id: 4, team: "ARS" },
    { id: 5, team: "MCI" },
  ];
  assert.deepEqual(onePerClub(rows).map((r) => r.id), [1, 2, 4]);
});
