import { expect, test, type TestInfo } from "@playwright/test";
import casasFile from "../data/casas.json";

const pages = ["/", "/votacoes", "/presenca", "/partidos", "/metodologia"];

/** Endereço da tela na casa do projeto ("" = ALERJ, "/sp" = ALESP). */
function at(info: TestInfo, path: string): string {
  const prefix = String((info.project.metadata as { prefix?: string }).prefix ?? "");
  return `${prefix}${path === "/" ? "/" : `${path}/`}`;
}

test.describe("static pages", () => {
  for (const path of pages) {
    test(`${path} renders with visible content`, async ({ page }, info) => {
      const consoleErrors: string[] = [];
      page.on("console", (message) => {
        if (message.type() === "error") {
          consoleErrors.push(message.text());
        }
      });
      await page.goto(at(info, path));
      await expect(page.locator("main")).toBeVisible();
      await expect(page.getByRole("heading", { name: /404|not found/i })).toHaveCount(0);
      const screenshot = await page.locator("main").screenshot();
      expect(screenshot.length).toBeGreaterThan(12_000);
      expect(consoleErrors).toEqual([]);
    });
  }
});

test("screens fit the viewport without page scroll", async ({ page }, info) => {
  for (const path of pages) {
    await page.goto(at(info, path));
    await page.waitForLoadState("networkidle");
    const [scrollHeight, viewport] = await page.evaluate(() => [document.documentElement.scrollHeight, window.innerHeight]);
    expect(scrollHeight, `${path} deve caber na tela`).toBeLessThanOrEqual(viewport);
  }
});

test("a deputado's votes load on demand", async ({ page }, info) => {
  await page.goto(at(info, "/"));
  await page.waitForLoadState("networkidle");
  await expect.poll(async () => page.locator("table.ruled tbody tr").count(), { timeout: 15_000 }).toBeGreaterThan(0);
});

test("a votação lists who voted how", async ({ page }, info) => {
  await page.goto(at(info, "/votacoes"));
  await page.waitForLoadState("networkidle");
  await expect.poll(async () => page.locator("main ul li a").count(), { timeout: 15_000 }).toBeGreaterThan(10);
});

test("hotkeys switch screens", async ({ page }, info) => {
  await page.goto(at(info, "/"));
  await page.waitForLoadState("networkidle");
  await page.keyboard.press("2");
  await expect(page).toHaveURL(/\/votacoes/);
});

test("the casa select sits left of the theme button and u goes to the next casa", async ({ page }, info) => {
  const meta = info.project.metadata as { uf: string; nome: string };
  const list = casasFile.casas;
  const next = list[(list.findIndex((item) => item.uf === meta.uf) + 1) % list.length];
  await page.goto(at(info, "/votacoes"));
  await page.waitForLoadState("networkidle");
  const select = page.getByRole("combobox", { name: "Casa" });
  await expect(select.locator("option:checked")).toHaveText(meta.nome);
  const switchBox = await select.boundingBox();
  const themeBox = await page.getByRole("button", { name: /Usar tema/ }).boundingBox();
  expect(switchBox && themeBox && switchBox.x + switchBox.width <= themeBox.x).toBeTruthy();
  await page.keyboard.press("u");
  await expect(page).toHaveURL(new RegExp(`^http://127\\.0\\.0\\.1:4173${next.root ? "" : `/${next.slug}`}/votacoes/$`));
});

test("choosing a casa keeps the screen", async ({ page }, info) => {
  const meta = info.project.metadata as { uf: string };
  const other = casasFile.casas.find((item) => item.uf !== meta.uf)!;
  await page.goto(at(info, "/presenca"));
  await page.waitForLoadState("networkidle");
  await page.getByRole("combobox", { name: "Casa" }).selectOption(other.uf);
  await expect(page).toHaveURL(new RegExp(`${other.root ? "" : `/${other.slug}`}/presenca/$`));
});
