// PG-3, PG-7 to PG-10, PG-15, PG-17 to PG-19, PG-21 to PG-24, PG-26 to PG-28, PG-30 in a browser: node browser.mjs <built site dir>
// Serves the site, opens /playground/ in Chrome ($CHROME, default
// /usr/bin/google-chrome) and exits 1 on any finding.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { chromium } from "playwright-core";

const root = process.argv[2];
const types = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".wasm": "application/wasm", ".svg": "image/svg+xml", ".py": "text/plain" };
const server = createServer(async (req, res) => {
  let path = normalize(decodeURIComponent(new URL(req.url, "http://x").pathname));
  if (path.endsWith("/")) path += "index.html";
  try {
    const body = await readFile(join(root, path));
    res.writeHead(200, { "content-type": types[extname(path)] || "application/octet-stream" });
    res.end(body);
  } catch {
    res.writeHead(404);
    res.end();
  }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const origin = `http://127.0.0.1:${server.address().port}`;
const findings = [];
const fail = (msg) => { findings.push(msg); console.log(`FAIL ${msg}`); };

const browser = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome", headless: true });
const page = await browser.newPage();
const requests = [];
page.on("request", (r) => {
  requests.push(r.url());
  if (r.method() !== "GET") fail(`PG-10: ${r.method()} ${r.url()}`);
});
page.on("pageerror", (e) => fail(`page error: ${e.message}`));
const csp = async (url) => (await (await fetch(url)).text()).match(/Content-Security-Policy" content="([^"]*)"/)?.[1];
const step = async (runs, label) => {
  await page.waitForSelector(`body[data-pg-runs="${runs}"]`, { timeout: 600000 });
  const exit = await page.getAttribute("body", "data-pg-exit");
  const files = await page.locator("#pg-outputs details").count();
  console.log(`${label}: exit ${exit}, ${files} files, ${await page.textContent("#pg-status")}`);
  return { exit, files };
};

try {
  if (await csp(`${origin}/playground/`) !== await csp(`${origin}/`)) fail("PG-7: the page's CSP differs from the home page's");
  await page.goto(`${origin}/playground/`);
  await page.waitForTimeout(1000);
  if (requests.some((u) => /\/playground\/(pyodide|prism)\/|\/(worker|syntax)\.js$/.test(u))) fail("PG-9, PG-24: Pyodide or Prism loaded before the start");
  if ((await fetch(`${origin}/playground/prism/LICENSE`)).status !== 200) fail("PG-24: Prism's licence is not served");
  const t0 = Date.now();
  await page.click("#pg-start");
  await page.waitForSelector("#pg-app:not([hidden])");
  if (await page.evaluate(() => document.activeElement.id) !== "pg-example") fail("PG-26: focus is not on the example selector after the start");
  // PG-27, PG-28: read in one task, so the worker's ready message cannot come in between.
  const early = await page.evaluate(() => {
    if (document.body.dataset.pgReady) return null;
    const $ = (id) => document.getElementById(id);
    const seen = { disabled: $("pg-compile").disabled, progress: $("pg-progress")?.checkVisibility() ?? false };
    $("pg-editor").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", ctrlKey: true }));
    return { ...seen, status: $("pg-status").textContent };
  });
  if (!early) console.log("PG-27, PG-28 not checked: the worker was ready first");
  else {
    if (!early.disabled) fail("PG-27: Compile is enabled before the worker is ready");
    if (!early.progress) fail("PG-28: no progress bar while the worker loads");
    // An extra compile would shift every run number the steps below wait for.
    if (early.status.startsWith("Compiling")) throw new Error("PG-27: Ctrl+Enter compiled before the worker was ready");
  }
  const options = await page.$$eval("#pg-example option", (os) => os.map((o) => o.value));
  let runs = 1;
  let r = await step(runs, options[0]);
  console.log(`first output ${((Date.now() - t0) / 1000).toFixed(1)} s after the start`);
  if (r.exit !== "0" || r.files === 0) fail(`${options[0]}: no output`);
  if (await page.isVisible("#pg-progress")) fail("PG-28: the progress bar stays after the worker is ready");
  if (await page.$eval("#pg-status", (s) => s.classList.contains("warning"))) fail("PG-30: a successful compile is shown as a warning");
  // The first example is basics: dev lists apps.web, which lists common, and each sets app.replicas.
  const classes = await page.$$eval("#pg-classes li > code", (cs) => cs.map((c) => c.textContent));
  if (classes.join() !== "common,apps.web,dev") fail(`PG-15: classes ${classes.join(", ")}`);
  await page.fill("#pg-search", "app.replicas");
  const chain = await page.$$eval("#pg-params details[open] .pg-chain li", (ls) => ls.map((l) => l.textContent));
  if (chain.join("|") !== "overridden common 1|overridden apps.web 2|final dev (target) 3") fail(`PG-17, PG-18: app.replicas ${chain.join("|")}`);
  await page.fill("#pg-search", "");
  // PG-23: the open output is highlighted; highlighting keeps the text, also of a 2,000-line YAML.
  await page.waitForSelector("#pg-outputs details[open] pre .token", { timeout: 10000 }).catch(() => fail("PG-23: the first output is not highlighted"));
  const shaded = await page.evaluate(async () => {
    const { highlight } = await import("./syntax.js");
    const pre = document.createElement("pre");
    const yaml = Array.from({ length: 500 }, (_, i) => `item-${i}:\n  name: "web-${i}" # comment\n  replicas: ${i}\n  enabled: true`).join("\n");
    const t0 = performance.now();
    highlight(pre, yaml, "big.yaml");
    const ms = performance.now() - t0;
    const kept = [[yaml, "a.yml"], ['{"a": [1, "<b>"], "c": null}', "a.tf.json"], ["# T\n\n**b** `c` <i>", "README.md"]].every(([text, name]) => {
      highlight(pre, text, name);
      return pre.textContent === text && pre.querySelector(".token");
    });
    return { ms, lines: yaml.split("\n").length, kept };
  });
  console.log(`highlighted ${shaded.lines} lines of YAML in ${shaded.ms.toFixed(1)} ms`);
  if (!shaded.kept) fail("PG-23: highlighting changed an output's text or left it plain");
  for (const name of options.slice(1)) {
    await page.selectOption("#pg-example", name);
    r = await step(++runs, name);
    if (r.exit !== "0" || r.files === 0) fail(`${name}: no output`);
    if (!(await page.isVisible("#pg-params details")) || await page.isVisible("#pg-prov-warning")) fail(`PG-17, PG-19: ${name}: no trace, or it differs`);
    if (name === "terraform") {
      const outs = await page.$$eval("#pg-outputs summary", (ss) => ss.map((s) => s.textContent));
      if (!outs.length || !outs.every((o) => o.endsWith(".tf.json"))) fail(`PG-21: terraform output ${outs.join(", ")}`);
      if (!(await page.textContent("#pg-description")).includes("terraform plan does not run in your browser")) fail("PG-22: no note on terraform plan");
    }
    if (await page.isVisible("#pg-helm") && !(await page.textContent("#pg-helm-output")).includes("kind:")) fail(`${name}: empty helm output`);
  }
  if (!(await page.isVisible("#pg-helm"))) fail("PG-11: no example shows the helm output");
  await page.fill("#pg-editor", `${await page.inputValue("#pg-editor")}\nbroken: [unclosed\n`);
  await page.click("#pg-compile");
  r = await step(++runs, "YAML error");
  const log = await page.textContent("#pg-log");
  if (r.exit === "0" || !/while parsing|expected|found/.test(log)) fail(`PG-3: the YAML error is not shown: ${log.slice(-200)}`);
  if (!(await page.$eval("#pg-status", (s) => s.classList.contains("warning")))) fail("PG-30: the failed compile is not shown as a warning");
  if (await page.isVisible("#pg-prov")) fail("PG-15: provenance shown for an inventory that did not render");
  // PG-30: a start that fails in the worker is a warning that says to reload.
  const broken = await browser.newContext();
  await broken.route(/\/playground\/packages\.json$/, (route) => route.abort());
  const failing = await broken.newPage();
  await failing.goto(`${origin}/playground/`);
  await failing.click("#pg-start");
  await failing.waitForSelector("#pg-status.warning", { timeout: 120000 }).catch(() => {});
  const said = await failing.textContent("#pg-status");
  if (!said.includes("failed to start; reload the page")) fail(`PG-30: a failed start says "${said}"`);
  await broken.close();
  const foreign = requests.filter((u) => !u.startsWith(origin) && !u.startsWith("data:"));
  if (foreign.length) fail(`PG-8: requests to another origin: ${foreign.join(", ")}`);
} catch (e) {
  fail(String(e.message).split("\n")[0]);
}
await browser.close();
server.close();
process.exit(findings.length ? 1 : 0);
