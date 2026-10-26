"""Turn the index into the catalog's view model (CAT-1, CAT-2). Standard library only.

Usage: view.py --index FILE --owner OWNER [--offline] [--artifacts DIR] [--sboms DIR] [--rekor FILE] [--discussions FILE] [--pages DIR] [--previous FILE] [--diffs DIR] [--wanted FILE] [--gate FILE] --out FILE

Sorts versions, picks each generator's latest version that is not yanked,
and adds display data from the GitHub API: owner logins and source stars.
A failed lookup leaves the user ID or no stars; --offline skips the API.
DIR/<name>.tar is the latest version's artifact layer; its README.md is
shown on the generator page (CAT-7), its CHANGELOG.md sections in the
weekly digest (CAT-36b), its schemas/sources.yaml the software of its
groups on /kinds/ (CAT-29c). DIR/<name>/<version>.spdx.json marks a
version whose SBOM the site offers (CAT-14); the schemas it lists give the
kinds of a latest listed version without a kinds record (CAT-29); --rekor
maps name and version to the transparency log index of the verified
attestation (CAT-17);
--discussions maps name to the URL and 👍 count of its discussion (CAT-20).
DIR/<name>.html is the generator's public package page; its "Total
downloads" are the pulls of the popularity score (CAT-23). --previous is the
catalog.json of the last build; its README and CHANGELOG sections are used when the latest digest
is unchanged and no artifact layer was fetched. --diffs DIR/<name>/<version>.output.diff
is a version's verified output diff; its first lines are shown (CAT-27).
--wanted is the list of open generator requests (CAT-31).
--gate is the registry's pull requests with their changed paths and comments;
only counts and requirement IDs are kept (CAT-33).
The index's recipes become recipes[] (CAT-38b).
"""

import argparse
import datetime
import hashlib
import html
import json
import math
import os
import re
import sys
import tarfile
import urllib.request

GITHUB = re.compile(r"^https://github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)\.git$")
README_MAX = 256 * 1024
HUES = 8
DIFF_LINES = 150
GROUP, VERSION = r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", r"v[0-9]+(?:(?:alpha|beta)[0-9]+)?"
SCHEMA = re.compile(rf"^\./schemas/({GROUP})/([a-z0-9]+)_({VERSION})\.json$")  # QA-7 layout
RENDERED = [re.compile(p) for p in (GROUP, r"[A-Za-z0-9]+", VERSION)]  # group, kind, version of a PUB-10 record
STAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
# CAT-29c: the groups kube-apiserver v1.37.1 serves without CRDs, as QA-10 discovers them; `core` for the core group.
BUILTIN = {"core", "admissionregistration.k8s.io", "apiextensions.k8s.io", "apiregistration.k8s.io", "apps", "authentication.k8s.io",
           "authorization.k8s.io", "autoscaling", "batch", "certificates.k8s.io", "coordination.k8s.io", "discovery.k8s.io",
           "events.k8s.io", "flowcontrol.apiserver.k8s.io", "networking.k8s.io", "node.k8s.io", "policy", "rbac.authorization.k8s.io",
           "resource.k8s.io", "scheduling.k8s.io", "storage.k8s.io", "storagemigration.k8s.io"}
SOURCE_KEY = re.compile(r"[a-z0-9][a-z0-9./-]*:")  # CAT-29c: a QA-7 sources.yaml entry, <group> or <group>/<version>
SOURCE_SOFTWARE = re.compile(r"  software: ([A-Za-z0-9][^\"'#:{}\[\]]*?)[ \t]*")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]")  # Cc but tab and newline, Bidi_Control


def readme(path, name="README.md"):
    """README.md (or another file) at the root of the artifact layer, or None."""
    try:
        with tarfile.open(path) as t:
            m = next((m for m in t.getmembers() if m.isfile() and m.name.removeprefix("./") == name), None)
            if m is None or m.size > README_MAX:
                return None
            return t.extractfile(m).read().decode("utf-8", errors="replace")
    except (OSError, tarfile.TarError):
        return None


ATX = re.compile(r"^ {0,3}(#{1,6})(?=[ \t]|$)")
FENCE = re.compile(r"^\s*(?:```|~~~)")
CHANGELOG_LINES = 15


