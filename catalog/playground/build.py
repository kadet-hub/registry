"""Build the playground's static files (PG-1, PG-5, PG-8, PG-11, PG-12). Standard library only.

Usage: build.py --index <index.json> --out <dir> --data <playground.json> [--projects <dir>] [--outputs <dir>]

Needs network, oras, node, and `npm ci` run in this directory. --out receives
the page's scripts from catalog/site/static/playground, pyodide/ with the
Pyodide runtime and every package the playground loads, packages.json and
examples.json. Each downloaded file is checked against the npm lockfile's
integrity (npm ci), the sha256 of pyodide-lock.json or the hashes of
sandbox/requirements.txt. compile.mjs then compiles every example under each
of its backends in Pyodide, fails on an error or an empty output, and writes
the bytecode archives (DEC-44). --projects receives each example as a Kapitan
project, --outputs its compiled files per backend, for check (PG-6).
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SITE_FILES = os.path.join(ROOT, "catalog", "site", "static", "playground")
OWNER = os.environ.get("OWNER", "kadet-hub")
CORE = ["pyodide.mjs", "pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]
# Compiled or vendored packages from the Pyodide distribution; the lock file adds their dependencies.
# cryptography, requests and jsonschema are left out and stubbed (DEC-44, kapitan_wasm.py).
FROM_PYODIDE = ["pyyaml", "jinja2", "markupsafe", "pydantic", "regex", "six", "pyparsing", "cachetools", "packaging"]
# Pure-Python wheels at the gate's versions (DEC-41).
FROM_PYPI = ["kapitan", "kadet", "python-box", "typeguard", "pydantic-settings", "python-dotenv",
             "kapicorp-reclass", "filetype", "toml", "omegaconf"]
# Files the page fetches when the visitor starts it, besides the wheels.
STARTUP = ["worker.js", "kapitan_wasm.py", "packages.json", "examples.json", "pyodide/site-packages-pyc.zip"] + \
    [f"pyodide/{f}" for f in CORE]


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def fetch(url, sha256, dest):
    data = get(url)
    digest = hashlib.sha256(data).hexdigest()
    if digest not in sha256:
        sys.exit(f"build.py: {url} has sha256 {digest}, expected {' or '.join(sorted(sha256))}")
    with open(dest, "wb") as f:
        f.write(data)


def gate_pins():
    """{normalized name: (version, {sha256, ...})} from sandbox/requirements.txt."""
    with open(os.path.join(ROOT, "sandbox", "requirements.txt"), encoding="utf-8") as f:
        text = f.read()
    pins = {}
    for m in re.finditer(r"^([A-Za-z0-9_.-]+)==(\S+)((?:\s*\\\n\s+--hash=sha256:[0-9a-f]{64})+)", text, re.MULTILINE):
        pins[norm(m.group(1))] = (m.group(2), set(re.findall(r"sha256:([0-9a-f]{64})", m.group(3))))
    return pins


def latest(versions):
    """The latest version that is not yanked, as catalog/build picks it (CAT-7, CAT-38)."""
    listed = [(v, e) for v, e in versions.items() if e.get("yanked") is None]
    if not listed:
        return None, None
    return max(listed, key=lambda ve: [int(p) for p in ve[0].split(".")])


def layer(ref, digest, artifact_type, work):
    """The files of an artifact's layer, pulled by digest."""
    manifest = json.loads(subprocess.run(["oras", "manifest", "fetch", f"{ref}@{digest}"],
                                         check=True, capture_output=True, text=True).stdout)
    if manifest.get("artifactType") != artifact_type:
        sys.exit(f"build.py: {ref}@{digest} is {manifest.get('artifactType')}, not {artifact_type}")
    tar = os.path.join(work, "layer.tar")
    subprocess.run(["oras", "blob", "fetch", "--output", tar, f"{ref}@{manifest['layers'][0]['digest']}"],
                   check=True, capture_output=True)
    files = {}
    with tarfile.open(tar) as t:
        for m in t.getmembers():
            if m.isfile():
                files[m.name.removeprefix("./")] = t.extractfile(m).read().decode("utf-8")
    os.remove(tar)
    return files


