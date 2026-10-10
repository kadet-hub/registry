"""Build the marketplace index (PUB-4, PUB-5). Standard library only.

Usage: index.py --versions JSONL --entries JSON [--previous JSON] --out JSON

--versions: one {"digest": ..., "meta": <config blob>} per attested tag.
--entries:  {name: <entry on main>} for every entry file on main.
--previous: the verified `latest` index, if one exists.
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--versions", required=True)
    p.add_argument("--entries", required=True)
    p.add_argument("--previous")
    p.add_argument("--out", required=True)
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
    print(f"index serial {index['serial']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