def changelog_sections(text, versions):
    """CAT-36b: {version: its CHANGELOG section} without control characters, sub-headings from h4 down."""
    found, current = {}, None
    fence = False
    for line in CONTROL.sub("", text or "").split("\n"):
        h = None if fence else ATX.match(line)
        fence ^= bool(FENCE.match(line))
        if h and current and len(h.group(1)) <= current[1]:
            current = None
        if h and current is None:
            current = next(((v, len(h.group(1))) for v in versions if v not in found  # QA-1's match
                            and re.search(rf"(?<![\w.])v?{re.escape(v)}(?![\w.-])", line)), None)
            if current:
                found[current[0]] = []
            continue
        if h:
            line = "#" * min(6, 3 + len(h.group(1)) - current[1]) + line[h.end():]
        if current:
            found[current[0]].append(line)
    return {v: "\n".join(lines).strip("\n") for v, lines in found.items() if "".join(lines).strip()}


def schema_kinds(path):
    """CAT-29: sorted (group, kind, version) of the schemas/<group>/<kind>_<version>.json an SBOM lists."""
    try:
        with open(path, encoding="utf-8") as f:
            files = json.load(f)["files"]
        names = [f["fileName"] for f in files if isinstance(f, dict) and isinstance(f.get("fileName"), str)]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return sorted({m.groups() for m in map(SCHEMA.match, names) if m and m.group(1) != "terraform"})  # QA-8 extracts


def schema_sources(text):
    """CAT-29c: {entry: its software or None} of a sources.yaml in the QA-7 block form, {} for a file in any other form."""
    found, key = {}, None
    for line in (text or "").splitlines():
        if line.startswith("  software:"):
            m = SOURCE_SOFTWARE.fullmatch(line)
            if not m or key is None or CONTROL.search(m.group(1)):
                return {}
            found[key] = m.group(1)
        elif line[:1] not in ("", " ", "#"):
            if not SOURCE_KEY.fullmatch(line.rstrip()):
                return {}
            key = line.rstrip()[:-1]
            found[key] = None
    return found


def rendered_kinds(record):
    """CAT-29: sorted (group, kind, version) of a version's kinds record (PUB-10), `core` for no group; None without one."""
    if not isinstance(record.get("kinds"), list):
        return None
    found = set()
    for k in record["kinds"]:
        if isinstance(k, dict) and all(isinstance(k.get(f), str) for f in ("group", "kind", "version")):
            t = (k["group"] or "core", k["kind"], k["version"])
            if all(p.fullmatch(v) for p, v in zip(RENDERED, t)):
                found.add(t)
    return sorted(found)


def diff_excerpt(path):
    """The first DIFF_LINES lines of an output diff without control characters, and how many follow, or None."""
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as f:
            lines = CONTROL.sub("", f.read()).split("\n")
    except OSError:
        return None
    if lines[-1] == "":
        lines.pop()
    return {"text": "\n".join(lines[:DIFF_LINES]), "more": max(len(lines) - DIFF_LINES, 0)}


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


PULLS = re.compile(r"Total downloads\s*([0-9][0-9.,]*)\s*([kKmM]?)")


