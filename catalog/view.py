"""Turn the index into the catalog's view model (CAT-1, CAT-2). Standard library only.

Usage: view.py --index FILE --owner OWNER [--offline] --out FILE

Sorts versions, picks each generator's latest version that is not yanked,
and adds display data from the GitHub API: owner logins and source stars.
A failed lookup leaves the user ID or no stars; --offline skips the API.
"""

import argparse
import json
import os
import re
import sys
import urllib.request

GITHUB = re.compile(r"^https://github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)\.git$")


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}", headers={"Accept": "application/vnd.github+json"})
    if os.environ.get("GH_TOKEN"):
        req.add_header("Authorization", f"Bearer {os.environ['GH_TOKEN']}")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except (OSError, ValueError):
        return None


def semver(v):
    return tuple(int(x) for x in v.split("."))


def view(index, owner, lookup):
    generators = []
    for name, versions in sorted(index.get("generators", {}).items()):
        ordered = [dict(r, version=v) for v, r in sorted(versions.items(), key=lambda kv: semver(kv[0]), reverse=True)]
        latest = next((r for r in ordered if not r.get("yanked")), None)
        shown = latest or ordered[0]
        repo = shown["source"]["repo"]
        m = GITHUB.match(repo)
        stars = None
        if m:
            data = lookup(f"/repos/{m.group(1)}/{m.group(2)}")
            stars = data.get("stargazers_count") if data else None
        owners = []
        for uid in shown.get("owners", []):
            data = lookup(f"/user/{uid}")
            owners.append({"id": str(uid), "login": data.get("login") if data else None})
        generators.append({
            "name": name,
            "description": shown.get("description", ""),
            "tags": shown.get("tags", []),
            "license": shown.get("license"),
            "latest": latest,
            "stars": stars,
            "owners": owners,
            "source_url": repo.removesuffix(".git"),
            "versions": ordered,
        })
    return {"owner": owner, "serial": index.get("serial"), "generators": generators}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--owner", required=True)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    with open(a.index, encoding="utf-8") as f:
        index = json.load(f)
    result = view(index, a.owner, (lambda _: None) if a.offline else api)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
