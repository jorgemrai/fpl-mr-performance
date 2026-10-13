import CaptainView from "@/components/CaptainView";

export const metadata = { title: "Capitán · Mr FPL Performance" };

export default function CaptainPage() {
  return (
    <>
      <h1>Capitán sugerido</h1>
      <p className="disclaimer">Ranking por proceso (rival + forma + titularidad), no garantiza resultado.</p>
      <CaptainView />
    </>
  );
}
