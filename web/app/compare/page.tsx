import { Suspense } from "react";
import CompareView from "@/components/CompareView";

export const metadata = { title: "Comparar · FPL Radar" };

export default function ComparePage() {
  return (
    <>
      <h1>Comparar jugadores</h1>
      <p className="muted">Radar de 2 a 4 jugadores. La selección se guarda en la URL: compártela tal cual.</p>
      <Suspense fallback={<p className="muted">Cargando…</p>}>
        <CompareView />
      </Suspense>
    </>
  );
}
