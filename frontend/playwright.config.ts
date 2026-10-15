import { defineConfig, devices } from "@playwright/test";
import casasFile from "./data/casas.json";

// Todas as casas num só servidor, como em produção: a raiz em /, as demais em /<slug>/ (scripts/build-all.sh).
// metadata.prefix diz a cada projeto onde mora a sua casa.
const desktop = { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } };
// Palco mínimo do site (1280×720): abaixo disso a página rola, o layout não cede.
const minimo = { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 720 } };

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: {
    timeout: 10_000
  },
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure"
  },
  webServer: {
    // Os testes rodam na raiz; o deploy em g0v.tomoyo.systems usa ROOT=/assembleias.
    command: "ROOT= sh scripts/build-all.sh && npx serve out-all -l 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    timeout: 300_000
  },
  projects: casasFile.casas.flatMap((casa) => {
    const metadata = { prefix: casa.root ? "" : `/${casa.slug}`, uf: casa.uf, nome: `${casa.sigla} · ${casa.estado}` };
    return [
      { name: `${casa.slug}-desktop`, use: desktop, metadata },
      { name: `${casa.slug}-min`, use: minimo, metadata }
    ];
  })
});
