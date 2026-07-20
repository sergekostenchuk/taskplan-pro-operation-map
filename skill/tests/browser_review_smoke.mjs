#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";


const [htmlPath, outputDirectory, manifestPath] = process.argv.slice(2);
if (!htmlPath || !outputDirectory) {
  console.error("Usage: node tests/browser_review_smoke.mjs <review.html> <output-dir>");
  process.exit(2);
}

const result = { checks: {}, screenshots: {}, errors: [] };
const check = (name, condition, detail = "") => {
  result.checks[name] = { passed: Boolean(condition), detail };
  if (!condition) throw new Error(`${name}: ${detail}`);
};

fs.mkdirSync(outputDirectory, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
  await page.goto(pathToFileURL(path.resolve(htmlPath)).href);
  await page.waitForSelector("#overviewGraph .overview-node");
  const expected = await page.evaluate(() => JSON.parse(document.querySelector("#graph-data").textContent).blocks.length);
  const expectedGroups = await page.evaluate(() => JSON.parse(document.querySelector("#presentation-data").textContent).overview_groups.length);
  check("overview_has_all_blocks", await page.locator("#overviewGraph .overview-node").count() === expected, `expected=${expected}`);
  check("overview_inspector_collapsed", await page.locator("body.inspector-collapsed").count() === 1);
  check("overview_has_configured_lanes", await page.locator("#overviewGraph .overview-lane").count() === expectedGroups, `expected=${expectedGroups}`);
  await page.locator(".overview-panel").screenshot({ path: path.join(outputDirectory, "overview-pipeline-main.png") });
  result.screenshots.pipeline = path.join(outputDirectory, "overview-pipeline-main.png");
  await page.locator("#allRelationsMode").click();
  check("all_relations_mode", await page.locator("#allRelationsMode.active").count() === 1);
  await page.screenshot({ path: path.join(outputDirectory, "overview-desktop-1280x800.png") });
  result.screenshots.desktop = path.join(outputDirectory, "overview-desktop-1280x800.png");

  const locales = await page.locator("#languageSelect option").evaluateAll(options => options.map(option => option.value));
  const inspectionLocale = locales.includes("en") ? "en" : locales[0];
  await page.selectOption("#languageSelect", inspectionLocale);
  await page.waitForFunction(locale => document.documentElement.lang === locale, inspectionLocale);
  check("configured_locale_ui", await page.locator("html").getAttribute("lang") === inspectionLocale, inspectionLocale);

  const firstBlock = await page.locator("#overviewGraph .overview-node").first().getAttribute("data-block");
  await page.locator(`#overviewGraph .overview-node[data-block="${firstBlock}"]`).click();
  await page.waitForSelector('#inspector textarea[data-field="owner_observation"]');
  check("five_review_fields", await page.locator("#inspector textarea[data-field]").count() === 5);
  await page.locator('#inspector textarea[data-field="owner_observation"]').fill("browser-smoke-persistence");
  if (locales.length > 1) await page.selectOption("#languageSelect", locales[locales.length - 1]);
  check("comment_survives_language_switch", (await page.locator('#inspector textarea[data-field="owner_observation"]').inputValue()) === "browser-smoke-persistence");

  await page.locator("#backOverview").click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForSelector("#overviewGraph .overview-node");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check("mobile_no_page_overflow", overflow <= 1, `overflow=${overflow}`);
  await page.screenshot({ path: path.join(outputDirectory, "overview-mobile-390x844.png") });
  result.screenshots.mobile = path.join(outputDirectory, "overview-mobile-390x844.png");
} catch (error) {
  result.errors.push(String(error?.stack || error));
} finally {
  await browser.close();
}

result.passed = result.errors.length === 0 && Object.values(result.checks).every((item) => item.passed);
fs.writeFileSync(path.join(outputDirectory, "browser-smoke.json"), JSON.stringify(result, null, 2) + "\n");
if (manifestPath && result.passed) {
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  manifest.checks = { ...(manifest.checks || {}), browser_smoke: "passed" };
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
}
console.log(JSON.stringify(result));
process.exit(result.passed ? 0 : 1);
