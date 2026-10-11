"""Validate the compiled output against the generator's own schemas (QA-7).

Usage: schema_check.py --schemas DIR --out DIR [--result FILE]

DIR holds <group>/<kind>_<version>.json and sources.yaml. Every document
with apiVersion and kind whose schema exists must validate; a group
without schemas is a review line, a group with schemas but without a
sources.yaml entry a finding. --result receives the software and versions
of the groups used, as JSON. Exits 1 on any finding.
"""

import argparse
import json
import os
import sys

import jsonschema
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tag_check import files


def documents(path):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        docs = [json.loads(text)] if path.endswith(".json") else list(yaml.safe_load_all(text))
    except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError):
        return
    for doc in docs:
        for item in doc if isinstance(doc, list) else [doc]:
            if isinstance(item, dict) and isinstance(item.get("apiVersion"), str) and isinstance(item.get("kind"), str):
                yield item


def schema_path(schemas, api_version, kind):
    group, _, version = api_version.rpartition("/")
    return group or "core", os.path.join(schemas, group or "core", f"{kind.lower()}_{version}.json")


def check(schemas, out):
    try:
        with open(os.path.join(schemas, "sources.yaml"), encoding="utf-8") as f:
            sources = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return ["QA-7: schemas/sources.yaml is missing or not YAML"], [], []
    findings, lines, used, cache, missing = [], [], {}, {}, set()
    for rel in files(out):
        if not rel.endswith((".yml", ".yaml", ".json")):
            continue
        for doc in documents(os.path.join(out, rel)):
            group, path = schema_path(schemas, doc["apiVersion"], doc["kind"])
            if not os.path.isfile(path):
                if (doc["apiVersion"], doc["kind"]) not in missing:
                    missing.add((doc["apiVersion"], doc["kind"]))
                    lines.append(f"review: {rel}: no schema for {doc['apiVersion']} {doc['kind']}")
                continue
            if not isinstance(sources.get(group), dict):
                findings.append(f"QA-7: {group}: schemas without an entry in sources.yaml")
                continue
            if path not in cache:
                with open(path, encoding="utf-8") as f:
                    schema = json.load(f)
                cls = jsonschema.validators.validator_for(schema, default=jsonschema.Draft7Validator)
                cache[path] = cls(schema)
            errors = sorted(cache[path].iter_errors(doc), key=lambda e: list(e.absolute_path))
            for e in errors[:5]:
                where = "/".join(str(p) for p in e.absolute_path) or "(root)"
                findings.append(f"QA-7: {rel}: {doc['kind']} {where}: {e.message[:200]}")
            used[group] = sources[group]
    result = []
    for s in used.values():
        entry = {k: str(s.get(k, "")) for k in ("software", "version", "source")}
        if entry not in result:
            result.append(entry)
    result.sort(key=lambda s: s["software"])
    lines += [f"QA-7: validated against {s['software']} {s['version']}" for s in result]
    return sorted(set(findings)), lines, result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--schemas", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--result")
    a = p.parse_args()
    findings, lines, result = check(a.schemas, a.out)
    if findings or lines:
        print("\n".join(findings + lines))
    if a.result:
        with open(a.result, "w", encoding="utf-8") as f:
            json.dump(result, f)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
