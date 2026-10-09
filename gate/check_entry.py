"""Checks on a pull request's entry and the generator manifest (GI-2, REG-*, QA-5).

Runs in the sandbox image (yaml, jsonschema, packaging). Three steps, each
reading only files the gate wrote and printing findings, exit 1 on any:

  files    --event E --files F --policy P --out O
           GI-2 on the changed files; writes the validated entry path or "".
  entry    --event E --head H --base B --reserved R --policy P --out O
           GI-1/QA-5 schema, layout, REG-2/3/5/6/8/9; writes entry.json.
  manifest --event E --entry J --manifest M --policy P
           QA-5 schema, REG-4, CMP-3, SEC-7, name match.
"""

import argparse
import json
import os
import re
import sys

import jsonschema
import yaml
from packaging.specifiers import InvalidSpecifier, SpecifierSet

KAPITAN = "0.36.3"
RENOVATE_BOT = 29139614
ENTRY_PATH = re.compile(r"^generators/([a-z][a-z0-9-]{1,38})\.yaml$")
NAME = re.compile(r"^[a-z][a-z0-9-]{1,38}$")
TAG = re.compile(r"^(?P<prefix>[A-Za-z0-9._-]*?)v?(?P<version>\d+\.\d+\.\d+)$")
# Same layout the Renovate regex manager relies on (REG-7).
LAYOUT = re.compile(r"repo: https://\S+\n\s+path: \S+\n\s+tag: \S+\n\s+sha: [0-9a-f]{40}")
MAX_ENTRY = 64 * 1024


def lines(path):
    with open(path, encoding="utf-8") as f:
        return [ln.split("#", 1)[0].strip() for ln in f if ln.split("#", 1)[0].strip()]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def schema_errors(data, schema_path):
    validator = jsonschema.Draft202012Validator(load_json(schema_path))
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message[:200]}" for e in validator.iter_errors(data)]


def actor(event, policy):
    pr = event["pull_request"]
    author = pr["user"]["id"]
    maintainers = {int(x) for x in lines(os.path.join(policy, "maintainers.txt"))}
    same_repo = pr["head"]["repo"] is not None and pr["head"]["repo"]["full_name"] == pr["base"]["repo"]["full_name"]
    return author, author in maintainers, author == RENOVATE_BOT and same_repo


def squash(name):
    return name.replace("-", "").replace("_", "")


def distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def step_files(a):
    """GI-2: which entry this pull request is about, if any."""
    event = load_json(a.event)
    _, maintainer, _ = actor(event, a.policy)
    with open(a.files, encoding="utf-8") as f:
        files = [json.loads(line) for line in f if line.strip()]
    findings = []
    entries = [f for f in files if f["filename"].startswith("generators/") or (f.get("previous_filename") or "").startswith("generators/")]
    if not maintainer:
        if len(files) != 1 or len(entries) != 1:
            findings.append(f"GI-2: a pull request from a non-maintainer changes exactly one entry file, found {len(files)} files")
        elif entries[0]["status"] not in ("added", "modified"):
            findings.append(f"GI-2: {entries[0]['status']} entries are maintainer pull requests")
    if len(entries) > 1:
        findings.append("GI-2: one entry per pull request")
    path = ""
    if not findings and entries:
        e = entries[0]
        if e["status"] == "removed":
            path = "removed:" + e["filename"]
        elif e["status"] == "renamed":
            findings.append("GI-2: renaming an entry is a removal plus a new entry")
        elif not ENTRY_PATH.match(e["filename"]):
            findings.append(f"REG-2: entry path must match generators/<name>.yaml: {e['filename'][:100]!r}")
        else:
            path = e["filename"]
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(path)
    return findings


