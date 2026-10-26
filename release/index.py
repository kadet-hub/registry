"""Build the marketplace index (PUB-4, PUB-5, REC-13). Standard library only.

Usage: index.py --versions JSONL --entries JSON [--recipe-versions JSONL --recipe-entries JSON]
                [--previous JSON] --out JSON --notes MD

--versions: one {"digest": ..., "meta": <config blob>} per attested tag.
--entries:  {name: <entry on main>} for every entry file on main.
--recipe-versions, --recipe-entries: the same for the recipes (REC-13).
--previous: the verified `latest` index, if one exists.
--notes:    where to write the GitHub release notes (PUB-12).
Exits 0 after writing --out, 3 when the content equals --previous.
"""

import argparse
import json
import sys
from datetime import datetime, timezone


def section(versions, entries, before, now):
    """The records of the generators or the recipes, from their versions, their entries and the previous index's."""
    records = {}

    def state(name, version):
        entry = entries.get(name)
        if entry is None:
            return "entry removed", []
        return (entry.get("yanked") or {}).get(version), (entry.get("advisories") or {}).get(version, [])

    for v in versions:
        meta = v["meta"]
        name, version = meta["name"], meta["version"]
        yanked, advisories = state(name, version)
        record = {k: meta[k] for k in meta if k not in ("name", "version")}
        old = (before.get(name) or {}).get(version) or {}
        record.update(digest=v["digest"], yanked=yanked, advisories=advisories, published=old.get("published", now))
        records.setdefault(name, {})[version] = record
    # INC-1: a yanked version whose artifact was deleted stays listed.
    for name, old in before.items():
        for version, record in old.items():
            yanked, advisories = state(name, version)
            if version not in records.get(name, {}) and yanked:
                records.setdefault(name, {})[version] = dict(record, yanked=yanked, advisories=advisories)
    return records


def build(versions, entries, previous, now, recipe_versions=(), recipe_entries=None):
    generators = section(versions, entries, (previous or {}).get("generators") or {}, now)
    # REC-13: the recipes in a section of their own; an index from before it has none.
    recipes = section(recipe_versions, recipe_entries or {}, (previous or {}).get("recipes") or {}, now)
    if previous is not None and previous["generators"] == generators and previous.get("recipes", {}) == recipes:
        return None
    return {"serial": (previous["serial"] + 1) if previous else 1, "generators": generators, "recipes": recipes}


def notes(previous, index):
    added, yanked = [], []
    for key, label in (("generators", ""), ("recipes", "recipe ")):
        before = (previous or {}).get(key, {})
        for name, versions in sorted(index[key].items()):
            for version, record in sorted(versions.items()):
                old = before.get(name, {}).get(version)
                if old is None:
                    added.append(f"- {label}{name} {version}")
                if record["yanked"] and not (old or {}).get("yanked"):
                    yanked.append(f"- {label}{name} {version}: {record['yanked']}")
    parts = [f"Index serial {index['serial']}" + (f", changes since serial {previous['serial']}." if previous else ".")]
    if added:
        parts.append("Added:\n\n" + "\n".join(added))
    if yanked:
        parts.append("Yanked:\n\n" + "\n".join(yanked))
    if not (added or yanked):
        parts.append("No version added or yanked.")
    return "\n\n".join(parts) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--versions", required=True)
    p.add_argument("--entries", required=True)
    p.add_argument("--recipe-versions")
    p.add_argument("--recipe-entries")
    p.add_argument("--previous")
    p.add_argument("--out", required=True)
    p.add_argument("--notes", required=True)
    a = p.parse_args()
    with open(a.versions, encoding="utf-8") as f:
        versions = [json.loads(line) for line in f if line.strip()]
    with open(a.entries, encoding="utf-8") as f:
        entries = json.load(f)
    recipe_versions, recipe_entries = [], {}
    if a.recipe_versions:
        with open(a.recipe_versions, encoding="utf-8") as f:
            recipe_versions = [json.loads(line) for line in f if line.strip()]
        with open(a.recipe_entries, encoding="utf-8") as f:
            recipe_entries = json.load(f)
    previous = None
    if a.previous:
        with open(a.previous, encoding="utf-8") as f:
            previous = json.load(f)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index = build(versions, entries, previous, now, recipe_versions, recipe_entries)
    if index is None:
        print("index unchanged")
        return 3
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(index, f, sort_keys=True, indent=1)
    with open(a.notes, "w", encoding="utf-8") as f:
        f.write(notes(previous, index))
    print(f"index serial {index['serial']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
