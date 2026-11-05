// PG-7: Pyodide and Kapitan run in this module worker, off the page's thread.
// Every file comes from this directory (PG-8).
import { loadPyodide } from "./pyodide/pyodide.mjs";

const here = (path) => new URL(path, import.meta.url).href;

const ready = (async () => {
  const py = await loadPyodide({ indexURL: here("./pyodide/") });
  const packages = await (await fetch(here("./packages.json"))).json();
  await py.loadPackage([...packages.pyodide, ...packages.wheels.map((w) => here(`./pyodide/${w}`))], {
    messageCallback: () => {},
  });
  // DEC-44: bytecode the build compiled for the modules the examples import.
  const site = py.runPython("import sys; next(p for p in sys.path if p.endswith('site-packages'))");
  py.unpackArchive(await (await fetch(here("./pyodide/site-packages-pyc.zip"))).arrayBuffer(), "zip", { extractDir: site });
  py.FS.writeFile("/home/pyodide/kapitan_wasm.py", await (await fetch(here("./kapitan_wasm.py"))).text());
  return { py, kw: py.pyimport("kapitan_wasm") };
})();
ready.then(
  () => postMessage({ type: "ready" }),
  (e) => postMessage({ type: "error", message: String(e) }),
);

onmessage = async ({ data }) => {
  const { py, kw } = await ready;
  const files = py.toPy(data.files);
  try {
    const [code, log, out] = kw.compile_project(files, data.backend).toJs({ dict_converter: Object.fromEntries });
    postMessage({ type: "result", id: data.id, code, log, out });
  } catch (e) {
    postMessage({ type: "result", id: data.id, code: -1, log: String(e), out: {} });
  } finally {
    files.destroy();
  }
};
