"""GI-14: check_entry.py's manifest step and schema_diff.py on a fuzzed kapitan-generator.yaml.

The last input byte picks the author and whether the entry is new.
"""

import json
import os
import sys
import tempfile
from types import SimpleNamespace

import atheris

ROOT = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "gate"))
with atheris.instrument_imports():
    import check_entry
    import schema_diff

POLICY = os.path.join(ROOT, "policy")
WORK = tempfile.mkdtemp()
TREE = {
    "README.md": "# demo\n\n```yaml\nparameters:\n  demo: {}\n```\n",
    "CHANGELOG.md": "# Changelog\n\n## 1.0.0\n",
    "LICENSE": "Apache License\nVersion 2.0, January 2004\n",
    "schemas/sources.yaml": "core:\n  software: kubernetes\n  version: 1.31.0\n",
}


def write(rel, text):
    path = os.path.join(WORK, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


for rel, text in TREE.items():
    write(f"tree/{rel}", text)
for i, author in enumerate((1001, 2002)):
    repo = {"full_name": "kadet-hub/registry"}
    write(f"event{i}.json", json.dumps({"pull_request": {"user": {"id": author}, "head": {"repo": repo}, "base": {"repo": repo}}}))
for new in (False, True):
    write(f"entry{int(new)}.json", json.dumps({"name": "demo", "new": new, "tag": "demo-v1.0.0", "owners": [1001]}))
MANIFEST = os.path.join(WORK, "tree", "kapitan-generator.yaml")


def TestOneInput(data):
    if not data:
        return
    with open(MANIFEST, "wb") as f:
        f.write(data)
    mode = data[-1]
    check_entry.step_manifest(SimpleNamespace(
        event=os.path.join(WORK, f"event{mode & 1}.json"), entry=os.path.join(WORK, f"entry{mode >> 1 & 1}.json"),
        manifest=MANIFEST, policy=POLICY, root_license=None))
    schema_diff.sources(os.path.join(WORK, "tree"))


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
