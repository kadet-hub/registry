"""Unit tests of the provenance replay in kapitan_wasm.py (PG-15 to PG-19).

Each fixture compiles with Kapitan and asserts the replay and that it found no
difference from the inventory Kapitan rendered. It needs Kapitan and its
backends, so the playground workflow runs it in the sandbox image and the
catalog tests leave it out.
"""

import json
import os
import sys
import unittest

# build.py copies every file of that directory to the site, so no __pycache__ there.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "static", "playground"))
import kapitan_wasm

TARGET = ("parameters:\n  kapitan:\n    vars:\n      target: t\n"
          "    compile:\n      - {output_path: ., input_type: jinja2, input_paths: [t.j2]}\n")
# t lists a and e; a lists b, b and e list common. omegaconf merges common twice, reclass once.
DIAMOND = {
    "t.j2": "t\n",
    "inventory/targets/t.yml": "classes: [a, e]\n" + TARGET + "  d:\n    k2: t\n",
    "inventory/classes/a.yml": "classes: [b]\nparameters:\n  v: a\n  w: a\n  lst: [x, y]\n",
    "inventory/classes/b.yml": "classes: [common]\nparameters:\n  v: b\n",
    "inventory/classes/e.yml": "classes: [common, f]\nparameters:\n  e: e\n",
    "inventory/classes/f.yml": "parameters:\n  w: f\n",
    "inventory/classes/common.yml": "parameters:\n  v: common\n  lst: [x]\n  d:\n    k: common\n  r:\n    a: 1\n",
}


def trace(files, backend):
    code, log, _, prov = kapitan_wasm.compile_project(files, backend)
    prov = json.loads(prov)
    assert code == 0 and "error" not in prov, (log, prov)
    return prov["t"]


def chain(t, path):
    """[(source name, raw value, op)] of the leaf at path."""
    (p,) = [p for p in t["params"] if p["path"] == path.split(".")]
    return p["value"], [(t["sources"][e["source"]]["name"], e["value"], e["op"]) for e in p["chain"]]


class Provenance(unittest.TestCase):
    def test_class_order(self):  # PG-15, PG-16
        om = trace(DIAMOND, "omegaconf")
        self.assertEqual([(s["name"], s["via"]) for s in om["sources"] if s["kind"] in ("class", "target")],
                         [("common", "b"), ("b", "a"), ("a", "t"), ("common", "e"), ("f", "e"), ("e", "t"), ("t", None)])
        self.assertEqual(om["other"]["backend"], "reclass")
        self.assertEqual([c["name"] for c in om["other"]["classes"]], ["common", "b", "a", "f", "e"])
        self.assertEqual([s["file"] for s in om["sources"] if s["kind"] == "class"][:2], ["classes/common.yml", "classes/b.yml"])
        rc = trace(DIAMOND, "reclass")
        self.assertEqual([s["name"] for s in rc["sources"] if s["kind"] == "class"], ["common", "b", "a", "f", "e"])
        self.assertEqual([c["name"] for c in rc["other"]["classes"]], ["common", "b", "a", "common", "f", "e"])
        for t in (om, rc):
            self.assertEqual(t["mismatches"], [])
            self.assertEqual([s["kind"] for s in t["sources"]][-2:], ["target", "compile"])

    def test_override_chain(self):  # PG-17: the second merge of common wins under omegaconf only
        om, rc = trace(DIAMOND, "omegaconf"), trace(DIAMOND, "reclass")
        self.assertEqual(chain(om, "v"),
                         ("common", [("common", "common", "set"), ("b", "b", "set"), ("a", "a", "set"), ("common", "common", "set")]))
        self.assertEqual(chain(rc, "v"), ("a", [("common", "common", "set"), ("b", "b", "set"), ("a", "a", "set")]))
        # reclass lists its classes as common, b, f, a, e but merges a before f.
        for t in (om, rc):
            self.assertEqual(chain(t, "w"), ("f", [("a", "a", "set"), ("f", "f", "set")]))

    def test_list_merge(self):  # PG-17: EXTEND_UNIQUE against reclass's append
        self.assertEqual(chain(trace(DIAMOND, "omegaconf"), "lst"),
                         (["x", "y"], [("common", ["x"], "set"), ("a", ["x", "y"], "extend"), ("common", ["x"], "extend")]))
        self.assertEqual(chain(trace(DIAMOND, "reclass"), "lst"),
                         (["x", "x", "y"], [("common", ["x"], "set"), ("a", ["x", "y"], "extend")]))

    def test_none_replaces_a_mapping(self):  # PG-17: the replaced leaves stay in the chain
        files = dict(DIAMOND)
        files["inventory/targets/t.yml"] += "  r: null\n"
        for backend, merged in (("omegaconf", 2), ("reclass", 1)):
            t = trace(files, backend)
            self.assertEqual(t["mismatches"], [], backend)
            (p,) = [p for p in t["params"] if p["path"] == ["r"]]
            self.assertEqual([(e["path"], e["value"]) for e in p["chain"]], [(["r", "a"], 1)] * merged + [(["r"], None)], backend)

    def test_reclass_override_prefix(self):  # PG-17
        files = dict(DIAMOND)
        files["inventory/targets/t.yml"] = files["inventory/targets/t.yml"].replace("  d:\n", "  ~d:\n")
        t = trace(files, "reclass")
        self.assertEqual(t["mismatches"], [])
        self.assertNotIn(["d", "k"], [p["path"] for p in t["params"]])
        self.assertEqual(chain(t, "d.k2"), ("t", [("common", "common", "set"), ("t", "t", "set")]))

    def test_interpolation(self):  # PG-17: raw and resolved value; a reference to a mapping resolves to its leaves
        for backend, ref in (("omegaconf", "${d.k}"), ("reclass", "${d:k}")):
            files = dict(DIAMOND)
            files["inventory/targets/t.yml"] += f"  name: {ref}-x\n  copy: ${{r}}\n"
            t = trace(files, backend)
            self.assertEqual(t["mismatches"], [], backend)
            self.assertEqual(chain(t, "name"), ("common-x", [("t", f"{ref}-x", "set")]))
            self.assertEqual(chain(t, "copy"), ({"a": 1}, [("t", "${r}", "set")]))

    def test_difference_is_reported(self):  # PG-19: omegaconf keeps a value that ??? would replace in the replay
        files = dict(DIAMOND)
        files["inventory/targets/t.yml"] += "  v: '???'\n"
        t = trace(files, "omegaconf")
        self.assertEqual(t["mismatches"], [["v"]])

    def test_other_backend_cannot_read(self):  # PG-16: the recipes' layout; reclass reads .g in g as g itself
        files = {"t.j2": "t\n", "inventory/targets/t.yml": "classes: [g]\n" + TARGET,
                 "inventory/classes/g/init.yml": "classes: [.g]\n", "inventory/classes/g/g.yml": "parameters:\n  v: g\n"}
        t = trace(files, "omegaconf")
        self.assertEqual([(s["name"], s["via"], s["file"]) for s in t["sources"] if s["kind"] == "class"],
                         [(".g", "g", "classes/g/g.yml"), ("g", "t", "classes/g/init.yml")])
        self.assertEqual(t["other"], {"backend": "reclass", "error": "ValueError: class g includes itself"})


if __name__ == "__main__":
    unittest.main()
