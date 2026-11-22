// AC-50 and the rendered checks of CAT-9h, CAT-25a, CAT-35c, CAT-54, CAT-76 and CAT-79: node browser.mjs <built site dir> [<screenshot dir>]
// Serves the site as http://kadet-hub.test, opens one page of every page type in Chrome ($CHROME, default
// /usr/bin/google-chrome) in the light and the dark theme, writes the 20 screenshots of AC-50 when a directory is given,
// and exits 1 on any finding. playwright-core is the one catalog/playground/package.json pins.
import { createServer } from "node:http";
import { readFile, readdir, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { extname, join, normalize, relative } from "node:path";

const { chromium } = createRequire(new URL("./playground/package.json", import.meta.url))("playwright-core");
const [root, shots] = process.argv.slice(2);
const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml",
  ".png": "image/png", ".woff2": "font/woff2", ".xml": "application/xml", ".txt": "text/plain" };
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
// A host name, not 127.0.0.1: count.js counts nothing on a local address, and CAT-25a looks at what it sends.
const origin = `http://kadet-hub.test:${server.address().port}`;
const counter = "https://stats.kadet-hub.org";
const findings = [];
const fail = (msg) => { findings.push(msg); console.log(`FAIL ${msg}`); };

// One page of every page type of "Page types"; the kind and security pages are found in the build.
const first = async (dir) => {
  for (const e of await readdir(join(root, dir), { recursive: true, withFileTypes: true }).catch(() => [])) {
    const path = relative(root, join(e.parentPath, e.name));
    if (e.name === "index.html" && path !== join(dir, "index.html")) return `/${path.slice(0, -"index.html".length)}`;
  }
  fail(`AC-50: no page under /${dir}/ in the build`);
  return null;
};
const PAGES = ["/", "/generators/", "/generators/demo/", "/recipes/", "/recipes/uptime-kuma/", "/stacks/", "/playground/", "/guides/",
  "/guides/how-kadet-hub-works/", "/blog/", "/blog/chainsaw-kind/", "/quickstart/", "/popularity/", "/wanted/", "/tags/", "/tags/helm/",
  "/kinds/", await first("kinds"), "/compatibility/", "/glossary/", "/stats/", await first("security"), "/imprint/", "/privacy/"].filter(Boolean);
const SHOTS = { "/": "start", "/generators/": "catalog", "/generators/demo/": "generator", "/guides/how-kadet-hub-works/": "guide", "/recipes/uptime-kuma/": "recipe" };
const LISTS = ["/guides/", "/blog/", "/stacks/", "/recipes/"]; // CAT-79

const browser = await chromium.launch({ executablePath: process.env.CHROME || "/usr/bin/google-chrome", headless: true,
  args: ["--host-resolver-rules=MAP kadet-hub.test 127.0.0.1"] });
const open = async (path, { width, theme = "light", ...opts }) => {
  const context = await browser.newContext({ viewport: { width, height: 900 }, colorScheme: theme, ...opts });
  const counted = [];
  await context.route(`${counter}/**`, (route) => { counted.push(decodeURIComponent(route.request().url())); return route.fulfill({ status: 204 }); });
  await context.route((u) => u.origin !== origin && u.origin !== counter && u.protocol !== "data:",
    (route) => { fail(`CAT-3: ${path} requests ${route.request().url()}`); return route.abort(); });
  const page = await context.newPage();
  page.on("pageerror", (e) => fail(`${path}: page error: ${e.message}`));
  page.on("console", (m) => { if (/Content Security Policy/.test(m.text())) fail(`CAT-3: ${path}: ${m.text()}`); });
  const res = await page.goto(origin + path, { waitUntil: "load" });
  if (!res.ok()) fail(`${path}: HTTP ${res.status()}`);
  await page.evaluate(() => document.fonts.ready);
  // The drawings move once at load; their last frame is the state that stays.
  await page.evaluate(() => { for (const a of document.getAnimations()) a.finish(); });
  return { context, page, counted };
};

