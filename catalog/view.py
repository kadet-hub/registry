"""Turn the index into the catalog's view model (CAT-1, CAT-2). Standard library only.

Usage: view.py --index FILE --owner OWNER [--offline] [--artifacts DIR] [--sboms DIR] [--rekor FILE] --out FILE

Sorts versions, picks each generator's latest version that is not yanked,
and adds display data from the GitHub API: owner logins and source stars.
A failed lookup leaves the user ID or no stars; --offline skips the API.
DIR/<name>.tar is the latest version's artifact layer; its README.md is
shown on the generator page (CAT-7). DIR/<name>/<version>.spdx.json marks a
version whose SBOM the site offers (CAT-14); --rekor maps name and version to
the transparency log index of the verified attestation (CAT-17).
"""

import argparse
import hashlib
import json
import os
import re
import sys
import tarfile
import urllib.request

GITHUB = re.compile(r"^https://github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)\.git$")
README_MAX = 256 * 1024
HUES = 8


def readme(path):
    """README.md at the root of the artifact layer, or None."""
    try:
        with tarfile.open(path) as t:
            m = next((m for m in t.getmembers() if m.isfile() and m.name.removeprefix("./") == "README.md"), None)
            if m is None or m.size > README_MAX:
                return None
            return t.extractfile(m).read().decode("utf-8", errors="replace")
    except (OSError, tarfile.TarError):
        return None


def blob_url(source):
    """Base URL of source.path at source.sha, for relative README links."""
    base = source["repo"].removesuffix(".git")
    sep = "/blob/" if base.startswith("https://github.com/") else "/-/blob/"
    path = "" if source["path"] == "." else source["path"].strip("/") + "/"
    return f"{base}{sep}{source['sha']}/{path}"


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


def view(index, owner, lookup, artifacts=None, sboms=None, rekor=None):
    generators = []
    for name, versions in sorted(index.get("generators", {}).items()):
        ordered = [dict(r, version=v, sbom=bool(sboms) and os.path.isfile(os.path.join(sboms, name, f"{v}.spdx.json")),
                        rekor=(rekor or {}).get(name, {}).get(v))
                   for v, r in sorted(versions.items(), key=lambda kv: semver(kv[0]), reverse=True)]
        latest = next((r for r in ordered if not r.get("yanked")), None)
        shown = latest or ordered[0]
        repo = shown["source"]["repo"]
        m = GITHUB.match(repo)
        stars = None
        if m:
            data = lookup(f"/repos/{m.group(1)}/{m.group(2)}")
            stars = str(data["stargazers_count"]) if data and "stargazers_count" in data else None  # 0 must show
        owners = []
        for uid in shown.get("owners", []):
            data = lookup(f"/user/{uid}")
            owners.append({"id": str(uid), "login": data.get("login") if data else None})
        tar = os.path.join(artifacts, f"{name}.tar") if artifacts and latest else None
        generators.append({
            "name": name,
            "monogram": name[0].upper(),
            "hue": int(hashlib.sha256(name.encode()).hexdigest(), 16) % HUES,
            "readme": readme(tar) if tar and os.path.isfile(tar) else None,
            "blob_url": blob_url(shown["source"]),
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


def load_rekor(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, TypeError, ValueError):
        return {}
    return {n: {v: str(i) for v, i in vs.items() if str(i).isdigit()} for n, vs in data.items() if isinstance(vs, dict)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--owner", required=True)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--artifacts")
    p.add_argument("--sboms")
    p.add_argument("--rekor")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    with open(a.index, encoding="utf-8") as f:
        index = json.load(f)
    result = view(index, a.owner, (lambda _: None) if a.offline else api, a.artifacts, a.sboms, load_rekor(a.rekor))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
