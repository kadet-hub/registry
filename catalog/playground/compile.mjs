// Compile every example under each of its backends in Pyodide, from the files
// the page serves, check its provenance, and write the bytecode archives
// (PG-6, PG-12, PG-20, DEC-44).
// Usage: node compile.mjs <static dir> <projects dir> [outputs dir]
// Fails on a compile error, an empty output or a provenance difference. outputs dir receives
// <example>/<backend>/<compiled path> for check.
import { mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";

const [staticDir, projectsDir, outputsDir] = process.argv.slice(2).map((p) => p && resolve(p));
const pyodideDir = join(staticDir, "pyodide");
const { loadPyodide } = await import(join(pyodideDir, "pyodide.mjs"));
const py = await loadPyodide({ indexURL: `${pyodideDir}/` });
const packages = JSON.parse(readFileSync(join(staticDir, "packages.json"), "utf8"));
await py.loadPackage([...packages.pyodide, ...packages.wheels.map((w) => join(pyodideDir, w))], { messageCallback: () => {} });
py.FS.writeFile("/home/pyodide/kapitan_wasm.py", readFileSync(join(staticDir, "kapitan_wasm.py")));
const kw = py.pyimport("kapitan_wasm");

const walk = (d) => readdirSync(d).flatMap((n) => {
  const p = join(d, n);
  return statSync(p).isDirectory() ? walk(p) : [p];
});
const { examples } = JSON.parse(readFileSync(join(staticDir, "examples.json"), "utf8"));
let failed = false;
for (const ex of examples) {
  const root = join(projectsDir, ex.name);
  const files = Object.fromEntries(walk(root).map((p) => [relative(root, p), readFileSync(p, "utf8")]));
  for (const backend of ex.backends) {
    const pyFiles = py.toPy(files);
    const [code, log, out, prov] = kw.compile_project(pyFiles, backend).toJs({ dict_converter: Object.fromEntries });
    pyFiles.destroy();
    const names = Object.keys(out);
    // PG-20: the provenance replay must find no difference from the inventory Kapitan rendered.
    const traced = JSON.parse(prov) ?? { error: "no provenance" };
    const differs = traced.error ? [traced.error]
      : Object.entries(traced).flatMap(([t, p]) => p.mismatches.map((m) => `${t}: ${m.join(".")}`));
    const params = traced.error ? 0 : Object.values(traced).reduce((n, p) => n + p.params.length, 0);
    console.log(`${ex.name} (${backend}): exit ${code}, ${names.length} files, ${params} parameters traced`);
    if (code !== 0 || names.length === 0 || differs.length) {
      console.log(differs.length ? `provenance differs from Kapitan's inventory: ${differs.join(", ")}` : log);
      failed = true;
      continue;
    }
    if (outputsDir) {
      for (const [name, text] of Object.entries(out)) {
        const path = join(outputsDir, ex.name, backend, name);
        mkdirSync(dirname(path), { recursive: true });
        writeFileSync(path, text);
      }
    }
  }
}
if (failed) process.exit(1);

// DEC-44: bytecode for every module the examples imported, compiled by this Pyodide.
// Site packages get unchecked-hash .pyc next to their sources; the standard library
// zip gets sourceless .pyc in place of the .py of each imported module.
py.runPython(`
import importlib.util, os, sys, zipfile
from importlib._bootstrap_external import _code_to_hash_pyc

def pyc(source, path):
    code = compile(source, path, "exec", dont_inherit=True)
    return bytes(_code_to_hash_pyc(code, importlib.util.source_hash(source), checked=False))

site = next(p for p in sys.path if p.endswith("site-packages"))
stdzip = next(p for p in sys.path if p.endswith(".zip"))
site_files, std_names = set(), set()
for m in list(sys.modules.values()):
    f = getattr(m, "__file__", None) or ""
    if f.startswith(site + "/") and f.endswith(".py"):
        site_files.add(f)
    elif f.startswith(stdzip + "/") and f.endswith(".py"):
        std_names.add(f[len(stdzip) + 1:])
with zipfile.ZipFile("/tmp/site-packages-pyc.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in sorted(site_files):
        with open(f, "rb") as src:
            z.writestr(os.path.relpath(importlib.util.cache_from_source(f), site), pyc(src.read(), f))
with zipfile.ZipFile(stdzip) as zin, zipfile.ZipFile("/tmp/python_stdlib.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
    for info in zin.infolist():
        data = zin.read(info)
        if info.filename in std_names:
            zout.writestr(info.filename[:-3] + ".pyc", pyc(data, info.filename))
        else:
            zout.writestr(info, data)
`);
writeFileSync(join(pyodideDir, "site-packages-pyc.zip"), py.FS.readFile("/tmp/site-packages-pyc.zip"));
writeFileSync(join(pyodideDir, "python_stdlib.zip"), py.FS.readFile("/tmp/python_stdlib.zip"));
