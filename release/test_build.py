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
    """GI-9, REG-2, REG-3, PUB-15, REC-11: release/build.py on recipe entries next to a generator of the same name."""

    def build(self, recipes, extra=None, files_extra=None):
        with tempfile.TemporaryDirectory() as tmp:
            base, src, out = (os.path.join(tmp, d) for d in ("base", "src", "out"))
            shutil.copytree(os.path.join(HERE, "..", "policy"), os.path.join(base, "policy"))
            files = {"base/generators/demo.yaml": entry("generators", "demo", "demo-v1.0.0"),
                     "src/demo/kapitan-generator.yaml": "name: demo\ndescription: Demo\nlicense: MIT\nowners: [1]\n"
                                                        "kapitan: '>=0.36.3'\nfixtures: tests\n",
                     # PUB-15: the root LICENSE that build-all writes next to each tree.
                     "src/demo.LICENSE": "MIT License\n"}
            for name in recipes:
                files[f"base/recipes/{name}.yaml"] = entry("recipes", name, f"{name}-v2.0.0", (extra or {}).get(name, "exceptions: []\n"))
                # What fetch_tree.py --recipe writes: the recipe with its tests files and the other recipes of the commit.
                files.update({f"src/recipes/{name}/{name}/{p}": t for p, t in RECIPE.items()})
                files[f"src/recipes/{name}/other/init.yml"] = "{}\n"
                files[f"src/recipes/{name}/LICENSE"] = "Apache License\n"
            files.update(files_extra or {})
            for rel, text in files.items():
                if text is None:
                    continue
                os.makedirs(os.path.dirname(os.path.join(tmp, rel)), exist_ok=True)
                with open(os.path.join(tmp, rel), "w", encoding="utf-8") as f:
                    f.write(text)
            os.makedirs(out)  # as build-all does
            # Without -I, so build.py imports what this test imported.
            p = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), "--base", base, "--sources", src, "--out", out],
                               capture_output=True, text=True)
            built = {}
            for name in ["demo"] + [f"recipes/{r}" for r in recipes]:
                d = os.path.join(out, name)
                if os.path.isdir(d):
                    with open(os.path.join(d, "meta.json"), encoding="utf-8") as f, \
                            tarfile.open(os.path.join(d, f"{os.path.basename(name)}.tar")) as t:
                        built[name] = (json.load(f), {m: t.extractfile(m).read() for m in sorted(t.getnames())})
                    if os.path.exists(os.path.join(d, "schemas.json")):
                        with open(os.path.join(d, "schemas.json"), encoding="utf-8") as f:
                            built[name] += (json.load(f),)
                    else:
                        built[name] += (None,)
            names = None
            if os.path.exists(os.path.join(out, "names.json")):
                with open(os.path.join(out, "names.json"), encoding="utf-8") as f:
                    names = json.load(f)
            return p, names, built

    def test_recipe_artifact(self):
        p, names, built = self.build(["demo"])
        self.assertEqual((p.returncode, names), (0, ["demo", "recipes/demo"]), p.stdout)
        meta, members, _ = built["recipes/demo"]
        shipped = {k: (False, v.encode()) for k, v in RECIPE.items() if not k.startswith("tests/")}
        self.assertEqual(sorted(members), ["LICENSE", "README.md", "init.yml", "vendor/crds.yaml"])
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
        self.assertEqual((p.returncode, names, list(built)), (0, ["demo"], ["demo"]))
        self.assertIn("recipe demo 2.0.0: yanked, not built", p.stdout)

    def test_schemas(self):  # PUB-8: sources.yaml as JSON for the sign job, which parses no YAML
        manifest = "name: demo\ndescription: Demo\nlicense: MIT\nowners: [1]\nkapitan: '>=0.36.3'\nfixtures: tests\nschemas: ./schemas/\n"
        sources = "# QA-7\ncore:\n  software: Kubernetes\n  version: 1.37.1\n  copyright: [A, B]\n"
        p, _, built = self.build([], files_extra={"src/demo/kapitan-generator.yaml": manifest, "src/demo/schemas/sources.yaml": sources})
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertEqual(built["demo"][2], {"dir": "schemas", "sources": {"core": {"software": "Kubernetes", "version": "1.37.1", "copyright": ["A", "B"]}}})
        for broken in (None, "- core\n", "core: [\n"):  # missing, not a mapping, not YAML
            _, _, built = self.build([], files_extra={"src/demo/kapitan-generator.yaml": manifest, "src/demo/schemas/sources.yaml": broken})
            self.assertEqual(built["demo"][2], {"dir": "schemas", "sources": {}})
        _, _, built = self.build([])
        self.assertIsNone(built["demo"][2])

    def test_root_license(self):  # PUB-15
        p, names, built = self.build(["demo"])
        self.assertEqual(p.returncode, 0, p.stdout)
        # The tar gets the repository root's LICENSE; tree stays the ID of the tree without it.
        meta, members, _ = built["demo"]
        self.assertEqual(members, {"LICENSE": b"MIT License\n", "kapitan-generator.yaml": members["kapitan-generator.yaml"]})
        self.assertEqual(meta["tree"], tree_id({"kapitan-generator.yaml": (False, members["kapitan-generator.yaml"])}))
        self.assertEqual(built["recipes/demo"][1]["LICENSE"], b"Apache License\n")
        # A LICENSE in the tree is shipped as it is.
        p, _, built = self.build([], files_extra={"src/demo/LICENSE": "Own license\n"})
        self.assertEqual(built["demo"][1]["LICENSE"], b"Own license\n")
        self.assertEqual(built["demo"][0]["tree"], tree_id({k: (False, v) for k, v in built["demo"][1].items()}))
        # Without either the build fails.
        p, _, built = self.build(["demo"], files_extra={"src/demo.LICENSE": None, "src/recipes/demo/LICENSE": None})
        self.assertEqual((p.returncode, built), (1, {}))
        self.assertIn("PUB-15: demo: no LICENSE in the tree or at the repository root", p.stdout)
        self.assertIn("PUB-15: recipe demo: no LICENSE in the tree or at the repository root", p.stdout)


if __name__ == "__main__":
    unittest.main()
