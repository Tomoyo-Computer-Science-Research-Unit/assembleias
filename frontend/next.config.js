// O site mora em g0v.tomoyo.systems/assembleias: a casa raiz (data/casas.json, root=true) em
// /assembleias e as demais em /assembleias/<slug>. NEXT_PUBLIC_UF escolhe a casa do build;
// NEXT_PUBLIC_BASE_PATH="" serve na raiz.
const { casas } = require("./data/casas.json");

const root = casas.find((item) => item.root) || casas[0];
const uf = (process.env.NEXT_PUBLIC_UF || root.uf).toUpperCase();
const casa = casas.find((item) => item.uf.toUpperCase() === uf) || root;
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? (casa.root ? "/assembleias" : `/assembleias/${casa.slug}`);

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  basePath,
  assetPrefix: basePath || undefined,
  trailingSlash: true,
  images: {
    unoptimized: true
  },
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
    NEXT_PUBLIC_UF: casa.uf.toUpperCase()
  }
};

module.exports = nextConfig;
