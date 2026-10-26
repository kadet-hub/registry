"""Check a consumer's dependencies against its policy and the index (CON-1, CON-2, CON-4, CON-5).

Usage: plan.py --inventory FILE --policy FILE --owner OWNER [--fetch] [--index FILE] --out FILE

Runs in the sandbox image without network. FILE for --inventory is the
output of `kapitan inventory`, of the fetch inventory with --fetch. Writes
the plan: every dependency to fetch, normalized, and the binaries the
fetched generators declare. Prints findings and exits 1 on any; without
--index the marketplace checks wait for the second call.
"""

import argparse
import json
import os
import re
import sys
from urllib.parse import urlsplit

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gate"))  # python -I does not add the script dir
from check_entry import schema_errors

RELPATH = re.compile(r"^[A-Za-z0-9._/-]+$")
OCI = re.compile(r"^(?P<host>[a-z0-9.-]+(?::\d+)?)/(?P<repo>[a-z0-9._/-]+)"
                 r"(?::(?P<tag>[A-Za-z0-9_][A-Za-z0-9._-]{0,127}))?@(?P<digest>sha256:[0-9a-f]{64})$")
NAME = re.compile(r"^[a-z][a-z0-9-]{1,38}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
VERSION = re.compile(r"^v?\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")


def relpath_ok(path):
    parts = path.split("/")
    return bool(RELPATH.match(path)) and not path.startswith("/") and not {"..", ".", ".git", ""} & set(parts)


def https_host(url):
    try:
        u = urlsplit(url)
    except ValueError:
        return None
    if u.scheme != "https" or not u.hostname or "@" in u.netloc:
        return None
    return u.netloc.lower()


def target_dependencies(data):
    """parameters.kapitan.dependencies of a target; None if a level has the wrong type."""
    for key in ("parameters", "kapitan", "dependencies"):
        if not isinstance(data or {}, dict):
            return None
        data = (data or {}).get(key)
    deps = data or []
    return deps if isinstance(deps, list) and all(isinstance(d, dict) for d in deps) else None


def dependencies(inventory, policy, owner, fetch=False):
    """Every dependency of every target, checked and normalized; with fetch, those of the fetch inventory (CON-4)."""
    hosts = policy.get("hosts", {})
    rule = "CON-4" if fetch else "CON-1"
    findings, seen = [], {}
    if not isinstance(inventory or {}, dict) or not all(isinstance(t, str) for t in inventory or {}):
        return [], [f"{rule}: the inventory is not a mapping of target names to targets"]
    for target, data in sorted((inventory or {}).items()):
        deps = target_dependencies(data)
        if deps is None:
            findings.append(f"{rule}: {target}: parameters.kapitan.dependencies is not a list of mappings")
            continue
        if fetch:
            # Kapitan writes compile, labels, vars.target and others into every target, empty when unset.
            kapitan = ((data or {}).get("parameters") or {}).get("kapitan") or {}
            extra = sorted(str(k) for k, v in kapitan.items()
                           if k != "dependencies" and v and not (isinstance(v, dict) and not any(v.values())))
            if extra:
                findings.append(f"CON-4: {target}: parameters.kapitan sets {', '.join(extra)}, "
                                "a fetch target sets only dependencies")
        for d in deps:
            kind, source, out = d.get("type"), str(d.get("source", "")), str(d.get("output_path", ""))
            where = f"{target}: {kind} {source}"
            dep = {"type": kind, "source": source, "output_path": out}
            errors = []
            if not relpath_ok(out):
                errors.append(f"output_path {out} must be a relative path inside the project")
            if kind == "oci":
                m = OCI.match(source)
                if not m:
                    errors.append("source must be <host>/<repository>[:<tag>]@sha256:<digest>")
                else:
                    host, repo = m.group("host"), m.group("repo")
                    name = repo[len(owner) + 1:] if host == "ghcr.io" and repo.startswith(owner + "/") else None
                    recipe = name[len("recipes/"):] if name and name.startswith("recipes/") else None
                    dep.update(host=host, repo=repo, tag=m.group("tag"), digest=m.group("digest"),
                               marketplace=name if name is not None and NAME.match(name) else None,
                               recipe=recipe if recipe is not None and NAME.match(recipe) else None)
                    if recipe is not None and not fetch:
                        errors.append("recipes belong in the fetch inventory (CON-4)")
                    elif recipe is not None and dep["recipe"] is None:
                        errors.append(f"{repo} is not a marketplace recipe")
                    elif recipe is None and name is not None and dep["marketplace"] is None:
                        errors.append(f"{repo} is not a marketplace generator")
                if d.get("insecure") or d.get("tls_verify") is not True or d.get("subpath") or d.get("media_type"):
                    errors.append("insecure, tls_verify, subpath and media_type are not supported")
            elif kind == "helm":
                host = https_host(source)
                if not host:
                    errors.append("source must be an https URL")
                if not VERSION.match(str(d.get("version") or "")):
                    errors.append("version must be an exact chart version")
                if d.get("helm_path"):
                    errors.append("helm_path is not supported")
                dep.update(host=host, chart_name=str(d.get("chart_name", "")), version=d.get("version"), sha256=None)
            elif kind == "git":
                host = https_host(source)
                if not host:
                    errors.append("source must be an https URL")
                if not SHA.match(str(d.get("ref") or "")):
                    errors.append("ref must be a full commit SHA")
                if d.get("submodules"):
                    errors.append("submodules are not supported")
                if d.get("subdir") and not relpath_ok(str(d["subdir"])):
                    errors.append("subdir must be a relative path")
                dep.update(host=host, ref=d.get("ref"), subdir=d.get("subdir"))
            elif kind == "https":
                host = https_host(source)
                if not host:
                    errors.append("source must be an https URL")
                dep.update(host=host, unpack=bool(d.get("unpack")))
            else:
                errors.append(f"type {kind} is not allowed")
            if dep.get("host") and dep["host"] not in hosts.get(kind, []):
                errors.append(f"host {dep['host']} is not allowed for {kind}")
            if fetch and not (dep.get("recipe") and out == f"inventory/classes/recipes/{dep['recipe']}"):
                errors.append(f"the fetch inventory holds only oci sources ghcr.io/{owner}/recipes/<name>"
                              "[:<version>]@sha256:<digest> with output_path inventory/classes/recipes/<name>")
            if errors:
                findings += [f"{rule}: {where}: {e}" for e in errors]
                continue
            if out in seen and seen[out] != dep:
                findings.append(f"{rule}: {where}: output_path {out} is used by another dependency")
            seen.setdefault(out, dep)
    return list(seen.values()), findings


def check_index(index, policy, deps):
    """CON-2 against an attested index, CON-5 and the included recipes of CON-4 for recipes.
    Returns binaries, findings, notices."""
    findings, notices, binaries, charts, includes = [], [], set(), {}, {}
    serial = index.get("serial", 0)
    if serial < policy["index_serial"]:
        findings.append(f"CON-2: index serial {serial} is lower than index_serial {policy['index_serial']}")
    elif serial > policy["index_serial"]:
        notices.append(f"index serial {serial} is newer than index_serial {policy['index_serial']}")
    for dep in deps:
        name = dep.get("marketplace") or dep.get("recipe")
        if not name:
            continue
        rule, kind, section = ("CON-5", "recipe ", index.get("recipes")) if dep.get("recipe") else \
            ("CON-2", "", index.get("generators"))
        records = [(v, r) for v, r in (section or {}).get(name, {}).items() if r.get("digest") == dep["digest"]]
        if not records:
            findings.append(f"{rule}: {dep['source']}: the index does not list this digest for {kind}{name}")
            continue
        version, record = records[0]
        if dep["tag"] and dep["tag"] != version:
            findings.append(f"{rule}: {dep['source']}: tag {dep['tag']} is not {version}, "
                            "the version the index lists for this digest")
            continue
        if record.get("yanked"):
            findings.append(f"{rule}: {kind}{name} {version} is yanked: {record['yanked']}")
            continue
        if dep.get("recipe"):  # a recipe adds no binaries (CON-5)
            for i in record.get("includes") or []:
                includes.setdefault(i["name"], set()).add((f"recipe {name} {version}", i["version"], i["digest"]))
            continue
        binaries.update(record.get("binaries", []))
        for c in record.get("charts", []):
            charts[(c["repo"].rstrip("/"), c["name"], c["version"])] = c["sha256"]
    # CON-4: the fetch inventory pins each included recipe at the digest every parent's record lists.
    pinned = {d["recipe"]: d["digest"] for d in deps if d.get("recipe")}
    for name, wanted in sorted(includes.items()):
        parents = " and ".join(f"{p} includes {name} {v} at {d}" for p, v, d in sorted(wanted))
        if len({d for _, _, d in wanted}) > 1:
            findings.append(f"CON-4: {parents}, the fetch inventory can pin only one")
        elif pinned.get(name) != next(iter(wanted))[2]:
            have = f"pins {name} at {pinned[name]}" if name in pinned else f"does not pin {name}"
            findings.append(f"CON-4: {parents}, the fetch inventory {have}")
    for dep in deps:
        if dep["type"] == "helm":
            dep["sha256"] = charts.get((dep["source"].rstrip("/"), dep["chart_name"], dep["version"]))
    return sorted(binaries), findings, notices


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inventory", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--owner", required=True)
    p.add_argument("--fetch", action="store_true")
    p.add_argument("--index")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    with open(a.policy, encoding="utf-8") as f:
        policy = yaml.safe_load(f)
    findings = [f"policy: {e}" for e in schema_errors(policy, os.path.join(HERE, "..", "policy", "consumer.schema.json"))]
    if findings:
        print("\n".join(findings))
        return 1
    with open(a.inventory, encoding="utf-8") as f:
        deps, findings = dependencies(yaml.safe_load(f), policy, a.owner, a.fetch)
    binaries = []
    if a.index:
        with open(a.index, encoding="utf-8") as f:
            binaries, more, notices = check_index(json.load(f), policy, deps)
        findings += more
        for n in notices:
            print(f"::notice::{n}")
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"deps": deps, "binaries": binaries, "policy_binaries": policy.get("binaries", []),
                   "inventory_backend": policy.get("inventory_backend"),
                   "output_capabilities": policy.get("output_capabilities", {})}, f)
    if findings:
        print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