def generator(name, digest, work):
    files = layer(f"ghcr.io/{OWNER}/{name}", digest, "application/vnd.kadet-hub.generator.v1", work)
    # schemas/ serves the gate's schema check and tests/ the author's suite; neither runs in a compile.
    return {p: t for p, t in files.items() if not p.startswith(("schemas/", "tests/"))}


def helm_binary(work):
    """helm as sandbox/Dockerfile pins it, so the gate and the page render with the same version."""
    with open(os.path.join(ROOT, "sandbox", "Dockerfile"), encoding="utf-8") as f:
        text = f.read()
    version = re.search(r"^ARG HELM_VERSION=(\S+)", text, re.MULTILINE).group(1)
    sha = re.search(r"^ARG HELM_SHA256=([0-9a-f]{64})", text, re.MULTILINE).group(1)
    tgz = os.path.join(work, "helm.tgz")
    fetch(f"https://get.helm.sh/helm-{version}-linux-amd64.tar.gz", {sha}, tgz)
    with tarfile.open(tgz) as t:
        t.extract("linux-amd64/helm", work, filter="data")
    return os.path.join(work, "linux-amd64", "helm"), version


def helm_template(chart, spec, values, work):
    """helm template's output of the chart the index names for the recipe (PG-11), as the recipe proof renders it."""
    helm, version = helm_binary(work)
    env = dict(os.environ, HELM_CACHE_HOME=os.path.join(work, "helm-cache"),
               HELM_CONFIG_HOME=os.path.join(work, "helm-config"), HELM_DATA_HOME=os.path.join(work, "helm-data"))
    out = os.path.join(work, "chart")
    os.makedirs(out)
    subprocess.run([helm, "pull", f"oci://{chart['repo']}@{chart['digest']}", "-d", out], env=env, check=True, capture_output=True)
    (tgz,) = [os.path.join(out, f) for f in os.listdir(out)]
    shown = subprocess.run([helm, "show", "chart", tgz], env=env, check=True, capture_output=True, text=True).stdout
    if not re.search(rf"^version: {re.escape(chart['version'])}$", shown, re.MULTILINE):
        sys.exit(f"build.py: oci://{chart['repo']}@{chart['digest']} is not version {chart['version']}")
    rendered = subprocess.run([helm, "template", spec["release"], tgz, "-n", spec["namespace"], "-f", values, "--include-crds"],
                              env=env, check=True, capture_output=True, text=True).stdout
    return {"chart": f"oci://{chart['repo']}:{chart['version']}@{chart['digest']}", "helm": version, "output": rendered}


def read_dir(path, skip=()):
    files = {}
    for dirpath, _, names in os.walk(path):
        for n in names:
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, path).replace(os.sep, "/")
            if rel not in skip:
                with open(p, encoding="utf-8") as f:
                    files[rel] = f.read()
    return files


