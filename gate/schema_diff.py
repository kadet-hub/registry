"""Compare the schema sources of the approved and the proposed tree (QA-7, QA-8).

Usage: schema_diff.py --old DIR --new DIR

Prints one line per schema group: software and version before and after,
so the reviewer sees whether a bump moved its schemas along. Runs in the
sandbox image; the trees are data only.
"""

import argparse
import os
import sys

import yaml


def sources(tree):
    try:
        with open(os.path.join(tree, "kapitan-generator.yaml"), encoding="utf-8") as f:
            schemas = (yaml.safe_load(f) or {}).get("schemas")
        if not isinstance(schemas, str) or ".." in schemas or schemas.startswith("/"):
            return {}
        with open(os.path.join(tree, schemas, "sources.yaml"), encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return {str(g): s for g, s in data.items() if isinstance(s, dict)}


def describe(s):
    return f"{s.get('software', '?')} {s.get('version', '?')}" if s else "none"


def diff(old, new):
    lines = []
    for group in sorted(set(old) | set(new)):
        a, b = old.get(group), new.get(group)
        same = " (unchanged)" if a and b and str(a.get("version")) == str(b.get("version")) else ""
        check = "QA-8" if group.startswith("terraform/") else "QA-7"
        lines.append(f"{check}: schemas {group}: {describe(a)} -> {describe(b)}{same}")
    return lines


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--old", required=True)
    p.add_argument("--new", required=True)
    a = p.parse_args()
    lines = diff(sources(a.old), sources(a.new))
    if lines:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
