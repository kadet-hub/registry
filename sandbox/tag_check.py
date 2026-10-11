"""Check the manifest's tags against the manifest and the compiled output (QA-6).

Usage: tag_check.py --manifest FILE --out DIR

kubernetes, helm and terraform need evidence; every other tag is printed
as a review line. Evidence for a tag the manifest lacks is a review line.
Prints findings and review lines; exits 1 on any finding.
"""

import argparse
import json
import os
import sys

import yaml


def files(out):
    for d, _, names in os.walk(out):
        for n in sorted(names):
            path = os.path.join(d, n)
            if os.path.isfile(path) and not os.path.islink(path):
                yield os.path.relpath(path, out)


def k8s_documents(path):
    """Documents with apiVersion and kind in a YAML or JSON file."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        docs = [json.loads(text)] if path.endswith(".json") else list(yaml.safe_load_all(text))
    except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError):
        return False
    for doc in docs:
        items = doc if isinstance(doc, list) else [doc]
        if any(isinstance(i, dict) and isinstance(i.get("apiVersion"), str) and isinstance(i.get("kind"), str) for i in items):
            return True
    return False


def evidence(manifest, out):
    found = {}
    for rel in files(out):
        if "terraform" not in found and rel.endswith((".tf.json", ".tf")):
            found["terraform"] = rel
        elif "kubernetes" not in found and rel.endswith((".yml", ".yaml", ".json")) and k8s_documents(os.path.join(out, rel)):
            found["kubernetes"] = rel
    if manifest.get("charts"):
        found["helm"] = "charts in the manifest"
    elif "helm template" in manifest.get("binaries", []):
        found["helm"] = "helm template in binaries"
    return found


MISSING = {
    "kubernetes": "no Kubernetes manifest (apiVersion and kind) in the compiled output",
    "terraform": "no *.tf.json or *.tf file in the compiled output",
    "helm": "no chart in the manifest and no helm template in binaries",
}


def check(manifest, out):
    tags = manifest.get("tags", [])
    found = evidence(manifest, out)
    findings, lines = [], []
    for tag in tags:
        if tag in MISSING:
            if tag in found:
                lines.append(f"QA-6: tag {tag}: {found[tag]}")
            else:
                findings.append(f"QA-6: tag {tag}: {MISSING[tag]}")
        else:
            lines.append(f"review: tag {tag}: check it against /tags/#{tag}")
    for tag in sorted(set(found) - set(tags)):
        lines.append(f"review: tag {tag} is not set, but the generator shows it: {found[tag]}")
    return findings, lines


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    with open(a.manifest, encoding="utf-8") as f:
        manifest = yaml.safe_load(f) or {}
    findings, lines = check(manifest, a.out)
    if findings or lines:
        print("\n".join(findings + lines))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