def examples(index, work):
    """examples.json: every example's own files, its libraries by key, and the Helm render."""
    with open(os.path.join(HERE, "examples.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    libs, out = {}, []
    for ex in manifest:
        helm = ex.get("helm")
        files = read_dir(os.path.join(HERE, "examples", ex["dir"]), skip={helm["values"]} if helm else set())
        gens = []
        if "generator" in ex:
            version, entry = latest(index["generators"][ex["generator"]])
            gens.append({"name": ex["generator"], "version": version, "digest": entry["digest"]})
        record = None
        if "recipe" in ex:
            version, record = latest(index["recipes"][ex["recipe"]])
            recipe = layer(f"ghcr.io/{OWNER}/recipes/{ex['recipe']}", record["digest"], "application/vnd.kadet-hub.recipe.v1", work)
            files.update({f"inventory/classes/recipes/{ex['recipe']}/{p}": t for p, t in recipe.items()})
            gens += record["generators"]
        refs = []
        for g in gens:
            key = f"{g['name']}@{g['digest']}"
            if key not in libs:
                libs[key] = generator(g["name"], g["digest"], work)
            refs.append({"key": key, "dir": f"lib/{g['name']}", "version": g["version"]})
        entry = {k: ex[k] for k in ("name", "title", "description", "backends")}
        entry.update(files=files, libs=refs)
        if helm:
            with tempfile.TemporaryDirectory(dir=work) as tmp:
                entry["helm"] = helm_template(record["chart"], helm, os.path.join(HERE, "examples", ex["dir"], helm["values"]), tmp)
        out.append(entry)
    return {"libs": libs, "examples": out}


def projects(data, dest):
    """Each example as a Kapitan project, for compile.mjs and the gate image (PG-6)."""
    for ex in data["examples"]:
        files = dict(ex["files"])
        for ref in ex["libs"]:
            files.update({f"{ref['dir']}/{p}": t for p, t in data["libs"][ref["key"]].items()})
        root = os.path.join(dest, ex["name"])
        os.makedirs(os.path.join(root, "inventory", "classes"), exist_ok=True)
        for rel, text in files.items():
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--data", required=True)
    p.add_argument("--projects")
    p.add_argument("--outputs")
    args = p.parse_args()
    with open(args.index, encoding="utf-8") as f:
        index = json.load(f)
    out = args.out
    os.makedirs(os.path.join(out, "pyodide"), exist_ok=True)
    for name in os.listdir(SITE_FILES):
        shutil.copyfile(os.path.join(SITE_FILES, name), os.path.join(out, name))

    npm = os.path.join(HERE, "node_modules", "pyodide")
    with open(os.path.join(HERE, "package.json"), encoding="utf-8") as f:
        pinned = json.load(f)["dependencies"]["pyodide"]
    with open(os.path.join(npm, "package.json"), encoding="utf-8") as f:
        if json.load(f)["version"] != pinned:
            sys.exit(f"build.py: node_modules has another pyodide than {pinned}; run npm ci")
    for name in CORE:
        shutil.copyfile(os.path.join(npm, name), os.path.join(out, "pyodide", name))
    with open(os.path.join(npm, "pyodide-lock.json"), encoding="utf-8") as f:
        lock = json.load(f)["packages"]
    by_norm = {norm(k): k for k in lock}
    todo, seen = [by_norm[norm(n)] for n in FROM_PYODIDE], set()
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        todo += [by_norm[norm(d)] for d in lock[name]["depends"]]
        pkg = lock[name]
        fetch(f"https://cdn.jsdelivr.net/pyodide/v{pinned}/full/{pkg['file_name']}", {pkg["sha256"]},
              os.path.join(out, "pyodide", pkg["file_name"]))
    pins, wheels = gate_pins(), []
    for name in FROM_PYPI:
        version, hashes = pins[norm(name)]
        meta = json.loads(get(f"https://pypi.org/pypi/{name}/{version}/json"))
        whl = next(u for u in meta["urls"] if u["filename"].endswith("-none-any.whl"))
        fetch(whl["url"], hashes, os.path.join(out, "pyodide", whl["filename"]))
        wheels.append(whl["filename"])
    with open(os.path.join(out, "packages.json"), "w", encoding="utf-8") as f:
        json.dump({"pyodide": sorted(seen), "wheels": wheels}, f)

    with tempfile.TemporaryDirectory() as work:
        data = examples(index, work)
        with open(os.path.join(out, "examples.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        proj = args.projects or os.path.join(work, "projects")
        projects(data, proj)
        cmd = ["node", os.path.join(HERE, "compile.mjs"), out, proj]
        subprocess.run(cmd + ([args.outputs] if args.outputs else []), check=True)

    def gz(rel):
        with open(os.path.join(out, rel), "rb") as f:
            return len(gzip.compress(f.read(), 6))
    startup = STARTUP + [f"pyodide/{lock[n]['file_name']}" for n in seen] + [f"pyodide/{w}" for w in wheels]
    os.makedirs(os.path.dirname(args.data), exist_ok=True)
    with open(args.data, "w", encoding="utf-8") as f:
        json.dump({"pyodide": pinned, "kapitan": pins["kapitan"][0],
                   "download": sum(gz(r) for r in startup),
                   "size": sum(os.path.getsize(os.path.join(out, r)) for r in startup),
                   "examples": [{"name": e["name"], "title": e["title"]} for e in data["examples"]]}, f)


if __name__ == "__main__":
    main()
