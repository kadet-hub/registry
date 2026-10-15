"""GI-14: plan.py's dependency and index checks on a fuzzed parameters.kapitan.dependencies.

`kapitan inventory` writes the inventory, so only a YAML list of mappings
is passed on, as one target's dependencies.
"""

import os
import sys

import atheris

ROOT = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path[:0] = [os.path.join(ROOT, "consumer"), os.path.join(ROOT, "gate")]
with atheris.instrument_imports():
    import plan
    import yaml

DIGEST = "sha256:" + "0" * 64
POLICY = {"index_serial": 5, "hosts": {"oci": ["ghcr.io"], "helm": ["charts.example.org"], "git": ["github.com"],
                                       "https": ["example.org"]}}
INDEX = {"serial": 5, "generators": {"gen": {
    "1.0.0": {"digest": DIGEST, "binaries": ["helm"],
              "charts": [{"repo": "https://charts.example.org/", "name": "app", "version": "1.0.0", "sha256": "a" * 64}]},
    "0.9.0": {"digest": "sha256:" + "1" * 64, "yanked": "broken"}}}}


def TestOneInput(data):
    try:
        deps = yaml.safe_load(data)
    except yaml.YAMLError:
        return
    if not isinstance(deps, list) or not all(isinstance(d, dict) for d in deps):
        return
    deps, _ = plan.dependencies({"minimal": {"parameters": {"kapitan": {"dependencies": deps}}}}, POLICY, "kadet-hub")
    plan.check_index(INDEX, POLICY, deps)


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
