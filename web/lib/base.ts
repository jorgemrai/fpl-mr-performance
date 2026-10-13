/** Prefija el basePath (/<repo> en GitHub Pages). Úsalo en TODOS los fetch de JSON. */
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export function withBase(path: string): string {
  return `${BASE_PATH}${path.startsWith("/") ? path : `/${path}`}`;
}
