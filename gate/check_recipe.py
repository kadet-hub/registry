"""Checks on a recipe's files (REC-4, the include rule of REC-5, REC-6, REC-15).

Usage: check_recipe.py --tree DIR --index FILE --policy DIR [--license FILE] --out FILE

Runs in the sandbox image without network. DIR is the recipe as
`fetch_tree.py --recipe` writes it, FILE for --index the attested index
and for --license the source repository's root LICENSE. Writes the
generators whose attestation the gate verifies, one reference per line.
Prints findings; exits 1 on any.
"""

import argparse
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "consumer")]  # python -I does not add the script dir
from check_entry import LICENSE_HEAD, lines, load_json, read_text  # noqa: E402
from plan import check_index  # noqa: E402

GENERATOR = re.compile(r"^ghcr\.io/kadet-hub/(?P<name>[a-z][a-z0-9-]{1,38}):(?P<tag>[A-Za-z0-9_][A-Za-z0-9._-]{0,127})"
                       r"@(?P<digest>sha256:[0-9a-f]{64})$")
INCLUDED = re.compile(r"^recipes\.(?P<other>[a-z][a-z0-9-]{1,38})(\.[A-Za-z0-9_-]+)?$")


def get(data, *keys):
    """data[k1][k2]..., None where a level is not a mapping."""
    for k in keys:
        data = data.get(k) if isinstance(data, dict) else None
    return data


def items(data):
    return data if isinstance(data, list) else []


def check(tree, index, policy, license_path):
    """Findings and the generator references to verify."""
    name = os.path.basename(os.path.normpath(tree))
    prefix = f"inventory/classes/recipes/{name}/"
    files = sorted(os.path.relpath(os.path.join(r, f), tree) for r, _, fs in os.walk(tree) for f in fs)
    shipped = [f for f in files if not f.startswith("tests/")]
    findings, classes = [], {}
    for f in shipped:
        if "/" not in f and f.endswith(".yml"):
            try:
                with open(os.path.join(tree, f), encoding="utf-8") as fh:
                    classes[f] = yaml.safe_load(fh)
            except (UnicodeDecodeError, yaml.YAMLError, RecursionError) as e:
                findings.append(f"REC-5: {f} is not YAML: {str(e)[:200]}")
    copies = {str(p)[len(prefix):] for doc in classes.values() for e in items(get(doc, "parameters", "kapitan", "compile"))
              if get(e, "input_type") == "copy" for p in items(get(e, "input_paths")) if str(p).startswith(prefix)}

    # REC-4: the shipped tree's layout.
    for f in shipped:
        top = "/" not in f
        if f.endswith(".py"):
            findings.append(f"REC-4: {f}: the shipped tree holds no Python file")
        elif f.startswith("vendor/") and f.endswith((".yml", ".yaml")) and f not in copies:
            findings.append(f"REC-4: {f}: YAML below vendor/ that no copy entry names would be a class file")
        elif not (f == "README.md" or f.startswith("vendor/") or top and f.endswith(".yml")
                  or top and f.endswith((".yml.LICENSE", ".yml.NOTICE")) and f.rsplit(".", 1)[0] in shipped):
            findings.append(f"REC-4: {f}: the shipped tree holds only README.md, class files *.yml at the root"
                            " with their .LICENSE and .NOTICE, and files below vendor/")
    # REC-15: the license next to each vendored file.
    for c in sorted(copies):
        if c + ".LICENSE" not in shipped:
            findings.append(f"REC-15: {c} is vendored by a copy entry and has no {os.path.basename(c)}.LICENSE next to it")
    # REC-4: the license of the repository root's LICENSE, as QA-2 matches it.
    text = read_text(license_path, LICENSE_HEAD) if license_path else None
    patterns = [ln.split(None, 1)[1] for ln in lines(os.path.join(policy, "licenses.txt"))]
    if text is None or not any(re.search(p, " ".join(text.split())) for p in patterns):
        findings.append("REC-4: the source repository's root LICENSE is missing or matches no license on policy/licenses.txt")

    deps = {}
    for f, doc in classes.items():
        # REC-5: classes of the recipe itself or of an included recipe, which REC-16 resolves.
        for cls in items(get(doc, "classes")):
            c = str(cls)
            m = INCLUDED.match(c)
            if not (c.startswith((".", f"recipes.{name}.")) or m and m.group("other") != name):
                findings.append(f"REC-5: {f}: class {c[:100]} is neither .<class>, recipes.{name}.<class>"
                                " nor recipes.<other>[.<option>]")
        # REC-6: generators pinned by version and digest at lib/<generator>.
        for d in items(get(doc, "parameters", "kapitan", "dependencies")):
            source = str(get(d, "source"))
            m = GENERATOR.match(source)
            if get(d, "type") != "oci" or not m or get(d, "output_path") != f"lib/{m.group('name')}":
                findings.append(f"REC-6: {f}: dependency {source[:200]} is not an oci dependency"
                                " ghcr.io/kadet-hub/<generator>:<version>@sha256:<digest> with output_path lib/<generator>")
                continue
            deps[source] = {"type": "oci", "source": source, "marketplace": m.group("name"), "tag": m.group("tag"),
                            "digest": m.group("digest")}
    # REC-6: listed in the attested index under that generator and version, not yanked (CON-2).
    _, listed, _ = check_index(index, {"index_serial": 0}, list(deps.values()))
    findings += [f"REC-6: {x}" for x in listed]
    refs = sorted({f"ghcr.io/kadet-hub/{d['marketplace']}@{d['digest']}" for d in deps.values()})
    return findings, refs


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True)
    p.add_argument("--index", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--license")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    findings, refs = check(a.tree, load_json(a.index), a.policy, a.license)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write("".join(r + "\n" for r in refs))
    if findings:
        print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
