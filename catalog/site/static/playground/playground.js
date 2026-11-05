// The playground page (PG-4, PG-9, PG-11). Nothing loads until the visitor
// starts it; then a module worker compiles with Kapitan in Pyodide.
const $ = (id) => document.getElementById(id);
const app = $("pg-app");
let worker, examples, current, files = {}, path = "", runs = 0;

const status = (text) => { $("pg-status").textContent = text; };
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
  }
  show(Object.keys(files).filter(editable).find((p) => p.startsWith("inventory/targets/")));
}

function compile() {
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
  status(data.code === 0 ? `Compiled ${names.length} files.` : "The compile failed; Kapitan's log is below.");
  $("pg-log").textContent = data.log.trim();
  $("pg-log").hidden = !data.log.trim();
  $("pg-outputs").replaceChildren(...names.map((name, i) => {
    const d = document.createElement("details");
    const s = document.createElement("summary");
    const pre = document.createElement("pre");
    s.textContent = name;
    pre.textContent = data.out[name];
    d.open = i === 0;
    d.append(s, pre);
    return d;
  }));
  document.body.dataset.pgRuns = String(data.id);
  document.body.dataset.pgExit = String(data.code);
}

async function start() {
  $("pg-start").disabled = true;
  status(`Loading Python and Kapitan (${$("pg-start").dataset.size})...`);
  examples = await (await fetch(new URL("./examples.json", import.meta.url))).json();
  $("pg-example").replaceChildren(...examples.examples.map((e) => new Option(e.title, e.name)));
  $("pg-intro").hidden = true;
  app.hidden = false;
  load(examples.examples[0].name);
  worker = new Worker(new URL("./worker.js", import.meta.url), { type: "module" });
  worker.onmessage = ({ data }) => {
    if (data.type === "error") return status(`The playground failed to start: ${data.message}`);
    if (data.type === "ready") {
      document.body.dataset.pgReady = "true";
      return compile();
    }
    result(data);
  };
}

$("pg-start").addEventListener("click", start);
$("pg-example").addEventListener("change", (e) => { load(e.target.value); compile(); });
$("pg-backend").addEventListener("change", compile);
$("pg-compile").addEventListener("click", compile);
$("pg-editor").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) compile();
});
