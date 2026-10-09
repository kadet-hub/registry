"""Check a consumer's dependencies against its policy and the index (CON-1, CON-2).

Usage: plan.py --inventory FILE --policy FILE --owner OWNER [--index FILE] --out FILE

Runs in the sandbox image without network. FILE for --inventory is the
output of `kapitan inventory`. Writes the plan: every dependency to fetch,
normalized, and the binaries the fetched generators declare. Prints
findings and exits 1 on any; without --index the marketplace checks wait for
the second call.
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
OCI = re.compile(r"^(?P<host>[a-z0-9.-]+(?::\d+)?)/(?P<repo>[a-z0-9._/-]+)@(?P<digest>sha256:[0-9a-f]{64})$")
NAME = re.compile(r"^[a-z][a-z0-9-]{1,38}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
VERSION = re.compile(r"^v?\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?$")


def relpath_ok(path):
    parts = path.split("/")
    return bool(RELPATH.match(path)) and not path.startswith("/") and not {"..", ".", ".git", ""} & set(parts)


def https_host(url):
    u = urlsplit(url)
    if u.scheme != "https" or not u.hostname or "@" in u.netloc:
        return None
    return u.netloc.lower()


def dependencies(inventory, policy, owner):
    """Every dependency of every target, checked and normalized."""
    hosts = policy.get("hosts", {})
    findings, seen = [], {}
    for target, data in sorted((inventory or {}).items()):
        deps = (((data or {}).get("parameters") or {}).get("kapitan") or {}).get("dependencies") or []
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
                    errors.append("source must be <host>/<repository>@sha256:<digest>")
                else:
                    host, repo = m.group("host"), m.group("repo")
                    name = repo[len(owner) + 1:] if host == "ghcr.io" and repo.startswith(owner + "/") else None
                    dep.update(host=host, repo=repo, digest=m.group("digest"),
                               marketplace=name if name is not None and NAME.match(name) else None)
                    if name is not None and dep["marketplace"] is None:
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
            if errors:
                findings += [f"CON-1: {where}: {e}" for e in errors]
                continue
            if out in seen and seen[out] != dep:
                findings.append(f"CON-1: {where}: output_path {out} is used by another dependency")
            seen.setdefault(out, dep)
    return list(seen.values()), findings


def check_index(index, policy, deps):
    """CON-2 against an attested index. Returns binaries, findings, notices."""
    findings, notices, binaries, charts = [], [], set(), {}
    serial = index.get("serial", 0)
    if serial < policy["index_serial"]:
        findings.append(f"CON-2: index serial {serial} is lower than index_serial {policy['index_serial']}")
    elif serial > policy["index_serial"]:
        notices.append(f"index serial {serial} is newer than index_serial {policy['index_serial']}")
    generators = index.get("generators", {})
    for dep in deps:
        name = dep.get("marketplace")
        if not name:
            continue
        records = [(v, r) for v, r in generators.get(name, {}).items() if r.get("digest") == dep["digest"]]
        if not records:
            findings.append(f"CON-2: {dep['source']}: the index does not list this digest for {name}")
            continue
        version, record = records[0]
        if record.get("yanked"):
            findings.append(f"CON-2: {name} {version} is yanked: {record['yanked']}")
            continue
        binaries.update(record.get("binaries", []))
        for c in record.get("charts", []):
            charts[(c["repo"].rstrip("/"), c["name"], c["version"])] = c["sha256"]
    for dep in deps:
        if dep["type"] == "helm":
            dep["sha256"] = charts.get((dep["source"].rstrip("/"), dep["chart_name"], dep["version"]))
    return sorted(binaries), findings, notices


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inventory", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--owner", required=True)
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
        deps, findings = dependencies(yaml.safe_load(f), policy, a.owner)
    binaries = []
    if a.index:
        with open(a.index, encoding="utf-8") as f:
            binaries, more, notices = check_index(json.load(f), policy, deps)
        findings += more
        for n in notices:
            print(f"::notice::{n}")
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"deps": deps, "binaries": binaries, "policy_binaries": policy.get("binaries", []),
                   "inventory_backend": policy.get("inventory_backend")}, f)
    if findings:
        print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
