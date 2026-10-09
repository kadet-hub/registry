import json
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace

import check_entry

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
POLICY = os.path.join(ROOT, "policy")
SHA = "a" * 40
OWNER, STRANGER, MAINTAINER = 1001, 2002, 3042152

ENTRY = """source:
  repo: https://github.com/example/demo.git
  path: generators/demo
  tag: {tag}
  sha: {sha}
owners: [{owners}]
"""
MANIFEST = """name: {name}
description: Demo generator
license: Apache-2.0
owners: [{owners}]
kapitan: "{kapitan}"
binaries: [{binaries}]
fixtures: tests/consumer
"""


class Case:
    def __init__(self, author=OWNER, base_entries=None, same_repo=False, author_id_bot=False):
        self.dir = tempfile.mkdtemp()
        self.base = os.path.join(self.dir, "base")
        os.makedirs(os.path.join(self.base, "generators"))
        shutil.copytree(POLICY, os.path.join(self.base, "policy"))
        for name, text in (base_entries or {}).items():
            self.write(f"base/generators/{name}.yaml", text)
        head = {"full_name": "kadet-hub/registry" if same_repo else "someone/registry"}
        self.write("event.json", json.dumps({"pull_request": {
            "user": {"id": author}, "head": {"repo": head}, "base": {"repo": {"full_name": "kadet-hub/registry"}}}}))

    def p(self, rel):
        return os.path.join(self.dir, rel)

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.p(rel)) or self.dir, exist_ok=True)
        with open(self.p(rel), "w", encoding="utf-8") as f:
            f.write(text)

    def files(self, *files):
        self.write("files.jsonl", "".join(json.dumps(f) + "\n" for f in files))
        a = SimpleNamespace(event=self.p("event.json"), files=self.p("files.jsonl"), policy=POLICY, out=self.p("path"))
        findings = check_entry.step_files(a)
        with open(self.p("path"), encoding="utf-8") as f:
            return findings, f.read()

    def entry(self, path, text=None, reserved=None):
        self.write("path", path)
        if text is not None:
            self.write("head.yaml", text)
        if reserved is not None:
            self.write("reserved.txt", reserved)
        a = SimpleNamespace(event=self.p("event.json"), path_file=self.p("path"), head=self.p("head.yaml"),
                            base=self.base, reserved=self.p("reserved.txt"), policy=POLICY, out=self.p("entry.json"))
        return check_entry.step_entry(a)

    def manifest(self, text):
        self.write("manifest.yaml", text)
        a = SimpleNamespace(event=self.p("event.json"), entry=self.p("entry.json"), manifest=self.p("manifest.yaml"),
                            policy=POLICY)
        return check_entry.step_manifest(a)


def entry(tag="v1.0.0", owners=OWNER, sha=SHA):
    return ENTRY.format(tag=tag, sha=sha, owners=owners)


def manifest(name="demo", owners=OWNER, kapitan=">=0.36.3,<0.37", binaries=""):
    return MANIFEST.format(name=name, owners=owners, kapitan=kapitan, binaries=binaries)


def has(findings, prefix):
    return any(f.startswith(prefix) for f in findings)


class Files(unittest.TestCase):
    def test_single_entry(self):
        self.assertEqual(Case().files({"filename": "generators/demo.yaml", "status": "added"}), ([], "generators/demo.yaml"))

    def test_non_maintainer_extra_file_fails(self):
        f, _ = Case().files({"filename": "generators/demo.yaml", "status": "added"}, {"filename": "policy/imports.txt", "status": "modified"})
        self.assertTrue(has(f, "GI-2"))

    def test_non_maintainer_policy_only_fails(self):
        f, _ = Case().files({"filename": ".github/workflows/gate.yml", "status": "modified"})
        self.assertTrue(has(f, "GI-2"))

    def test_non_maintainer_removal_fails(self):
        f, _ = Case().files({"filename": "generators/demo.yaml", "status": "removed"})
        self.assertTrue(has(f, "GI-2"))

    def test_maintainer_without_entry_passes(self):
        self.assertEqual(Case(author=MAINTAINER).files({"filename": "policy/imports.txt", "status": "modified"}), ([], ""))

    def test_bad_path_fails(self):
        f, _ = Case().files({"filename": "generators/$(id).yaml", "status": "added"})
        self.assertTrue(has(f, "REG-2"))