def step_entry(a):
    event = load_json(a.event)
    author, maintainer, renovate = actor(event, a.policy)
    with open(a.path_file, encoding="utf-8") as f:
        path = f.read().strip()
    reserved_main = set(lines(os.path.join(a.base, "policy", "reserved-names.txt")))
    if path.startswith("removed:"):
        # REG-9: a removal reserves the name in the same pull request.
        name = ENTRY_PATH.match(path[len("removed:"):]).group(1)
        reserved_head = set(lines(a.reserved)) if os.path.exists(a.reserved) else set()
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"removed": name}, f)
        return [] if name in reserved_head else [f"REG-9: removing {name} must add it to policy/reserved-names.txt"]
    name = ENTRY_PATH.match(path).group(1)
    if os.path.getsize(a.head) > MAX_ENTRY:
        return ["GI-1: entry file too large"]
    with open(a.head, encoding="utf-8") as f:
        text = f.read()
    try:
        entry = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return [f"GI-1: entry is not YAML: {str(e)[:200]}"]
    findings = [f"QA-5: entry: {e}" for e in schema_errors(entry, os.path.join(a.policy, "entry.schema.json"))]
    if findings:
        return findings
    if not LAYOUT.search(text):
        findings.append("REG-7: entry source must list repo, path, tag, sha in this order")
    if name in reserved_main:
        findings.append(f"REG-2: {name} is reserved")
    base_path = os.path.join(a.base, path)
    old = None
    if os.path.exists(base_path):
        with open(base_path, encoding="utf-8") as f:
            old = yaml.safe_load(f)
    tag = TAG.match(entry["source"]["tag"])
    if old is None:
        others = {os.path.splitext(n)[0] for n in os.listdir(os.path.join(a.base, "generators"))} \
            if os.path.isdir(os.path.join(a.base, "generators")) else set()
        for other in sorted(others | reserved_main):
            if squash(other) == squash(name):
                findings.append(f"REG-3: {name} equals {other} without separators")
            elif distance(other, name) == 1:
                print(f"review: REG-3: {name} is one edit away from {other}")
    else:
        if not (maintainer or renovate or author in old["owners"]):
            findings.append("REG-5: a change to an entry is authored by an owner, a maintainer or Renovate")
        if not maintainer and (old["source"]["repo"], old["source"]["path"]) != (entry["source"]["repo"], entry["source"]["path"]):
            findings.append("REG-8: only a maintainer changes source.repo or source.path")
        old_tag = TAG.match(old["source"]["tag"])
        if old_tag.group("prefix") != tag.group("prefix"):
            findings.append("REG-6: the tag prefix must not change")
        elif tuple(map(int, tag.group("version").split("."))) <= tuple(map(int, old_tag.group("version").split("."))):
            findings.append(f"REG-6: {tag.group('version')} is not newer than {old_tag.group('version')}")
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"name": name, "new": old is None, "version": tag.group("version"), **entry["source"],
                   "owners": entry["owners"], "previous_sha": old["source"]["sha"] if old else None}, f)
    return findings


def step_manifest(a):
    event = load_json(a.event)
    author, _, _ = actor(event, a.policy)
    entry = load_json(a.entry)
    if not os.path.isfile(a.manifest) or os.path.islink(a.manifest):
        return ["QA-5: kapitan-generator.yaml missing in the generator directory"]
    with open(a.manifest, encoding="utf-8") as f:
        try:
            manifest = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return [f"QA-5: manifest is not YAML: {str(e)[:200]}"]
    findings = [f"QA-5: manifest: {e}" for e in schema_errors(manifest, os.path.join(a.policy, "manifest.schema.json"))]
    if findings:
        return findings
    if manifest["name"] != entry["name"]:
        findings.append(f"REG-2: manifest name {manifest['name']} differs from entry {entry['name']}")
    if entry["new"]:
        if author not in manifest["owners"]:
            findings.append("REG-4: the author of a new entry is listed in the manifest's owners")
        if sorted(manifest["owners"]) != sorted(entry["owners"]):
            findings.append("REG-4: entry owners equal the manifest's owners")
    try:
        if KAPITAN not in SpecifierSet(manifest["kapitan"]):
            findings.append(f"CMP-3: kapitan range {manifest['kapitan']} excludes {KAPITAN}")
    except InvalidSpecifier:
        findings.append(f"CMP-3: kapitan range {manifest['kapitan']!r} does not parse")
    allowed = {ln.split()[0] for ln in lines(os.path.join(a.policy, "binaries.txt"))} - {"kapitan-probe"}
    for b in manifest.get("binaries", []):
        if b.replace(" ", "-") not in allowed:
            findings.append(f"SEC-7: binary {b!r} is not on policy/binaries.txt")
    return findings


def main():
    p = argparse.ArgumentParser()
    p.add_argument("step", choices=["files", "entry", "manifest"])
    p.add_argument("--event", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--files")
    p.add_argument("--path-file")
    p.add_argument("--head")
    p.add_argument("--base")
    p.add_argument("--reserved")
    p.add_argument("--entry")
    p.add_argument("--manifest")
    p.add_argument("--out")
    a = p.parse_args()
    findings = {"files": step_files, "entry": step_entry, "manifest": step_manifest}[a.step](a)
    if findings:
        print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
