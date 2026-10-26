import os
import shutil
import tempfile
import unittest

import check_recipe

POLICY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "policy")
LISTED, YANKED = "sha256:" + "a" * 64, "sha256:" + "b" * 64
INDEX = {"serial": 1, "generators": {"kubernetes": {"1.9.0": {"digest": LISTED}, "1.8.0": {"digest": YANKED, "yanked": "broken"}}}}
INIT = f"""classes:
  - .demo
  - recipes.demo.crds
  - recipes.other
  - recipes.other.route
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/kubernetes:1.9.0@{LISTED}
        output_path: lib/kubernetes
    compile:
      - input_type: copy
        input_paths:
          - inventory/classes/recipes/demo/vendor/crds.yaml
        output_path: manifests/
"""
FILES = {
    "README.md": "# demo\n",
    "init.yml": INIT,
    "demo.yml": "parameters: {}\n",
    "demo.yml.LICENSE": "Apache License\n",
    "demo.yml.NOTICE": "Demo\n",
    "crds.yml": "parameters: {}\n",
    "vendor/crds.yaml": "kind: CustomResourceDefinition\n",
    "vendor/crds.yaml.LICENSE": "Apache License\n",
    "vendor/crds.yaml.NOTICE": "Demo\n",
    "vendor/script.sh": "true\n",
    "tests/target.yml": "classes: [recipes.demo]\n",
    "tests/smoke": "",
}
APACHE = "Apache License\n                           Version 2.0, January 2004\n"


def check(changes=None, license_text=APACHE):
    d = tempfile.mkdtemp()
    try:
        for rel, text in {**FILES, **(changes or {})}.items():
            if text is not None:
                path = os.path.join(d, "demo", rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
        license_path = None
        if license_text is not None:
            license_path = os.path.join(d, "LICENSE")
            with open(license_path, "w", encoding="utf-8") as f:
                f.write(license_text)
        return check_recipe.check(os.path.join(d, "demo"), INDEX, POLICY, license_path)
    finally:
        shutil.rmtree(d)


def init(old, new):
    return {"init.yml": INIT.replace(old, new)}


class Recipe(unittest.TestCase):
    def assert_finding(self, prefix, changes=None, **kwargs):
        findings, _ = check(changes, **kwargs)
        self.assertTrue(any(f.startswith(prefix) for f in findings), (changes, findings))

    def test_passes(self):  # REC-4, REC-5, REC-6, REC-15
        self.assertEqual(check(), ([], [f"ghcr.io/kadet-hub/kubernetes@{LISTED}"]))
        # Nothing below tests/ is judged.
        self.assertEqual(check({"tests/run.py": "", "tests/x.yml": "classes: [kapitan]\n"})[0], [])

    def test_layout(self):  # REC-4
        for changes in ({"notes.txt": ""}, {"x.yaml": ""}, {"sub/x.yml": "parameters: {}\n"}, {"orphan.yml.LICENSE": ""},
                        {"README.md.LICENSE": ""}, {"x.py": ""}, {"vendor/x.py": ""}, {"vendor/x.yml": "parameters: {}\n"},
                        {"vendor/x.yaml": ""}, {"tests/target.yml": None, "tests/smoke": None, "tests": ""}):
            self.assert_finding("REC-4", changes)

    def test_license(self):  # REC-4
        self.assert_finding("REC-4: the source repository's root LICENSE", license_text="All rights reserved.\n")
        self.assert_finding("REC-4: the source repository's root LICENSE", license_text=None)

    def test_vendored_license(self):  # REC-15
        self.assert_finding("REC-15: vendor/crds.yaml", {"vendor/crds.yaml.LICENSE": None})
        self.assertEqual(check({"vendor/crds.yaml.NOTICE": None})[0], [])

    def test_includes(self):  # REC-5
        for cls in ("recipes.demo", "recipes.other.vendor.x", "kapitan.x", "recipes.Other", "recipes"):
            self.assert_finding("REC-5: init.yml: class", init("  - recipes.other\n", f"  - {cls}\n"))
        self.assert_finding("REC-5: init.yml is not YAML", {"init.yml": "["})
        self.assert_finding("REC-5: init.yml is not YAML", {"init.yml": "[" * 2000})

    def test_pins(self):  # REC-6
        source = f"ghcr.io/kadet-hub/kubernetes:1.9.0@{LISTED}"
        for old, new in ((source, f"ghcr.io/kadet-hub/kubernetes@{LISTED}"), (source, f"docker.io/kadet-hub/kubernetes:1.9.0@{LISTED}"),
                         (source, "ghcr.io/kadet-hub/kubernetes:1.9.0"), ("output_path: lib/kubernetes", "output_path: lib/k8s"),
                         ("type: oci", "type: helm"), (source, f"ghcr.io/kadet-hub/kubernetes:1.9.0@sha256:{'c' * 64}"),
                         (source, f"ghcr.io/kadet-hub/kubernetes:1.8.0@{LISTED}"), (source, f"ghcr.io/kadet-hub/kubernetes:1.8.0@{YANKED}")):
            self.assert_finding("REC-6", init(old, new))


if __name__ == "__main__":
    unittest.main()
