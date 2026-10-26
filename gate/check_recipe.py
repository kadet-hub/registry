"""Checks on a recipe's files (REC-4, the include rule of REC-5, REC-6, REC-15 to REC-17, REC-13).

Usage: check_recipe.py --tree DIR --index FILE --policy DIR [--license FILE] [--requires FILE] --out FILE

Runs in the sandbox image without network. DIR is the recipe as
`fetch_tree.py --recipe` writes it, next to the other recipes of the
commit, FILE for --index the attested index, for --license the source
repository's root LICENSE and for --requires the JSON list of recipes it
requires (REC-17). Writes to --out as JSON the generators whose
attestation the gate verifies with where they unpack, the binaries the
index lists for them, the included and required recipes and the
published versions they resolve to (REC-8, REC-16, REC-17), what REC-10
shows, and the description and license the index records (REC-13).
Prints findings; exits 1 on any.
"""

import argparse
import json
import os
import re
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [HERE, os.path.join(HERE, "..", "consumer"), os.path.join(HERE, "..", "release")]  # python -I does not add the script dir
from check_entry import LICENSE_HEAD, lines, load_json, read_text  # noqa: E402
from plan import check_index  # noqa: E402
from tree import read_dir, tree_id  # noqa: E402

GENERATOR = re.compile(r"^ghcr\.io/kadet-hub/(?P<name>[a-z][a-z0-9-]{1,38}):(?P<tag>[A-Za-z0-9_][A-Za-z0-9._-]{0,127})"
                       r"@(?P<digest>sha256:[0-9a-f]{64})$")
INCLUDED = re.compile(r"^recipes\.(?P<other>[a-z][a-z0-9-]{1,38})(\.[A-Za-z0-9_-]+)?$")
README_LINE = {"source": re.compile(r"^Source: .*$", re.M), "level": re.compile(r"^Level: .*$", re.M)}
# QA-5a: the characters manifest.schema.json bans from a description; tab, line feed and carriage return are whitespace here.
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def get(data, *keys):
    """data[k1][k2]..., None where a level is not a mapping."""
    for k in keys:
        data = data.get(k) if isinstance(data, dict) else None
    return data


def items(data):
    return data if isinstance(data, list) else []


def load_classes(tree, files, findings, label="REC-5", prefix=""):
    """The class files at the root of tree, parsed."""
    classes = {}
    for f in files:
        if "/" not in f and f.endswith(".yml"):
            try:
                with open(os.path.join(tree, f), encoding="utf-8") as fh:
                    classes[prefix + f] = yaml.safe_load(fh)
            except (UnicodeDecodeError, yaml.YAMLError, RecursionError) as e:
                findings.append(f"{label}: {prefix}{f} is not YAML: {str(e)[:200]}")
    return classes


def generators(index, classes, lib, findings):
    """REC-6: the generators the class files pin, listed in the attested index (CON-2); the pins,
    each reference to verify with where it unpacks below lib, and their binaries."""
    deps = {}
    for f, doc in classes.items():
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
    binaries, listed, _ = check_index(index, {"index_serial": 0}, list(deps.values()))
    findings += [f"REC-6: {x}" for x in listed]
    pull = sorted({(f"ghcr.io/kadet-hub/{d['marketplace']}@{d['digest']}", f"{lib}/{d['marketplace']}") for d in deps.values()})
    return deps, [list(p) for p in pull], binaries


def description(readme, findings):
    """REC-13: the first paragraph after the README's heading (RCP-32), its whitespace collapsed; QA-5a applies."""
    lines_ = (readme or "").split("\n")
    start = next((i + 1 for i, ln in enumerate(lines_) if ln.startswith("#")), len(lines_))
    para = []
    for ln in lines_[start:]:
        if ln.strip(" \t\r"):
            para.append(ln)
        elif para:
            break
    if not para or para[0].startswith("#"):
        findings.append("REC-13: README.md has no paragraph after its heading for the description (RCP-32)")
        return None
    if any(CONTROL.search(ln) for ln in para):
        findings.append("QA-5a: README.md: the first paragraph holds a control or bidirectional formatting character")
        return None
    text = re.sub(r"[ \t\r]+", " ", " ".join(para)).strip()
    if len(text) > 300:
        findings.append(f"REC-13: README.md: the description has {len(text)} characters, RCP-32 allows 300")
        return None
    return text


