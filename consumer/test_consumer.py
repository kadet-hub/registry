import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan import check_index, dependencies

DIGEST = "sha256:" + "a" * 64
POLICY = {"index_serial": 5, "hosts": {"oci": ["ghcr.io"], "helm": ["charts.example.org"], "git": ["github.com"]}}


def inventory(*deps):
    return {"t1": {"parameters": {"kapitan": {"dependencies": list(deps)}}}}


def oci(source, **kw):
    return {"type": "oci", "source": source, "output_path": "lib/gen", "insecure": False, "tls_verify": True,
            "subpath": None, "media_type": None, **kw}


def helm(**kw):
    return {"type": "helm", "source": "https://charts.example.org", "chart_name": "demo", "version": "1.2.3",
            "output_path": "charts/demo", "helm_path": None, **kw}


def index(serial=5, yanked=None):
    record = {"digest": DIGEST, "yanked": yanked, "binaries": ["helm template"],
              "charts": [{"repo": "https://charts.example.org/", "name": "demo", "version": "1.2.3", "sha256": "b" * 64}]}
    return {"serial": serial, "generators": {"gen": {"1.0.0": record}}}


class Dependencies(unittest.TestCase):
    def check(self, *deps):
        return dependencies(inventory(*deps), POLICY, "kadet-hub")

    def test_marketplace_artifact(self):
        deps, findings = self.check(oci(f"ghcr.io/kadet-hub/gen@{DIGEST}"))
        self.assertEqual(findings, [])
        self.assertEqual(deps[0]["marketplace"], "gen")

    def test_rejected_dependencies(self):
        cases = [
            (oci("ghcr.io/kadet-hub/gen:1.0.0"), "source must be"),
            (oci(f"ghcr.io/kadet-hub/gen@{DIGEST}", insecure=True), "insecure"),
            (oci(f"quay.io/x/gen@{DIGEST}"), "host quay.io is not allowed for oci"),
            (oci(f"ghcr.io/kadet-hub/gen@{DIGEST}", output_path="../x"), "output_path"),
            (helm(version=None), "exact chart version"),
            (helm(source="http://charts.example.org"), "https URL"),
            ({"type": "git", "source": "https://github.com/a/b.git", "ref": "main", "output_path": "x"}, "full commit SHA"),
            ({"type": "git", "source": "https://github.com/a/b.git", "ref": "c" * 40, "output_path": "x",
              "submodules": True}, "submodules"),
            ({"type": "http", "source": "http://example.org/x", "output_path": "x"}, "type http is not allowed"),
            ({"type": "https", "source": "https://user@example.org/x", "output_path": "x"}, "https URL"),
        ]
        for dep, want in cases:
            with self.subTest(want=want):
                _, findings = self.check(dep)
                self.assertTrue(any(want in f for f in findings), findings)

    def test_conflicting_output_path(self):
        _, findings = self.check(oci(f"ghcr.io/kadet-hub/gen@{DIGEST}"), oci(f"ghcr.io/kadet-hub/other@{DIGEST}"))
        self.assertTrue(any("used by another dependency" in f for f in findings), findings)


class Index(unittest.TestCase):
    def deps(self):
        deps, _ = dependencies(inventory(oci(f"ghcr.io/kadet-hub/gen@{DIGEST}"), helm()), POLICY, "kadet-hub")
        return deps

    def test_listed_version_passes_with_binaries_and_chart_digest(self):
        deps = self.deps()
        binaries, findings, notices = check_index(index(), POLICY, deps)
        self.assertEqual((binaries, findings, notices), (["helm template"], [], []))
        self.assertEqual(deps[1]["sha256"], "b" * 64)

    def test_lower_serial_fails_and_higher_is_reported(self):
        _, findings, _ = check_index(index(serial=4), POLICY, self.deps())
        self.assertTrue(any("serial 4 is lower" in f for f in findings), findings)
        _, findings, notices = check_index(index(serial=6), POLICY, self.deps())
        self.assertEqual(findings, [])
        self.assertTrue(notices)

    def test_unlisted_and_yanked_digests_fail(self):
        unlisted = index()
        unlisted["generators"]["gen"]["1.0.0"]["digest"] = "sha256:" + "c" * 64
        _, findings, _ = check_index(unlisted, POLICY, self.deps())
        self.assertTrue(any("does not list this digest" in f for f in findings), findings)
        _, findings, _ = check_index(index(yanked="broken"), POLICY, self.deps())
        self.assertTrue(any("yanked: broken" in f for f in findings), findings)


if __name__ == "__main__":
    unittest.main()
