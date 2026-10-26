import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

try:
    import jsonschema  # noqa: F401
    import yaml  # noqa: F401
except ImportError:
    raise unittest.SkipTest("build.py needs PyYAML and jsonschema; selftest runs this in the sandbox image")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from tree import tree_id  # noqa: E402

SHA = "a" * 40
RECIPE = {"init.yml": "classes: [.demo]\n", "README.md": "# demo\n", "vendor/crds.yaml": "kind: CRD\n",
          "tests/target.yml": "classes: [recipes.demo]\n", "tests/values.yaml": "{}\n", "tests/smoke": ""}


def entry(repo, path, tag, extra=""):
    return f"source:\n  repo: https://github.com/kadet-hub/{repo}.git\n  path: {path}\n  tag: {tag}\n  sha: {SHA}\nowners: [1]\n{extra}"


class Build(unittest.TestCase):
    """GI-9, REG-2, REG-3, REC-11: release/build.py on recipe entries next to a generator of the same name."""

    def build(self, recipes, extra=None):
        with tempfile.TemporaryDirectory() as tmp:
            base, src, out = (os.path.join(tmp, d) for d in ("base", "src", "out"))
            shutil.copytree(os.path.join(HERE, "..", "policy"), os.path.join(base, "policy"))
            files = {"base/generators/demo.yaml": entry("generators", "demo", "demo-v1.0.0"),
                     "src/demo/kapitan-generator.yaml": "name: demo\ndescription: Demo\nlicense: MIT\nowners: [1]\n"
                                                        "kapitan: '>=0.36.3'\nfixtures: tests\n"}
            for name in recipes:
                files[f"base/recipes/{name}.yaml"] = entry("recipes", name, f"{name}-v2.0.0", (extra or {}).get(name, "exceptions: []\n"))
                # What fetch_tree.py --recipe writes: the recipe with its tests files and the other recipes of the commit.
                files.update({f"src/recipes/{name}/{name}/{p}": t for p, t in RECIPE.items()})
                files[f"src/recipes/{name}/other/init.yml"] = "{}\n"
            for rel, text in files.items():
                os.makedirs(os.path.dirname(os.path.join(tmp, rel)), exist_ok=True)
                with open(os.path.join(tmp, rel), "w", encoding="utf-8") as f:
                    f.write(text)
            # Without -I, so build.py imports what this test imported.
            p = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), "--base", base, "--sources", src, "--out", out],
                               capture_output=True, text=True)
            built = {}
            for name in recipes:
                d = os.path.join(out, "recipes", name)
                if os.path.isdir(d):
                    with open(os.path.join(d, "meta.json"), encoding="utf-8") as f, tarfile.open(os.path.join(d, f"{name}.tar")) as t:
                        built[name] = (json.load(f), sorted(t.getnames()))
            names = None
            if os.path.exists(os.path.join(out, "names.json")):
                with open(os.path.join(out, "names.json"), encoding="utf-8") as f:
                    names = json.load(f)
            return p, names, built

    def test_recipe_artifact(self):
        p, names, built = self.build(["demo"])
        self.assertEqual((p.returncode, names), (0, ["demo", "recipes/demo"]), p.stdout)
        meta, members = built["demo"]
        shipped = {k: (False, v.encode()) for k, v in RECIPE.items() if not k.startswith("tests/")}
        self.assertEqual(members, ["README.md", "init.yml", "vendor/crds.yaml"])
        self.assertEqual(meta, {"name": "demo", "version": "2.0.0", "tree": tree_id(shipped), "owners": [1],
                                "source": {"repo": "https://github.com/kadet-hub/recipes.git", "path": "demo",
                                           "tag": "demo-v2.0.0", "sha": SHA}})

    def test_recipe_names(self):  # REG-2, REG-3 among recipes and the reserved names (REC-2)
        p, names, built = self.build(["recipes", "foo-bar", "foobar"])
        self.assertEqual(p.returncode, 1)
        self.assertIn("REG-2: recipe recipes is reserved", p.stdout)
        self.assertIn("REG-3: recipe foobar equals foo-bar without separators", p.stdout)
        p, _, _ = self.build(["demo"], {"demo": "exceptions: []\nunknown: 1\n"})
        self.assertEqual(p.returncode, 1)
        self.assertIn("GI-9: recipe demo: entry:", p.stdout)

    def test_yanked_recipe_is_not_built(self):  # PUB-2
        p, names, built = self.build(["demo"], {"demo": "yanked:\n  2.0.0: broken\n"})
        self.assertEqual((p.returncode, names, built), (0, ["demo"], {}))
        self.assertIn("recipe demo 2.0.0: yanked, not built", p.stdout)


if __name__ == "__main__":
    unittest.main()