def published(index, recipe, rule, findings):
    """REC-16: the oldest version the index lists, not yanked, with the tree of the recipe's directory without tests."""
    name = os.path.basename(recipe)
    if not os.path.isfile(os.path.join(recipe, "init.yml")):
        findings.append(f"{rule}: {name} is not a recipe directory at source.sha")
        return None
    tree = tree_id({p: f for p, f in read_dir(recipe).items() if p.split("/")[0] != "tests"})
    found = {v: r for v, r in (get(index, "recipes", name) or {}).items() if get(r, "tree") == tree}
    listed = sorted((v for v, r in found.items() if not get(r, "yanked")), key=lambda v: tuple(map(int, v.split("."))))
    if not listed:
        findings.append(f"{rule}: the index lists " + (f"{name} {', '.join(sorted(found))} with tree {tree} only yanked"
                                                        if found else f"no version of {name} with tree {tree}"))
        return None
    return {"rule": rule, "version": listed[0], "digest": get(found[listed[0]], "digest")}


def check(tree, index, policy, license_path, required=()):
    """Findings, and the generators to verify, their binaries, the included and required recipes and their versions,
    the description and the license."""
    name = os.path.basename(os.path.normpath(tree))
    prefix = f"inventory/classes/recipes/{name}/"
    files = sorted(os.path.relpath(os.path.join(r, f), tree) for r, _, fs in os.walk(tree) for f in fs)
    shipped = [f for f in files if not f.startswith("tests/")]
    findings = []
    classes = load_classes(tree, shipped, findings)
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
    # REC-4: the license of the repository root's LICENSE, as QA-2 matches it; REC-13 records its identifier.
    text = read_text(license_path, LICENSE_HEAD) if license_path else None
    licenses = [ln.split(None, 1) for ln in lines(os.path.join(policy, "licenses.txt"))]
    spdx = next((i for i, p in licenses if text is not None and re.search(p, " ".join(text.split()))), None)
    if spdx is None:
        findings.append("REC-4: the source repository's root LICENSE is missing or matches no license on policy/licenses.txt")

    included = set()
    for f, doc in classes.items():
        # REC-5: classes of the recipe itself or of an included recipe, which REC-16 resolves.
        for cls in items(get(doc, "classes")):
            c = str(cls)
            m = INCLUDED.match(c)
            if m and m.group("other") != name:
                included.add(m.group("other"))
            elif not c.startswith((".", f"recipes.{name}.")):
                findings.append(f"REC-5: {f}: class {c[:100]} is neither .<class>, recipes.{name}.<class>"
                                " nor recipes.<other>[.<option>]")
    # REC-6, REC-8, REC-17: the generators of the compile with the included recipes, and of each required recipe's own.
    parent = os.path.dirname(os.path.normpath(tree))

    def classes_of(others):
        out = {}
        for other in others:
            d = os.path.join(parent, other)
            if os.path.isdir(d):
                files = sorted(f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f)))
                out.update(load_classes(d, files, findings, "REC-6", f"{other}/"))
        return out

    deps, pull, binaries = generators(index, {**classes, **classes_of(sorted(included))}, "lib", findings)
    readme = read_text(os.path.join(tree, "README.md"))
    result = {"pull": pull, "binaries": binaries, "included": sorted(included), "required": {}, "recipes": {},
              "pins": sorted(deps), **{k: r.findall(readme or "")[:1] for k, r in README_LINE.items()},
              "description": description(readme, findings), "license": spdx}
    for r in required:
        _, pull, result["required"][r] = generators(index, classes_of([r]), f"requires/{r}/lib", findings)
        result["pull"] += pull
    # REC-16, REC-17: the published version of each included and each required recipe.
    for other, rule in [*((o, "REC-16") for o in sorted(included)), *((r, "REC-17") for r in required)]:
        version = published(index, os.path.join(parent, other), rule, findings)
        if version:
            result["recipes"][other] = version
    return findings, result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True)
    p.add_argument("--index", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--license")
    p.add_argument("--requires")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    findings, result = check(a.tree, load_json(a.index), a.policy, a.license, load_json(a.requires) if a.requires else [])
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f)
    if findings:
        print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
