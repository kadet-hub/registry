"""GI-14: check_recipe.py on a fuzzed class file init.yml of a recipe that requires the recipe other."""

import os
import sys
import tempfile

import atheris

ROOT = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path[:0] = [os.path.join(ROOT, "gate"), os.path.join(ROOT, "consumer"), os.path.join(ROOT, "release")]
with atheris.instrument_imports():
    import check_recipe

POLICY = os.path.join(ROOT, "policy")
DIGEST = "sha256:" + "0" * 64
INDEX = {"serial": 5, "generators": {"kubernetes": {"1.9.0": {"digest": DIGEST}, "1.8.0": {"digest": "sha256:" + "1" * 64,
                                                                                        "yanked": "broken"}}},
         "recipes": {"other": {"1.0.0": {"tree": "0" * 40, "digest": DIGEST}}}}
WORK = tempfile.mkdtemp()
TREE = os.path.join(WORK, "demo")
for rel in ("README.md", "demo.yml", "vendor/crds.yaml", "vendor/crds.yaml.LICENSE", "tests/target.yml", "../other/init.yml"):
    os.makedirs(os.path.dirname(os.path.join(TREE, rel)), exist_ok=True)
    with open(os.path.join(TREE, rel), "w", encoding="utf-8") as f:
        f.write("parameters: {}\n")
LICENSE = os.path.join(WORK, "LICENSE")
with open(LICENSE, "w", encoding="utf-8") as f:
    f.write("Apache License, Version 2.0\n")


def TestOneInput(data):
    with open(os.path.join(TREE, "init.yml"), "wb") as f:
        f.write(data)
    check_recipe.check(TREE, INDEX, POLICY, LICENSE, ["other"])


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
