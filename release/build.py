"""Validate every entry on main and build its artifact (GI-9, REG-2, REG-3, PUB-1).

Usage: build.py --base MAIN --sources DIR --out DIR

Runs in the sandbox image without network. DIR/<name> holds the fetched tree
`source.sha:source.path` of each entry. Writes <out>/<name>/<name>.tar and
meta.json for every entry whose current version is not yanked, and
<out>/names.json. Prints findings and exits 1 on any.
"""

import argparse
import json
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "gate")]  # python -I does not add the script dir
from check_entry import ENTRY_PATH, TAG, lines, schema_errors, squash
from tree import read_dir, tree_id, write_tar


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--sources", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    policy = os.path.join(a.base, "policy")
    reserved = set(lines(os.path.join(policy, "reserved-names.txt")))
    gen_dir = os.path.join(a.base, "generators")
    files = sorted(os.listdir(gen_dir)) if os.path.isdir(gen_dir) else []
    findings, names = [], []
    seen = {squash(r): r for r in reserved}
    for fname in files:
        m = ENTRY_PATH.match("generators/" + fname)
        if not m:
            findings.append(f"REG-2: {fname}: entry path must match generators/<name>.yaml")
            continue
        name = m.group(1)
        if name in reserved:
            findings.append(f"REG-2: {name} is reserved")
        if squash(name) in seen:
            findings.append(f"REG-3: {name} equals {seen[squash(name)]} without separators")
        seen.setdefault(squash(name), name)
        with open(os.path.join(gen_dir, fname), encoding="utf-8") as f:
            entry = yaml.safe_load(f)
        errors = schema_errors(entry, os.path.join(policy, "entry.schema.json"))
        if errors:
            findings += [f"GI-9: {name}: entry: {e}" for e in errors]
            continue
        src = entry["source"]
        version = TAG.match(src["tag"]).group("version")
        if version in entry.get("yanked", {}):
            print(f"{name} {version}: yanked, not built")
            continue
        tree = os.path.join(a.sources, name)
        with open(os.path.join(tree, "kapitan-generator.yaml"), encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        errors = schema_errors(manifest, os.path.join(policy, "manifest.schema.json"))
        if errors:
            findings += [f"GI-9: {name}: manifest: {e}" for e in errors]
            continue
        if manifest["name"] != name:
            findings.append(f"REG-2: manifest name {manifest['name']} differs from entry {name}")
            continue
        content = read_dir(tree)
        meta = {
            "name": name, "version": version, "tree": tree_id(content), "krab": None,
            "description": manifest["description"], "tags": manifest.get("tags", []),
            "source": {k: src[k] for k in ("repo", "path", "tag", "sha")},
            "owners": entry["owners"],
            "license": manifest["license"], "kapitan": manifest["kapitan"],
            "binaries": manifest.get("binaries", []),
            "output_capabilities": manifest.get("output_capabilities", []),
            "unparsed_outputs": manifest.get("unparsed_outputs", []),
            "charts": [{k: c[k] for k in ("repo", "name", "version", "sha256")} for c in manifest.get("charts", [])],
        }
        out = os.path.join(a.out, name)
        os.makedirs(out)
        write_tar(content, os.path.join(out, f"{name}.tar"))
        with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(meta, sort_keys=True, separators=(",", ":")))
        names.append(name)
    with open(os.path.join(a.out, "names.json"), "w", encoding="utf-8") as f:
        json.dump(names, f)
    if findings:
        print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
