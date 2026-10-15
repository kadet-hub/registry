"""GI-14: check_entry.py's entry step on a fuzzed generators/<name>.yaml.

The last input byte picks the author and whether main already holds the
entry, so the bump rules run too.
"""

import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

import atheris

ROOT = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "gate"))
with atheris.instrument_imports():
    import check_entry

POLICY = os.path.join(ROOT, "policy")
OLD = "source:\n  repo: https://github.com/example/demo.git\n  path: demo\n  tag: demo-v1.0.0\n  sha: " + "a" * 40 + "\nowners: [1001]\n"
AUTHORS = [1001, 2002, int(check_entry.lines(os.path.join(POLICY, "maintainers.txt"))[0]), check_entry.RENOVATE_BOT]
WORK = tempfile.mkdtemp()


def write(rel, text):
    path = os.path.join(WORK, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


for base in ("new", "old"):
    os.makedirs(os.path.join(WORK, base, "generators"))
    shutil.copytree(POLICY, os.path.join(WORK, base, "policy"))
write("old/generators/demo.yaml", OLD)
write("new/generators/demo-x.yaml", OLD)
for i, author in enumerate(AUTHORS):
    repo = {"full_name": "kadet-hub/registry"}
    write(f"event{i}.json", json.dumps({"pull_request": {"user": {"id": author}, "head": {"repo": repo}, "base": {"repo": repo}}}))
PATH = write("path", "generators/demo.yaml")
HEAD = os.path.join(WORK, "head.yaml")


def TestOneInput(data):
    if not data:
        return
    with open(HEAD, "wb") as f:
        f.write(data)
    mode = data[-1]
    check_entry.step_entry(SimpleNamespace(
        event=os.path.join(WORK, f"event{mode % 4}.json"), path_file=PATH, head=HEAD,
        base=os.path.join(WORK, ("new", "old")[mode >> 2 & 1]), reserved=os.path.join(WORK, "reserved.txt"),
        policy=POLICY, out=os.path.join(WORK, "entry.json")))


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
