"""Build the marketplace index (PUB-4, PUB-5). Standard library only.

Usage: index.py --versions JSONL --entries JSON [--previous JSON] --out JSON --notes MD

--versions: one {"digest": ..., "meta": <config blob>} per attested tag.
--entries:  {name: <entry on main>} for every entry file on main.
--previous: the verified `latest` index, if one exists.
--notes:    where to write the GitHub release notes (PUB-12).
Exits 0 after writing --out, 3 when the content equals --previous.
"""

import argparse
import json
import sys
from datetime import datetime, timezone


def build(versions, entries, previous, now):
    generators = {}

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
        before = ((previous or {}).get("generators", {}).get(name) or {}).get(version) or {}
        record.update(digest=v["digest"], yanked=yanked, advisories=advisories, published=before.get("published", now))
        generators.setdefault(name, {})[version] = record
    # INC-1: a yanked version whose artifact was deleted stays listed.
    for name, old in ((previous or {}).get("generators") or {}).items():
        for version, record in old.items():
            yanked, advisories = state(name, version)
            if version not in generators.get(name, {}) and yanked:
                generators.setdefault(name, {})[version] = dict(record, yanked=yanked, advisories=advisories)
    if previous is not None and previous["generators"] == generators:
        return None
    return {"serial": (previous["serial"] + 1) if previous else 1, "generators": generators}


def notes(previous, index):
    before = (previous or {}).get("generators", {})
    added, yanked = [], []
    for name, versions in sorted(index["generators"].items()):
        for version, record in sorted(versions.items()):
            old = before.get(name, {}).get(version)
            if old is None:
                added.append(f"- {name} {version}")
            if record["yanked"] and not (old or {}).get("yanked"):
                yanked.append(f"- {name} {version}: {record['yanked']}")
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
    p.add_argument("--previous")
    p.add_argument("--out", required=True)
    p.add_argument("--notes", required=True)
    a = p.parse_args()
    with open(a.versions, encoding="utf-8") as f:
        versions = [json.loads(line) for line in f if line.strip()]
    with open(a.entries, encoding="utf-8") as f:
        entries = json.load(f)
    previous = None
    if a.previous:
        with open(a.previous, encoding="utf-8") as f:
            previous = json.load(f)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    index = build(versions, entries, previous, now)
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
