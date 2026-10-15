import type { MetadataRoute } from "next";

export const dynamic = "force-static";

const baseUrl = `https://g0v.tomoyo.systems${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}`;
const routes = ["/", "/votacoes/", "/presenca/", "/partidos/", "/metodologia/"];

export default function sitemap(): MetadataRoute.Sitemap {
  return routes.map((route) => ({ url: `${baseUrl}${route}`, changeFrequency: "daily", priority: route === "/" ? 1 : 0.8 }));
}