def pulls(path):
    """Total downloads from a package page, or None when it cannot be read."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = html.unescape(re.sub(r"<[^>]+>", " ", f.read()))
    except OSError:
        return None
    m = PULLS.search(re.sub(r"\s+", " ", text))
    if not m:
        return None
    number = float(m.group(1).replace(",", ""))
    return int(number * {"": 1, "k": 1000, "m": 1000000}[m.group(2).lower()])


def score(up, stars, shared, downloads):
    """CAT-23: round(10·log2(1 + 👍) + 4·log2(1 + stars ÷ n) + 2·log2(1 + pulls))."""
    return round(10 * math.log2(1 + up) + 4 * math.log2(1 + stars / shared) + 2 * math.log2(1 + downloads))


def semver(v):
    return tuple(int(x) for x in v.split("."))


def view(index, owner, lookup, artifacts=None, sboms=None, rekor=None, discussions=None, pages=None, previous=None, diffs=None):
    generators, by_kind, named = [], {}, {}  # CAT-29: {section: {lower-case kind: entry}}; CAT-29c: {section: software}
    for name, versions in sorted(index.get("generators", {}).items()):
        ordered = [dict(r, version=v, sbom=bool(sboms) and os.path.isfile(os.path.join(sboms, name, f"{v}.spdx.json")),
                        rekor=(rekor or {}).get(name, {}).get(v),
                        diff=diff_excerpt(os.path.join(diffs, name, f"{v}.output.diff")) if diffs else None)
                   for v, r in sorted(versions.items(), key=lambda kv: semver(kv[0]), reverse=True)]
        for r in ordered:  # CAT-15: one entry per software and version, the first source wins
            first = {}
            for c in r.get("compatibility") or []:
                first.setdefault((c["software"], c["version"]), c)
            if first:
                r["compatibility"] = list(first.values())
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
        kept = (previous or {}).get((name, (latest or {}).get("digest")), {})
        rendered = rendered_kinds(latest) if latest else None
        kinds = rendered if rendered is not None else (
            schema_kinds(os.path.join(sboms, name, f"{latest['version']}.spdx.json")) if sboms and latest else [])
        sources = schema_sources(readme(tar, "schemas/sources.yaml")) if tar and os.path.isfile(tar) else kept.get("sources")
        entries = sources or {}
        for group, kind, version in kinds:
            section = version if group == "core" and version != "v1" else group  # CAT-29: Talos's v1alpha1 is no core kind
            entry = f"{group}/{version}" if f"{group}/{version}" in entries else group  # QA-7: the versioned entry takes precedence
            named.setdefault(section, set()).update({entries.get(entry)} - {None, "Kubernetes"})
            e = by_kind.setdefault(section, {}).setdefault(kind.lower(), {"name": kind, "page": False, "rendered": [], "schema": [], "versions": {}})
            if rendered is None:
                if name not in e["schema"]:
                    e["schema"].append(name)
                continue
            if not e["rendered"]:
                e["name"] = kind  # the recorded case over the file name's
            if name not in e["rendered"]:
                e["rendered"].append(name)
            e["versions"].setdefault(version if group == "core" else f"{group}/{version}", []).append(name)
            e["page"] = len(e["rendered"]) > 1  # CAT-29b
        generators.append({
            "name": name,
            "monogram": name[0].upper(),
            "hue": int(hashlib.sha256(name.encode()).hexdigest(), 16) % HUES,
            "readme": readme(tar) if tar and os.path.isfile(tar) else kept.get("readme"),
            "changelog": changelog_sections(readme(tar, "CHANGELOG.md"), [r["version"] for r in ordered if not r.get("yanked")])
                         if tar and os.path.isfile(tar) else kept.get("changelog"),  # CAT-36b
            "blob_url": blob_url(shown["source"]),
            "description": shown.get("description", ""),
            "tags": shown.get("tags", []),
            "kinds": sorted({k for _, k, _ in kinds}),
            "sources": sources,  # CAT-29c, kept for the next build
            "license": shown.get("license"),
            "latest": latest,
            "stars": stars,
            "discussion": (discussions or {}).get(name),
            "pulls": pulls(os.path.join(pages, f"{name}.html")) if pages else None,
            "owners": owners,
            "source_url": repo.removesuffix(".git"),
            "versions": ordered,
        })
    listed = [g["source_url"] for g in generators if g["latest"]]
    for g in generators:
        n = listed.count(g["source_url"])
        g["stars_shared"] = n if n > 1 and g["stars"] is not None else None
        up = g["discussion"]["up"] if g["discussion"] else 0
        g["score"] = score(up, int(g["stars"] or 0), max(n, 1), g["pulls"] or 0)
    sections = {"builtin": sorted(s for s in by_kind if s in BUILTIN), "custom": sorted(s for s in by_kind if s not in BUILTIN)}
    labels = {s: named[s].pop() for s in sections["custom"] if len(named[s]) == 1}
    return {"owner": owner, "serial": index.get("serial"), "generators": generators, "kinds": by_kind, "sections": sections,
            "software": labels, "releases": releases(index, {g["name"]: g["changelog"] or {} for g in generators}),
            "recipes": recipes(index)}


def recipes(index):
    """CAT-38, CAT-38b: each recipe's versions, newest first, every generator pin with the index's yank reason."""
    found = []
    for name, versions in sorted((index.get("recipes") or {}).items()):
        ordered = [dict(r, version=v, chart=r.get("chart"), generators=[
                       dict(p, yanked=(index.get("generators", {}).get(p["name"], {}).get(p["version"]) or {}).get("yanked"))
                       for p in r.get("generators") or []])
                   for v, r in sorted(versions.items(), key=lambda kv: semver(kv[0]), reverse=True)]
        latest = next((r for r in ordered if not r.get("yanked")), None)
        shown = latest or ordered[0]
        found.append({"name": name, "description": shown.get("description", ""), "latest": latest,
                      "blob_url": blob_url(shown["source"]), "versions": ordered})
    return found


FIRST_WEEK = datetime.date(2026, 10, 12)


def excerpt(g, found):
    """CAT-36b: the CHANGELOG sections of g's versions, newest first, CHANGELOG_LINES lines in all."""
    g["entries"], g["cut"], left = [], False, CHANGELOG_LINES
    for v in reversed(g["versions"]):
        if not found.get(v):
            continue
        if left <= 0:
            g["cut"] = True
            break
        lines = found[v].split("\n")
        g["cut"] |= len(lines) > left
        lines = lines[:left]
        left -= len(lines)
        fences = [m.group() for m in map(FENCE.match, lines) if m]
        if len(fences) % 2:  # cut inside a fenced code block: close it
            lines.append(fences[-1])
        g["entries"].append({"version": v, "text": "\n".join(lines)})


