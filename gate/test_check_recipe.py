import os
import shutil
import tempfile
import unittest

import check_recipe
from tree import tree_id

POLICY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "policy")
LISTED, YANKED = "sha256:" + "a" * 64, "sha256:" + "b" * 64
PUBLISHED, OLDER = "sha256:" + "d" * 64, "sha256:" + "e" * 64
INDEX = {"serial": 1, "generators": {"kubernetes": {"1.9.0": {"digest": LISTED}, "1.8.0": {"digest": YANKED, "yanked": "broken"}},
                                     "cloudnative-pg": {"1.1.0": {"digest": LISTED, "binaries": ["helm template"]}}}}
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
    "README.md": "# demo\n\nThe demo recipe, rendered by\n  the `kubernetes` generator.\n\nSource: `oci://ghcr.io/x/demo:1.0.0@sha256:0`\n\nLevel: `renders`\n",
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
OTHER = {"init.yml": "parameters: {}\n", "tests/target.yml": "classes: [recipes.other]\n"}


def tree_of(files):
    """The tree ID the release records for a recipe directory of files: without tests/ (REC-11)."""
    return tree_id({p: (False, t.encode()) for p, t in files.items() if p.split("/")[0] != "tests"})


def check(changes=None, license_text=APACHE, other=None, req=None, required=(), recipes=None):
    """check_recipe.check on demo with changes, the included recipe other and the recipe req as {path: text},
    and the index's recipes, by default other's tree as other 1.0.0."""
    other = OTHER if other is None else other
    recipes = {"other": {"1.0.0": {"tree": tree_of(other), "digest": PUBLISHED}}} if recipes is None else recipes
    d = tempfile.mkdtemp()
    try:
        others = [(f"../{n}/{rel}", text) for n, files in (("other", other), ("req", req or {})) for rel, text in files.items()]
        for rel, text in [*{**FILES, **(changes or {})}.items(), *others]:
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
        return check_recipe.check(os.path.join(d, "demo"), {**INDEX, "recipes": recipes}, POLICY, license_path, required)
    finally:
        shutil.rmtree(d)


def init(old, new):
    return {"init.yml": INIT.replace(old, new)}


