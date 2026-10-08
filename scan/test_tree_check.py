import os
import tempfile
import unittest

import tree_check

IMPORTS = os.path.join(os.path.dirname(__file__), "..", "policy", "imports.txt")


def check(files, binaries=False, links=()):
    with tempfile.TemporaryDirectory() as d:
        for rel, content in files.items():
            path = os.path.join(d, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(content.encode() if isinstance(content, str) else content)
        for src, dst in links:
            os.symlink(src, os.path.join(d, dst))
        return tree_check.check_tree(d, tree_check.parse_imports(IMPORTS, binaries))


class Imports(unittest.TestCase):
    def test_benign_generator_passes(self):
        self.assertEqual(check({
            "__init__.py": "import os\nimport yaml\nfrom omegaconf import OmegaConf\n"
                           "from kapitan.inputs.kadet import BaseObj, inventory\nfrom . import util\nimport helpers\n",
            "util.py": "from .helpers import x\n",
            "helpers.py": "x = 1\n",
        }), [])

    def test_blocked_imports(self):
        for line in ("import socket", "import _posixsubprocess", "import subprocess", "import importlib",
                     "from kapitan.inputs.kadet import cached", "from kapitan.inputs import kadet",
                     "import kapitan.inputs.kadet", "from jinja2.sandbox import Environment", "import jinja2",
                     "from os import system", "from os import *", "from yaml import unsafe_load", "import ctypes"):
            self.assertTrue(check({"__init__.py": line + "\n"}), line)

    def test_subprocess_needs_declared_binary(self):
        self.assertEqual(check({"__init__.py": "import subprocess\n"}, binaries=True), [])

    def test_shadowing_stdlib_name_is_not_in_tree(self):
        self.assertTrue(check({"__init__.py": "import socket\n", "socket.py": ""}))

    def test_unparseable_file_fails(self):
        self.assertTrue(check({"x.py": "def (:\n"}))


class Tree(unittest.TestCase):
    def test_banned_files(self):
        for rel in (".gitattributes", ".gitmodules", "lib/x.so", "x.pyc", "a.pth", "sitecustomize.py", ".semgrepignore"):
            self.assertTrue(check({rel: ""}), rel)

    def test_symlink_lfs_size_template_collision(self):
        self.assertTrue(check({"a.txt": ""}, links=[("/etc/passwd", "l")]))
        self.assertTrue(check({"big.bin": "x" * (1024 * 1024 + 1)}))
        self.assertTrue(check({"f": "version https://git-lfs.github.com/spec/v1\noid sha256:0\n"}))
        self.assertTrue(check({"t.j2": "{{ cycler.__init__.__globals__ }}"}))
        self.assertTrue(check({"A.txt": "", "a.txt": ""}))
        self.assertTrue(check({"ü.txt": ""}))


if __name__ == "__main__":
    unittest.main()
