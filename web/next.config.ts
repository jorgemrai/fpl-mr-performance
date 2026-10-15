import type { NextConfig } from "next";

// En GitHub Pages la app vive en /<repo>; en local, en la raíz.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const nextConfig: NextConfig = {
  output: "export",
  basePath,
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
