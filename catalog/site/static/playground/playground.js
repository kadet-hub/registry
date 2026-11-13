// The playground page (PG-4, PG-9, PG-11, PG-15 to PG-19, PG-26 to PG-28, PG-30). Nothing loads until
// the visitor starts it; then a module worker compiles with Kapitan in Pyodide.
const $ = (id) => document.getElementById(id);
const app = $("pg-app");
let worker, examples, current, files = {}, path = "", runs = 0, prov = null, syntax, ready = false;

// PG-30: a failed compile or start is shown as a warning.
const status = (text, failed = false) => {
  $("pg-status").textContent = text;
  $("pg-status").classList.toggle("warning", failed);
};
// lib/ holds fetched generators: compiled, not edited.
const editable = (p) => !p.startsWith("lib/") && /\.(ya?ml|py|j2|md|txt|json)$/.test(p) && !/(^|\/)(README\.md|LICENSE)$/.test(p);

function show(p) {
  if (path) files[path] = $("pg-editor").value;
  path = p;
  $("pg-editor").value = files[p];
  $("pg-editor-label").textContent = p;
  for (const b of $("pg-files").querySelectorAll("button")) b.setAttribute("aria-pressed", String(b.dataset.path === p));
}

function load(name) {
  current = examples.examples.find((e) => e.name === name);
  files = structuredClone(current.files);
  path = "";
  $("pg-description").textContent = current.description;
  $("pg-backend").value = current.backends[0];
  $("pg-tested").textContent = current.backends.join(" and ");
  $("pg-files").replaceChildren(...Object.keys(files).filter(editable).sort().map((p) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "pg-file";
    b.dataset.path = p;
    b.textContent = p;
    b.addEventListener("click", () => show(p));
    return b;
  }));
  const lib = current.libs.map((l) => `${l.dir} (${l.key.split("@")[0]} ${l.version})`).join(", ");
  $("pg-libs").textContent = lib ? `Compiled with ${lib}, from the published artifact by digest; not shown.` : "";
  const helm = current.helm;
  $("pg-helm").hidden = !helm;
  if (helm) {
    $("pg-helm-source").textContent = `${helm.chart}, rendered with helm ${helm.helm}`;
    $("pg-helm-output").textContent = helm.output;
    shade($("pg-helm-output"), helm.output, "helm.yaml");
  }
  show(Object.keys(files).filter(editable).find((p) => p.startsWith("inventory/targets/")));
}

function compile() {
  if (!ready) return; // PG-27: the worker compiles once it is ready, with what is selected then
  if (path) files[path] = $("pg-editor").value;
  const project = { ...files };
  for (const l of current.libs) {
    for (const [p, text] of Object.entries(examples.libs[l.key])) project[`${l.dir}/${p}`] = text;
  }
  $("pg-compile").disabled = true;
  status("Compiling...");
  worker.postMessage({ id: ++runs, files: project, backend: $("pg-backend").value });
}

function result(data) {
  $("pg-compile").disabled = false;
  const names = Object.keys(data.out);
  status(data.code === 0 ? `Compiled ${names.length} files.` : "The compile failed; Kapitan's log is below.", data.code !== 0);
  $("pg-log").textContent = data.log.trim();
  $("pg-log").hidden = !data.log.trim();
  $("pg-outputs").replaceChildren(...names.map((name, i) => {
    const d = document.createElement("details");
    const s = document.createElement("summary");
    const pre = document.createElement("pre");
    s.textContent = name;
    pre.textContent = data.out[name];
    // An output is highlighted when it is first opened.
    d.addEventListener("toggle", () => {
      if (d.open && !pre.dataset.shaded) shade(pre, data.out[name], name);
    });
    d.open = i === 0;
    d.append(s, pre);
    return d;
  }));
  showProv(data);
  document.body.dataset.pgRuns = String(data.id);
  document.body.dataset.pgExit = String(data.code);
}

// PG-23: plain text stays if the highlighter fails to load.
function shade(pre, text, name) {
  pre.dataset.shaded = "true";
  syntax.then((m) => m.highlight(pre, text, name), () => {});
}

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
};
const json = (v) => JSON.stringify(v) ?? "null";
const clip = (s) => (s.length > 120 ? `${s.slice(0, 120)}...` : s);

// Provenance from kapitan_wasm.py: null when the inventory did not render.
function showProv(data) {
  prov = data.prov;
  $("pg-prov").hidden = !prov;
  if (!prov) return;
  const targets = prov.error ? [] : Object.keys(prov);
  const keep = $("pg-target").value;
  $("pg-target").replaceChildren(...targets.map((t) => new Option(t, t)));
  if (targets.includes(keep)) $("pg-target").value = keep;
  $("pg-prov-backend").textContent = data.backend;
  showTarget();
}

