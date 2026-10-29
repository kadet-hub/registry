"""Scan the images of scan/rescan's list with Trivy for the catalog's security report (SEC-19, CAT-39). Standard library only.

Usage: image_report.py IMAGES OUT

IMAGES has one line per scanned version, "<page>\t<version>\t<references
separated by spaces>", the page being generators/<name> or recipes/<name>.
Downloads the vulnerability database once, scans each reference once and
writes OUT: {"scanned", "trivy", "db", "pages": {page: {"version", "images"}},
"images": {reference: {"vulnerabilities": [{"id", "severity", "package",
"installed", "fixed"}]} or {"error"}}}. Needs trivy on PATH.
"""

import datetime
import json
import subprocess
import sys


def trivy(*args):
    return subprocess.run(["trivy", *args], capture_output=True, text=True)


def scan(ref):
    """The vulnerabilities Trivy lists for ref, one per package and advisory in each result, or the error."""
    run = trivy("image", "--quiet", "--skip-db-update", "--scanners", "vuln", "--image-src", "remote",
                "--timeout", "15m", "--format", "json", ref)
    try:
        report = json.loads(run.stdout) if run.returncode == 0 else None
    except ValueError:
        report = None
    if report is None:
        return {"error": ((run.stderr.strip().splitlines() or [f"trivy exited {run.returncode}"])[-1])[-300:]}
    return {"vulnerabilities": [{"id": v.get("VulnerabilityID", ""), "severity": v.get("Severity", "UNKNOWN"),
                                 "package": v.get("PkgName", ""), "installed": v.get("InstalledVersion", ""),
                                 "fixed": v.get("FixedVersion", "")}
                                for r in report.get("Results") or [] for v in r.get("Vulnerabilities") or []]}


def main():
    pages = {}
    with open(sys.argv[1], encoding="utf-8") as f:
        for line in f:
            page, version, refs = line.rstrip("\n").split("\t")
            pages[page] = {"version": version, "images": refs.split()}
    scanned = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    db = trivy("image", "--quiet", "--download-db-only")
    if db.returncode:
        sys.exit(f"trivy: vulnerability database not downloaded: {db.stderr.strip()}")
    meta = json.loads(trivy("version", "--format", "json").stdout)
    images = {ref: scan(ref) for ref in sorted({r for p in pages.values() for r in p["images"]})}
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump({"scanned": scanned, "trivy": meta["Version"], "db": meta["VulnerabilityDB"]["UpdatedAt"][:19] + "Z",
                   "pages": pages, "images": images}, f, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
