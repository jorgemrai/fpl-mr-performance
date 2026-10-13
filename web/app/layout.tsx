import type { Metadata } from "next";
import Link from "next/link";
import "@/styles/theme.css";
import "@/styles/app.css";
import Footer from "@/components/Footer";

export const metadata: Metadata = {
  title: "Mr FPL Performance",
  description: "Compara jugadores de la Fantasy Premier League con radares de percentiles por posición.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap"
        />
      </head>
      <body>
        <header className="site-header">
          <nav>
            <Link href="/" className="brand">
              Mr FPL <span>Performance</span>
            </Link>
            <Link href="/" className="nav-link">
              Jugadores
            </Link>
            <Link href="/compare/" className="nav-link">
              Comparar
            </Link>
          </nav>
        </header>
        <main>{children}</main>
        <Footer />
      </body>
    </html>
  );
}