// CAT-54: every text in view against what it stands on. HTML text takes the first background behind it; text in an SVG the
// shape painted before it under its middle, or the page behind the SVG. Opacity multiplies the colour's alpha.
const contrast = () => {
  const rgba = (c) => { const m = c.match(/rgba?\(([\d.]+),? ([\d.]+),? ([\d.]+)(?:,? \/? ?([\d.]+))?\)/); return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null; };
  const over = (top, under) => top.slice(0, 3).map((v, i) => v * top[3] + under[i] * (1 - top[3])).concat(1);
  const lum = (c) => { const [r, g, b] = c.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const opacity = (e) => { let o = 1; for (let n = e; n && n.nodeType === 1; n = n.parentElement) o *= +getComputedStyle(n).opacity; return o; };
  const behind = (e) => {
    const layers = [];
    for (let n = e; n; n = n.parentElement) { const c = rgba(getComputedStyle(n).backgroundColor); if (c && c[3] > 0) { layers.push(c); if (c[3] === 1) break; } }
    return layers.reduceRight((under, top) => over(top, under), [255, 255, 255, 1]);
  };
  const shapeBehind = (text) => {
    const svg = text.ownerSVGElement, r = text.getBoundingClientRect(), x = r.x + r.width / 2, y = r.y + r.height / 2;
    let hit = null;
    for (const s of svg.querySelectorAll("path, rect, polygon, ellipse, circle")) {
      if (s.compareDocumentPosition(text) & Node.DOCUMENT_POSITION_PRECEDING) break; // painted after the text
      const b = s.getBoundingClientRect(), fill = rgba(getComputedStyle(s).fill);
      if (!fill || fill[3] === 0 || x < b.left || x > b.right || y < b.top || y > b.bottom || !s.checkVisibility({ opacityProperty: true })) continue;
      const at = new DOMPoint(x, y).matrixTransform(s.getScreenCTM().inverse());
      if (s.isPointInFill(at)) hit = s;
    }
    return hit ? over(rgba(getComputedStyle(hit).fill), behind(svg)) : behind(svg);
  };
  const low = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node; (node = walker.nextNode());) {
    const e = node.parentElement;
    if (!node.textContent.trim() || !e || e.closest("script, style, title, desc, .visually-hidden, :disabled, [aria-disabled='true']")) continue;
    const cs = getComputedStyle(e);
    if (parseFloat(cs.fontSize) === 0 || !e.checkVisibility({ opacityProperty: true, visibilityProperty: true }) || !e.getClientRects().length) continue;
    const svg = e instanceof SVGElement;
    const fg = rgba(svg ? cs.fill : cs.color);
    if (!fg) continue;
    fg[3] *= opacity(e);
    const bg = svg ? shapeBehind(e) : behind(e);
    const r = ratio(over(fg, bg), bg);
    if (r < 4.5) low.push(`${r.toFixed(2)}:1 "${node.textContent.trim().slice(0, 40)}" (${e.tagName.toLowerCase()}.${[...e.classList].join(".")})`);
  }
  return [...new Set(low)];
};

// CAT-76: the longest line of running text, in characters. A line ends where the next character stands left of the last.
const measure = () => {
  let longest = { n: 0 };
  const RUNNING = "p, li, dd, blockquote, figcaption";
  for (const block of document.querySelectorAll(`:is(main, footer.site) :is(${RUNNING})`)) {
    if (block.closest("pre, table, nav, svg, .station-tabs, .tag-filter, .toolbar") || !block.checkVisibility()) continue;
    let n = 0, last = null, text = "";
    const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
    for (let node; (node = walker.nextNode());) {
      if (node.parentElement.closest("pre, svg, .visually-hidden") || node.parentElement.closest(RUNNING) !== block) continue;
      for (let i = 0; i < node.length; i++) {
        const range = document.createRange();
        range.setStart(node, i);
        range.setEnd(node, i + 1);
        const r = [...range.getClientRects()].find((b) => b.width > 0);
        if (!r) continue;
        if (last && (r.left < last.left - 1 || r.top > last.bottom)) { n = 0; text = ""; }
        n++;
        text += node.textContent[i];
        last = r;
        if (n > longest.n) longest = { n, text, where: `${block.tagName.toLowerCase()}.${[...block.classList].join(".")}` };
      }
    }
  }
  return longest;
};