class Recipe(unittest.TestCase):
    def assert_finding(self, prefix, changes=None, **kwargs):
        findings, _ = check(changes, **kwargs)
        self.assertTrue(any(f.startswith(prefix) for f in findings), (changes, findings))

    def test_passes(self):  # REC-4, REC-5, REC-6, REC-15, REC-16, what REC-10 shows and REC-13 records
        self.assertEqual(check(), ([], {"pull": [[f"ghcr.io/kadet-hub/kubernetes@{LISTED}", "lib/kubernetes"]], "binaries": [],
                                        "included": ["other"], "required": {},
                                        "recipes": {"other": {"rule": "REC-16", "version": "1.0.0", "digest": PUBLISHED}},
                                        "pins": [f"ghcr.io/kadet-hub/kubernetes:1.9.0@{LISTED}"],
                                        "source": ["Source: `oci://ghcr.io/x/demo:1.0.0@sha256:0`"], "level": ["Level: `renders`"],
                                        "description": "The demo recipe, rendered by the `kubernetes` generator.",
                                        "license": "Apache-2.0"}))
        # Nothing below tests/ is judged.
        self.assertEqual(check({"tests/run.py": "", "tests/x.yml": "classes: [kapitan]\n"})[0], [])

    def test_layout(self):  # REC-4
        for changes in ({"notes.txt": ""}, {"x.yaml": ""}, {"sub/x.yml": "parameters: {}\n"}, {"orphan.yml.LICENSE": ""},
                        {"README.md.LICENSE": ""}, {"x.py": ""}, {"vendor/x.py": ""}, {"vendor/x.yml": "parameters: {}\n"},
                        {"vendor/x.yaml": ""}, {"tests/target.yml": None, "tests/smoke": None, "tests": ""}):
            self.assert_finding("REC-4", changes)

    def test_license(self):  # REC-4, REC-13
        self.assert_finding("REC-4: the source repository's root LICENSE", license_text="All rights reserved.\n")
        self.assert_finding("REC-4: the source repository's root LICENSE", license_text=None)
        mit = "Permission is hereby granted, free of charge, to any person\nobtaining a copy of this software\n"
        self.assertEqual(check(license_text=mit)[1]["license"], "MIT")
        self.assertIsNone(check(license_text=None)[1]["license"])

    def test_description(self):  # REC-13, QA-5a
        readme = "# demo\r\n\r\nThe demo\trecipe.\r\nSecond line.\r\n\r\n## Include\n"
        self.assertEqual(check({"README.md": readme})[1]["description"], "The demo recipe. Second line.")
        self.assertEqual(check({"README.md": "# demo\nText right below.\n"})[1]["description"], "Text right below.")
        for readme in ("# demo\n\n## Include\n", "# demo\n", "", None, "No heading.\n"):
            self.assert_finding("REC-13: README.md has no paragraph after its heading", {"README.md": readme})
        for char in ("\x1b", "\x00", "\x0c", "\x85", "\u202e", "\u2066", "\u061c"):
            self.assert_finding("QA-5a: README.md: the first paragraph", {"README.md": f"# demo\n\nThe {char}demo recipe.\n"})
            self.assertIsNone(check({"README.md": f"# demo\n\nThe {char}demo recipe.\n"})[1]["description"])

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

    def test_included(self):  # REC-6, REC-8
        pin = f"""parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/cloudnative-pg:1.1.0@{LISTED}
        output_path: lib/cloudnative-pg
"""
        findings, result = check(other={"init.yml": pin, "tests/target.yml": "x: [", "sub/x.yml": "["})
        self.assertEqual((findings, result["pull"], result["binaries"]),
                         ([], [[f"ghcr.io/kadet-hub/cloudnative-pg@{LISTED}", "lib/cloudnative-pg"],
                               [f"ghcr.io/kadet-hub/kubernetes@{LISTED}", "lib/kubernetes"]], ["helm template"]))
        # Only the recipes demo includes pin generators of its compile.
        alone = init("  - recipes.other\n  - recipes.other.route\n", "")
        self.assertEqual(check(alone, other={"init.yml": pin})[1]["pull"], [[f"ghcr.io/kadet-hub/kubernetes@{LISTED}", "lib/kubernetes"]])
        self.assert_finding("REC-6: CON-2: ghcr.io/kadet-hub/cloudnative-pg:1.1.0@sha256:ccc",
                            other={"init.yml": pin.replace(LISTED, "sha256:" + "c" * 64)})
        self.assert_finding("REC-6: other/init.yml is not YAML", other={"init.yml": "["})
        self.assert_finding("REC-6: other/init.yml: dependency", other={"init.yml": pin.replace("lib/cloudnative-pg", "lib/x")})


    def test_published(self):  # REC-16
        tree = tree_of(OTHER)
        # The oldest version with the tree that is not yanked.
        versions = {"1.1.0": {"tree": tree, "digest": LISTED}, "1.0.10": {"tree": tree, "digest": PUBLISHED},
                    "1.0.9": {"tree": tree, "digest": OLDER, "yanked": "broken"}, "1.0.1": {"tree": "0" * 40, "digest": OLDER}}
        self.assertEqual(check(recipes={"other": versions})[1]["recipes"],
                         {"other": {"rule": "REC-16", "version": "1.0.10", "digest": PUBLISHED}})
        # tests/ is not part of the tree; every other file is.
        self.assertEqual(check(other={**OTHER, "tests/x.yml": "x\n"}, recipes={"other": versions})[0], [])
        self.assert_finding(f"REC-16: the index lists no version of other with tree {tree_of({**OTHER, 'vendor/x.yaml': ''})}",
                            other={**OTHER, "vendor/x.yaml": ""}, recipes={"other": versions})
        self.assert_finding(f"REC-16: the index lists no version of other with tree {tree}", recipes={})
        self.assert_finding("REC-16: the index lists no version of other", recipes={"other": {"1.0.1": versions["1.0.1"]}})
        self.assert_finding(f"REC-16: the index lists other 1.0.9 with tree {tree} only yanked",
                            recipes={"other": {"1.0.9": versions["1.0.9"]}})
        self.assert_finding("REC-16: other is not a recipe directory at source.sha", other={"README.md": "# other\n"})
        self.assertEqual(check(recipes={})[1]["recipes"], {})

    def test_required(self):  # REC-17, REC-6
        pin = f"""parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/cloudnative-pg:1.1.0@{LISTED}
        output_path: lib/cloudnative-pg
"""
        req = {"init.yml": pin, "README.md": "# req\n", "tests/target.yml": "classes: [recipes.req]\n"}
        recipes = {"other": {"1.0.0": {"tree": tree_of(OTHER), "digest": PUBLISHED}}, "req": {"2.0.0": {"tree": tree_of(req), "digest": OLDER}}}
        findings, result = check(req=req, required=["req"], recipes=recipes)
        self.assertEqual(findings, [])
        # A project of its own: its generators below requires/req/lib, its binaries apart from the recipe's.
        self.assertEqual((result["pull"], result["binaries"], result["required"]),
                         ([[f"ghcr.io/kadet-hub/kubernetes@{LISTED}", "lib/kubernetes"],
                           [f"ghcr.io/kadet-hub/cloudnative-pg@{LISTED}", "requires/req/lib/cloudnative-pg"]], [], {"req": ["helm template"]}))
        self.assertEqual(result["recipes"]["req"], {"rule": "REC-17", "version": "2.0.0", "digest": OLDER})
        self.assertEqual(result["pins"], [f"ghcr.io/kadet-hub/kubernetes:1.9.0@{LISTED}"])
        self.assert_finding(f"REC-17: the index lists no version of req with tree {tree_of(req)}", req=req, required=["req"])
        self.assert_finding("REC-17: the index lists req 2.0.0", req=req, required=["req"],
                            recipes={"req": {"2.0.0": {**recipes["req"]["2.0.0"], "yanked": "broken"}}})
        self.assert_finding(f"REC-6: CON-2: ghcr.io/kadet-hub/cloudnative-pg:1.1.0@sha256:{'c' * 64}",
                            req={**req, "init.yml": pin.replace(LISTED, "sha256:" + "c" * 64)}, required=["req"], recipes=recipes)
        self.assert_finding("REC-17: missing is not a recipe directory at source.sha", required=["missing"])
        # A recipe that is only next to it is neither verified nor resolved.
        self.assertEqual(check(req=req, recipes=recipes)[1]["required"], {})

if __name__ == "__main__":
    unittest.main()