def releases(index, changelogs=None):
    """CAT-36b: per week from FIRST_WEEK, each generator's listed versions published that week, with their CHANGELOG sections."""
    weeks = {}
    for name, versions in sorted(index.get("generators", {}).items()):
        dated = sorted((r["published"], v, r) for v, r in versions.items()
                       if isinstance(r.get("published"), str) and STAMP.match(r["published"]))
        first = dated[0][0] if dated else None
        for published, v, r in dated:
            day = datetime.date.fromisoformat(published[:10])
            monday = day - datetime.timedelta(days=day.weekday())
            if monday < FIRST_WEEK or r.get("yanked"):
                continue
            g = weeks.setdefault(monday, {}).setdefault(name, {"name": name, "versions": [], "new": False})
            g["versions"].append(v)
            g["new"] |= published == first
            g["blob_url"] = blob_url(r["source"])
            g["changelog"] = g["blob_url"] + "CHANGELOG.md"
    for gs in weeks.values():
        for g in gs.values():
            excerpt(g, (changelogs or {}).get(g["name"], {}))
    return [{"monday": m.isoformat(), "date": (m + datetime.timedelta(days=7)).isoformat(),
             "sunday": (m + datetime.timedelta(days=6)).isoformat(), "generators": list(gs.values())}
            for m, gs in sorted(weeks.items())]


def load_rekor(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, TypeError, ValueError):
        return {}
    return {n: {v: str(i) for v, i in vs.items() if str(i).isdigit()} for n, vs in data.items() if isinstance(vs, dict)}


def load_discussions(path, owner):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, TypeError, ValueError):
        return {}
    prefix = f"https://github.com/{owner}/registry/discussions/"
    return {n: {"url": d["url"], "up": d["up"]} for n, d in data.items()
            if isinstance(d, dict) and str(d.get("url", "")).startswith(prefix) and type(d.get("up")) is int}