try {
  for (const path of PAGES) {
    for (const theme of ["light", "dark"]) {
      for (const width of [375, 1024, 1440]) {
        if (width === 1024 && theme === "dark") continue; // the width checks need one theme
        const { context, page } = await open(path, { width, theme });
        for (const low of await page.evaluate(contrast)) fail(`CAT-54: ${path} ${theme} ${width}px: ${low}`);
        if (theme === "light") {
          const line = await page.evaluate(measure);
          if (line.n > 80) fail(`CAT-76: ${path} ${width}px: ${line.n} characters in ${line.where}: "${line.text}"`);
          if (width === 375 && await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) fail(`CAT-9: ${path} scrolls sideways at 375px`);
        }
        if (SHOTS[path] && width !== 1024 && shots) {
          await mkdir(shots, { recursive: true });
          await page.screenshot({ path: join(shots, `${SHOTS[path]}-${width}-${theme}.png`), fullPage: true });
        }
        if (width >= 1024 && theme === "light") { // CAT-9h: the panels whose lines the site writes fit their boxes
          await page.evaluate(() => { for (const d of document.querySelectorAll("details.version")) d.open = true; });
          const wide = await page.$$eval(".harbour .term pre, .live-edit pre, details.version :is([id^=entry-], [id^=verify-])",
            (ps) => ps.filter((p) => p.scrollWidth > p.clientWidth).map((p) => `${p.closest("[id]")?.id}: ${p.scrollWidth} > ${p.clientWidth}`));
          for (const w of wide) fail(`CAT-9h: ${path} ${width}px: ${w}`);
        }
        if (LISTS.includes(path) && width !== 1024 && theme === "light") { // CAT-79: two cards side by side from 64rem, one below
          const [a, b, list, col] = await page.evaluate(() => {
            const ul = document.querySelector(".page-head ~ * .guide-list");
            const [x, y] = ul.children;
            return [x.getBoundingClientRect().toJSON(), y.getBoundingClientRect().toJSON(), ul.getBoundingClientRect().width,
              ul.closest("main").getBoundingClientRect().width - 2 * parseFloat(getComputedStyle(ul.closest("main")).paddingLeft)];
          });
          const side = Math.abs(a.top - b.top) < 1 && b.left >= a.right;
          if (side !== (width === 1440)) fail(`CAT-79: ${path} ${width}px: the first two cards ${side ? "side by side" : "one under the other"}`);
          if (list < col - 1) fail(`CAT-79: ${path} ${width}px: the list is ${list}px of the column's ${col}px`);
        }
        await context.close();
      }
    }
  }

  // CAT-25a: a query reaches the counter neither as the page counted nor as the next page's referrer. The fixture's
  // demo renders HTTPRoute, so the search finds it.
  {
    const { context, page, counted } = await open("/generators/?q=httproute", { width: 1440 });
    await page.waitForFunction(() => document.querySelectorAll(".card:not([hidden])").length > 0);
    await page.waitForTimeout(500);
    await Promise.all([page.waitForURL(/\/generators\/demo\/$/), page.click(".card:not([hidden]) .card-name a")]);
    await page.waitForTimeout(500);
    const referrer = await page.evaluate(() => document.referrer);
    if (referrer !== `${origin}/`) fail(`CAT-25a: the generator page's referrer is ${referrer}`);
    if (counted.length < 2) fail(`CAT-25a: ${counted.length} requests to the counter, expected one per page`);
    for (const url of counted) if (url.toLowerCase().includes("httproute")) fail(`CAT-25a: the counter got ${url}`);
    await context.close();
  }

  // CAT-35c: every edge and cluster label keeps 4 pt from every line, arrowhead, node outline and other label, measured on
  // the box of its glyphs in Manrope Medium at 12 pt; every node label lies inside its node. dot's units are points.
  {
    const { context, page } = await open("/guides/how-kadet-hub-works/", { width: 1440 });
    const found = await page.evaluate(() => {
      const ctx = document.createElement("canvas").getContext("2d");
      const out = [];
      for (const svg of document.querySelectorAll(".diagram svg")) {
        const name = svg.closest("figure").querySelector("title, [id]")?.textContent ?? "";
        const glyphs = (t) => { // the ink box of a label in the SVG's units, without the spaces that only reserve room
          const cs = getComputedStyle(t);
          ctx.font = `${cs.fontWeight} ${t.getAttribute("font-size")}px ${cs.fontFamily}`;
          const raw = t.textContent, s = raw.trim(), whole = ctx.measureText(raw).width, m = ctx.measureText(s);
          const x = +t.getAttribute("x"), y = +t.getAttribute("y") + new DOMMatrix(cs.transform).f;
          const start = ({ middle: x - whole / 2, end: x - whole }[t.getAttribute("text-anchor")] ?? x) + ctx.measureText(raw.slice(0, raw.indexOf(s))).width;
          return { name: s, x0: start - m.actualBoundingBoxLeft, x1: start + m.actualBoundingBoxRight, y0: y - m.actualBoundingBoxAscent, y1: y + m.actualBoundingBoxDescent };
        };
        const samples = (shape) => {
          const pts = [], len = shape.getTotalLength();
          for (let d = 0; d <= len; d += 0.25) { const p = shape.getPointAtLength(d); pts.push([p.x, p.y]); }
          return pts;
        };
        const gap = (b, [x, y]) => Math.hypot(Math.max(b.x0 - x, 0, x - b.x1), Math.max(b.y0 - y, 0, y - b.y1));
        const apart = (a, b) => Math.hypot(Math.max(a.x0 - b.x1, 0, b.x0 - a.x1), Math.max(a.y0 - b.y1, 0, b.y0 - a.y1));
        const lines = [...svg.querySelectorAll(".edge path, .edge polygon, .node path, .node polygon, .node ellipse")].flatMap(samples);
        const labels = [...svg.querySelectorAll(".edge text, .cluster > text")].filter((t) => t.textContent.trim()).map(glyphs);
        for (const [i, l] of labels.entries()) {
          const near = Math.min(...lines.map((p) => gap(l, p)));
          if (near < 4) out.push(`${name}: "${l.name}" ${near.toFixed(2)} pt from a line or outline`);
          for (const m of labels.slice(i + 1)) if (apart(l, m) < 4) out.push(`${name}: "${l.name}" ${apart(l, m).toFixed(2)} pt from "${m.name}"`);
        }
        for (const node of svg.querySelectorAll(".node")) {
          const shape = node.querySelector("path, polygon, ellipse")?.getBBox();
          for (const t of node.querySelectorAll("text")) {
            const g = glyphs(t);
            if (!shape || g.x0 < shape.x || g.x1 > shape.x + shape.width || g.y0 < shape.y || g.y1 > shape.y + shape.height) out.push(`${name}: node label "${g.name}" outside its node`);
          }
        }
      }
      return out;
    });
    for (const f of found) fail(`CAT-35c: ${f}`);
    await context.close();
  }
} catch (e) {
  fail(String(e.message).split("\n")[0]);
}
await browser.close();
server.close();
console.log(`${PAGES.length} pages checked, ${findings.length} findings`);
process.exit(findings.length ? 1 : 0);
