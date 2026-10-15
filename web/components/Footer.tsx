"use client";

import { useMeta } from "@/lib/data";

export default function Footer() {
  const { data: meta } = useMeta();
  const updated = meta ? new Date(meta.dataFetchedAt).toLocaleString("es-ES", { dateStyle: "medium", timeStyle: "short" }) : null;
  return (
    <footer className="site-footer">
      {meta && (
        <p>
          GW {meta.gw} · Datos actualizados: {updated}
        </p>
      )}
      <p>Proyecto no oficial, sin afiliación con la Premier League ni con Fantasy Premier League.</p>
    </footer>
  );
}
