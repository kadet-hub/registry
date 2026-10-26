"""GI-14: check_entry.quality on a fuzzed __init__.py of a generator tree (QA-1a)."""

import os
import sys
import tempfile

import atheris

ROOT = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "gate"))
with atheris.instrument_imports():
    import check_entry

POLICY = os.path.join(ROOT, "policy")
TREE = tempfile.mkdtemp()
for name, text in (("README.md", "```yaml\nparameters: {}\n```\n"), ("CHANGELOG.md", "## 1.0.0\n"), ("LICENSE", "Apache License\nVersion 2.0, January 2004\n")):
    with open(os.path.join(TREE, name), "w", encoding="utf-8") as f:
        f.write(text)
INIT = os.path.join(TREE, "__init__.py")


def TestOneInput(data):
    with open(INIT, "wb") as f:
        f.write(data)
    check_entry.quality(TREE, {"license": "Apache-2.0"}, {"tag": "demo-v1.0.0"}, None, POLICY)


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