def load_wanted(path):
    """CAT-31: open generator requests, most 👍 first, then oldest first; None when they were not read."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, TypeError, ValueError):
        return None
    if not isinstance(data, list):
        return None
    keep = [{k: r[k] for k in ("number", "title", "up", "created", "updated")} for r in data
            if isinstance(r, dict) and type(r.get("number")) is int and type(r.get("up")) is int and isinstance(r.get("title"), str)
            and all(isinstance(r.get(k), str) and STAMP.match(r[k]) for k in ("created", "updated"))]
    return sorted(keep, key=lambda r: (-r["up"], r["created"], r["number"]))


ENTRY = re.compile(r"^generators/[^/]+\.yaml$")
FINDING = re.compile(r"((?:GI|REG|SEC|QA|CMP)-[0-9]+[a-z]?): ")
# CAT-33: lines of the finding form that the gate prints for checks that passed.
PASSED = re.compile(r"QA-6: tag [a-z]+: (?!no )|QA-(?:7|8|10|11): validated against |CMP-4: krab |SEC-12: declared ")


def findings(report):
    """CAT-33: requirement IDs of the finding lines in a gate report, before its section "## Output diff"."""
    ids = set()
    for line in report.split("\n"):
        if line == "## Output diff":
            break
        m = FINDING.match(line)
        if m and not PASSED.match(line):
            ids.add(m.group(1))
    return ids


def load_gate(path):
    """CAT-33: entry pull requests and the requirements of their failed gate runs; None when they were not read."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, TypeError, ValueError):
        return None
    if not isinstance(data, list):
        return None
    kinds = ("new", "update", "other", "all")
    prs, rejected, by_id, none = dict.fromkeys(kinds, 0), dict.fromkeys(kinds, 0), {}, 0
    for pr in data:
        if not isinstance(pr, dict) or not any(isinstance(f, str) and ENTRY.match(f) for f in pr.get("files") or []):
            continue
        runs = [v.partition("\n```") for c in pr.get("comments") or [] if isinstance(c, dict) and c.get("author") == "github-actions"
                for v in c.get("versions") or [] if isinstance(v, str) and v.startswith("<!-- kadet-hub-gate -->\n")]
        if not runs:
            continue
        kind = ("update" if any("\nCode diff since the approved version: " in h for h, _, _ in runs) else
                "new" if any("\nNew entry; source tree: " in h for h, _, _ in runs) else "other")
        failed = [findings(r) for h, _, r in runs if "\n**gate: failed**" in h]
        prs[kind] += 1
        prs["all"] += 1
        if failed:
            rejected[kind] += 1
            rejected["all"] += 1
            none += not all(failed)
            for i in set().union(*failed):
                by_id[i] = by_id.get(i, 0) + 1
    natural = lambda kv: (-kv[1], re.sub(r"[0-9]+", lambda m: m.group().zfill(3), kv[0]))  # most first, QA-6 before QA-10
    return {"prs": prs, "rejected": rejected, "none": none,
            "requirements": [{"id": i, "prs": n} for i, n in sorted(by_id.items(), key=natural)]}


def stats(generators, gate):
    """CAT-33: pulls per generator, versions per month of their publication and how many of them are yanked, gate results."""
    months = {}
    for g in generators:
        for r in g["versions"]:
            if isinstance(r.get("published"), str) and STAMP.match(r["published"]):
                m = months.setdefault(r["published"][:7], {"month": r["published"][:7], "published": 0, "yanked": 0})
                m["published"] += 1
                m["yanked"] += bool(r.get("yanked"))
    pulls = [{"name": g["name"], "pulls": g["pulls"]} for g in generators]
    return {"pulls": sorted(pulls, key=lambda p: (p["pulls"] is None, -(p["pulls"] or 0), p["name"])),
            "pulls_total": sum(p["pulls"] or 0 for p in pulls),
            "months": [months[m] for m in sorted(months, reverse=True)], "gate": gate}


def load_previous(path):
    """{(name, latest digest): {"readme": README, "changelog": CHANGELOG sections, "sources": group software}} from the last build's catalog.json."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, TypeError, ValueError):
        return {}
    return {(g["name"], g["latest"]["digest"]): {
                "readme": g["readme"],
                "changelog": {v: t for v, t in g["changelog"].items() if isinstance(t, str)} if isinstance(g.get("changelog"), dict) else None,
                "sources": {k: s if isinstance(s, str) else None for k, s in g["sources"].items()} if isinstance(g.get("sources"), dict) else None}
            for g in data.get("generators", [])
            if isinstance(g, dict) and isinstance(g.get("latest"), dict) and isinstance(g.get("readme"), str)
            and len(g["readme"].encode()) <= README_MAX}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", required=True)
    p.add_argument("--owner", required=True)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--artifacts")
    p.add_argument("--sboms")
    p.add_argument("--rekor")
    p.add_argument("--discussions")
    p.add_argument("--pages")
    p.add_argument("--previous")
    p.add_argument("--diffs")
    p.add_argument("--wanted")
    p.add_argument("--gate")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    with open(a.index, encoding="utf-8") as f:
        index = json.load(f)
    result = view(index, a.owner, (lambda _: None) if a.offline else api, a.artifacts, a.sboms, load_rekor(a.rekor),
                  load_discussions(a.discussions, a.owner), a.pages, load_previous(a.previous), a.diffs)
    result["wanted"] = load_wanted(a.wanted)
    result["stats"] = stats(result["generators"], load_gate(a.gate))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
