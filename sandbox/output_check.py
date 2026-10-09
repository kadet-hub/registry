"""Judge compile output against the SEC-12 rules in policy/output/.

Usage: output_check.py --out DIR --policy DIR [--allow CAPABILITY]... [--unparsed GLOB]...

Runs conftest per parser over the regular files below --out. A match of a
capability not passed with --allow, a file without a parser that matches no
--unparsed glob, a non-regular file and a conftest error are findings.
Prints every finding and every allowed match; exits 1 on any finding.
"""

import argparse
import fnmatch
import json
import os
import stat
import subprocess
import sys

# parser, rego namespace
GROUPS = {
    "yaml": ("yaml", "output.k8s"),
    "json": ("json", "output.k8s"),
    "tfjson": ("json", "output.terraform"),
    "hcl2": ("hcl2", "output.terraform"),
    "dockerfile": ("dockerfile", "output.dockerfile"),
}


def group(rel):
    name = os.path.basename(rel)
    if name == "Dockerfile":
        return "dockerfile"
    if name.endswith(".tf.json"):
        return "tfjson"
    if name.endswith(".tf"):
        return "hcl2"
    if name.endswith(".json"):
        return "json"
    if name.endswith((".yml", ".yaml")):
        return "yaml"
    return None


def conftest(parser, namespace, policy, paths):
    cmd = ["conftest", "test", "--no-fail", "--no-color", "--output", "json",
           "--policy", policy, "--namespace", namespace, "--parser", parser, "--", *paths]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"conftest --parser {parser}: exit {r.returncode}: {(r.stderr or r.stdout).strip()[:500]}")
    return json.loads(r.stdout)


def check(out, policy, allow, unparsed):
    findings, notes, files = [], [], {}
    for dirpath, dirnames, filenames in os.walk(out):
        for name in sorted(dirnames + filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, out)
            mode = os.lstat(path).st_mode
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                findings.append(f"SEC-12: {rel}: not a regular file")
                continue
            g = group(rel)
            if g:
                files.setdefault(g, []).append(path)
                continue
            glob = next((p for p in unparsed if fnmatch.fnmatchcase(rel, p)), None)
            if glob:
                notes.append(f"SEC-12: unparsed output {rel} ({glob})")
            else:
                findings.append(f"SEC-12: {rel}: no parser; declare it in unparsed_outputs")
    for g, paths in sorted(files.items()):
        parser, namespace = GROUPS[g]
        for result in conftest(parser, namespace, policy, paths):
            rel = os.path.relpath(result["filename"], out)
            for failure in result.get("failures") or []:
                capability, _, detail = failure["msg"].partition(": ")
                line = f"{capability}: {rel}: {detail}"
                if capability in allow:
                    notes.append(f"SEC-12: declared {line}")
                else:
                    findings.append(f"SEC-12: {line}")
    return findings, notes


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--allow", action="append", default=[])
    p.add_argument("--unparsed", action="append", default=[])
    a = p.parse_args()
    try:
        findings, notes = check(a.out, a.policy, set(a.allow), a.unparsed)
    except (RuntimeError, OSError, ValueError, KeyError) as e:
        print(f"SEC-12: {e}")
        return 1
    for line in notes + findings:
        print(line)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
