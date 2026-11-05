// PG-3, PG-7 to PG-10, PG-15, PG-17 to PG-19 in a browser: node browser.mjs <built site dir>
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
  if (requests.some((u) => u.includes("/playground/pyodide/") || u.endsWith("/worker.js"))) fail("PG-9: Pyodide loaded before the start");
  const t0 = Date.now();
  await page.click("#pg-start");
  const options = await page.$$eval("#pg-example option", (os) => os.map((o) => o.value));
  let runs = 1;
  let r = await step(runs, options[0]);
  console.log(`first output ${((Date.now() - t0) / 1000).toFixed(1)} s after the start`);
  if (r.exit !== "0" || r.files === 0) fail(`${options[0]}: no output`);
  // The first example is basics: dev lists apps.web, which lists common, and each sets app.replicas.
  const classes = await page.$$eval("#pg-classes li > code", (cs) => cs.map((c) => c.textContent));
  if (classes.join() !== "common,apps.web,dev") fail(`PG-15: classes ${classes.join(", ")}`);
  await page.fill("#pg-search", "app.replicas");
  const chain = await page.$$eval("#pg-params details[open] .pg-chain li", (ls) => ls.map((l) => l.textContent));
  if (chain.join("|") !== "overridden common 1|overridden apps.web 2|final dev (target) 3") fail(`PG-17, PG-18: app.replicas ${chain.join("|")}`);
  await page.fill("#pg-search", "");
  for (const name of options.slice(1)) {
    await page.selectOption("#pg-example", name);
    r = await step(++runs, name);
    if (r.exit !== "0" || r.files === 0) fail(`${name}: no output`);
    if (!(await page.isVisible("#pg-params details")) || await page.isVisible("#pg-prov-warning")) fail(`PG-17, PG-19: ${name}: no trace, or it differs`);
    if (await page.isVisible("#pg-helm") && !(await page.textContent("#pg-helm-output")).includes("kind:")) fail(`${name}: empty helm output`);
  }
  if (!(await page.isVisible("#pg-helm"))) fail("PG-11: no example shows the helm output");
  await page.fill("#pg-editor", `${await page.inputValue("#pg-editor")}\nbroken: [unclosed\n`);
  await page.click("#pg-compile");
  r = await step(++runs, "YAML error");
  const log = await page.textContent("#pg-log");
  if (r.exit === "0" || !/while parsing|expected|found/.test(log)) fail(`PG-3: the YAML error is not shown: ${log.slice(-200)}`);
  if (await page.isVisible("#pg-prov")) fail("PG-15: provenance shown for an inventory that did not render");
  const foreign = requests.filter((u) => !u.startsWith(origin) && !u.startsWith("data:"));
  if (foreign.length) fail(`PG-8: requests to another origin: ${foreign.join(", ")}`);
} catch (e) {
  fail(String(e.message).split("\n")[0]);
}
await browser.close();
server.close();
process.exit(findings.length ? 1 : 0);