class Entry(unittest.TestCase):
    def test_new_entry_passes(self):
        self.assertEqual(Case().entry("generators/demo.yaml", entry()), [])

    def test_schema_rejects_injection_and_bad_sha(self):
        self.assertTrue(has(Case().entry("generators/demo.yaml", entry(tag="v1.0.0-$(id)")), "QA-5"))
        self.assertTrue(has(Case().entry("generators/demo.yaml", entry(sha="main")), "QA-5"))
        self.assertTrue(has(Case().entry("generators/demo.yaml", entry().replace("example/demo.git", "example/demo")), "QA-5"))

    def test_layout_order(self):
        text = entry().replace("  path: generators/demo\n", "").replace("  sha:", "  path: generators/demo\n  sha:")
        self.assertTrue(has(Case().entry("generators/demo.yaml", text), "REG-7"))

    def test_reserved_and_similar_names(self):
        self.assertTrue(has(Case().entry("generators/kapitan.yaml", entry()), "REG-2"))
        self.assertTrue(has(Case(base_entries={"kube-rnetes": entry()}).entry("generators/kubernetes.yaml", entry()), "REG-3"))

    def test_bump(self):
        c = Case(base_entries={"demo": entry()})
        self.assertEqual(c.entry("generators/demo.yaml", entry(tag="v1.1.0")), [])
        self.assertTrue(has(c.entry("generators/demo.yaml", entry(tag="v1.0.0")), "REG-6"))
        self.assertTrue(has(c.entry("generators/demo.yaml", entry(tag="other-v2.0.0")), "REG-6"))

    def test_bump_by_stranger_and_repo_change(self):
        self.assertTrue(has(Case(author=STRANGER, base_entries={"demo": entry()}).entry("generators/demo.yaml", entry(tag="v1.1.0")), "REG-5"))
        moved = entry(tag="v1.1.0").replace("example/demo.git", "attacker/demo.git")
        self.assertTrue(has(Case(base_entries={"demo": entry()}).entry("generators/demo.yaml", moved), "REG-8"))
        self.assertEqual(Case(author=MAINTAINER, base_entries={"demo": entry()}).entry("generators/demo.yaml", moved), [])

    def test_renovate_bump_needs_same_repo_branch(self):
        bump = entry(tag="v1.1.0")
        self.assertEqual(Case(author=check_entry.RENOVATE_BOT, same_repo=True, base_entries={"demo": entry()}).entry("generators/demo.yaml", bump), [])
        self.assertTrue(has(Case(author=check_entry.RENOVATE_BOT, base_entries={"demo": entry()}).entry("generators/demo.yaml", bump), "REG-5"))

    def test_removal_reserves_name(self):
        c = Case(author=MAINTAINER, base_entries={"demo": entry()})
        self.assertTrue(has(c.entry("removed:generators/demo.yaml", reserved="kapitan\n"), "REG-9"))
        self.assertEqual(c.entry("removed:generators/demo.yaml", reserved="kapitan\ndemo\n"), [])


class Manifest(unittest.TestCase):
    def setUp(self):
        self.c = Case()
        self.assertEqual(self.c.entry("generators/demo.yaml", entry()), [])

    def test_valid(self):
        self.assertEqual(self.c.manifest(manifest(binaries='"helm template"')), [])

    def test_failures(self):
        self.assertTrue(has(self.c.manifest(manifest(name="other")), "REG-2"))
        self.assertTrue(has(self.c.manifest(manifest(owners=STRANGER)), "REG-4"))
        self.assertTrue(has(self.c.manifest(manifest(kapitan=">=0.37")), "CMP-3"))
        self.assertTrue(has(self.c.manifest(manifest(binaries='"curl get"')), "SEC-7"))
        self.assertTrue(has(self.c.manifest(manifest() + "dependencies: [requests]\n"), "QA-5"))
        self.assertTrue(has(self.c.manifest(manifest().replace("tests/consumer", "../outside")), "QA-5"))

    def test_tags_come_from_the_list(self):
        self.assertEqual(self.c.manifest(manifest() + "tags: [helm, kubernetes]\n"), [])
        self.assertTrue(has(self.c.manifest(manifest() + "tags: [crypto]\n"), "QA-5"))


if __name__ == "__main__":
    unittest.main()