function showTarget() {
  const t = prov[$("pg-target").value];
  const warning = $("pg-prov-warning");
  const differs = prov.error ? [] : t.mismatches.map((p) => p.join("."));
  warning.hidden = !prov.error && !differs.length;
  warning.textContent = prov.error ? `The playground could not trace where the values come from: ${prov.error}`
    : `The trace differs from Kapitan's merged inventory at ${differs.join(", ")}, so the sources shown there can be wrong.`;
  if (prov.error) {
    $("pg-classes").replaceChildren();
    $("pg-order-other").textContent = "";
    $("pg-count").textContent = "";
    $("pg-params").replaceChildren();
    return;
  }
  const target = t.sources.find((s) => s.kind === "target").name;
  $("pg-classes").replaceChildren(...t.sources.filter((s) => s.kind === "class" || s.kind === "target").map((s) => {
    const li = el("li");
    const from = s.kind === "target" ? "the target" : `listed by ${s.via === target ? "the target" : s.via}`;
    li.append(el("code", "", s.name), " ", el("span", "pg-note", `${from}, ${s.file}`));
    return li;
  }));
  const o = t.other;
  const mine = t.sources.filter((s) => s.kind === "class").map((s) => s.file).join();
  $("pg-order-other").textContent = o.error ? `${o.backend} cannot read this inventory: ${o.error}`
    : o.classes.map((c) => c.file).join() === mine ? `${o.backend} merges the same classes in the same order.`
    : `${o.backend} merges ${o.classes.length ? o.classes.map((c) => c.name).join(", ") : "no classes"}, in this order.`;
  showParams();
}

function showParams() {
  if (!prov || prov.error) return;
  const t = prov[$("pg-target").value];
  const name = (e) => {
    const s = t.sources[e.source];
    return s.kind === "target" ? `${s.name} (target)` : s.name;
  };
  const q = $("pg-search").value.trim().toLowerCase();
  const rows = t.params.filter((p) => p.path.join(".").toLowerCase().includes(q));
  $("pg-count").textContent = `${rows.length} of ${t.params.length} parameters`;
  $("pg-params").replaceChildren(...rows.map((p) => {
    // The value is the last "set" and every list merged into it after.
    const last = p.chain.findLastIndex((e) => e.op === "set");
    const final = p.chain.slice(last);
    const d = el("details");
    d.open = rows.length === 1;
    const s = el("summary");
    s.append(el("code", "pg-path", p.path.join(".")), " ", el("code", "", clip(json(p.value))), " ",
      el("span", "pg-src", final.map(name).join(" + ")));
    const raw = json(p.chain.at(-1).value);
    if (final.length === 1 && raw !== json(p.value)) s.append(" ", el("span", "pg-note", "resolved from"), " ", el("code", "", clip(raw)));
    if (last > 0) s.append(" ", el("span", "pg-note", `overrides ${last}`));
    const ol = el("ol", "pg-chain");
    p.chain.forEach((e, i) => {
      const li = el("li", i >= last ? "pg-win" : "");
      li.append(el("span", "pg-tag", i < last ? "overridden" : final.length > 1 ? "merged" : "final"), " ", el("span", "pg-src", name(e)));
      if (e.path.length !== p.path.length) li.append(" ", el("code", "", e.path.join(".")));
      li.append(" ", el("code", "", json(e.value)));
      ol.append(li);
    });
    d.append(s, ol);
    return d;
  }));
}

async function start() {
  $("pg-start").disabled = true;
  syntax = import("./syntax.js");
  examples = await (await fetch(new URL("./examples.json", import.meta.url))).json();
  $("pg-example").replaceChildren(...examples.examples.map((e) => new Option(e.title, e.name)));
  $("pg-intro").hidden = true;
  app.hidden = false;
  $("pg-progress").hidden = false;
  status(`Loading Python and Kapitan (${$("pg-start").dataset.size})...`);
  $("pg-example").focus(); // PG-26: the start button that had focus is gone
  load(examples.examples[0].name);
  worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
  worker.onmessage = ({ data }) => {
    $("pg-progress").hidden = true; // PG-28: the worker's first message, ready or error, ends the load
    // PG-30: without a worker Compile stays disabled (PG-27), so only a reload tries again.
    if (data.type === "error") return status(`The playground failed to start; reload the page to try again: ${data.message}`, true);
    if (data.type === "ready") {
      ready = true;
      document.body.dataset.pgReady = "true";
      return compile();
    }
    result(data);
  };
  // PG-30: a worker whose script or Pyodide's module does not load posts nothing; the browser reports it here.
  worker.onerror = (e) => worker.onmessage({ data: { type: "error", message: e.message || "the worker did not load" } });
}

$("pg-start").addEventListener("click", start);
$("pg-example").addEventListener("change", (e) => { load(e.target.value); compile(); });
$("pg-backend").addEventListener("change", compile);
$("pg-compile").addEventListener("click", compile);
$("pg-target").addEventListener("change", showTarget);
$("pg-search").addEventListener("input", showParams);
$("pg-editor").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) compile();
});
