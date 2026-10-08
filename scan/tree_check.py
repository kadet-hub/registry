"""Check the generator tree's files and Python imports (SEC-3, SEC-5).

Usage: tree_check.py --tree DIR --imports FILE [--binaries-declared]

Runs in the sandbox image so the syntax tree is parsed by the Python version
that compiles the generator. Prints findings; exits 1 if there is any.
"""

import argparse
import ast
import fnmatch
import importlib.util
import os
import stat
import sys
import unicodedata

MAX_SIZE = 1024 * 1024
BANNED_NAMES = {".gitattributes", ".gitmodules", "sitecustomize.py", "usercustomize.py",
                ".gitleaks.toml", ".gitleaksignore", ".semgrepignore"}
BANNED_SUFFIXES = (".pyc", ".pyo", ".so", ".pyd", ".pth")
LFS_POINTER = b"version https://git-lfs.github.com/spec/v1"
TEMPLATE_DUNDERS = (b"__globals__", b"__builtins__", b"__subclasses__", b"__mro__", b"__base__", b"__class__")


def parse_imports(path, binaries_declared):
    """Lines: <module> [import] [name ...]; '*' any name, '!glob' forbidden name."""
    policy = {}
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    if binaries_declared:
        lines.append("subprocess import *")
    for raw in lines:
        fields = raw.split("#", 1)[0].split()
        if not fields:
            continue
        module, *rest = fields
        policy[module] = {
            "import": "import" in rest,
            "names": {f for f in rest if f not in ("import",) and not f.startswith("!")},
            "deny": [f[1:] for f in rest if f.startswith("!")],
        }
    return policy


def in_tree(module, file_dir, tree):
    """A module of the generator's own, never one that resolves outside the tree."""
    top = module.split(".")[0]
    if top in sys.stdlib_module_names or importlib.util.find_spec(top) is not None:
        return False
    return any(os.path.isfile(os.path.join(d, top + ".py")) or os.path.isdir(os.path.join(d, top))
               for d in (file_dir, tree))


def check_imports(rel, tree_ast, file_dir, tree, policy):
    findings = []
    for node in ast.walk(tree_ast):
        if isinstance(node, ast.Import):
            for alias in node.names:
                entry = policy.get(alias.name)
                if not (in_tree(alias.name, file_dir, tree) or (entry and entry["import"])):
                    findings.append(f"imports: {rel}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level or in_tree(node.module or "", file_dir, tree):
                continue
            entry = policy.get(node.module)
            for alias in node.names:
                name = alias.name
                ok = entry is not None and ("*" in entry["names"] or name in entry["names"])
                if ok and name == "*":
                    ok = "*" in entry["names"] and not entry["deny"]
                if ok and any(fnmatch.fnmatchcase(name, d) for d in entry["deny"]):
                    ok = False
                if not ok:
                    findings.append(f"imports: {rel}:{node.lineno}: from {node.module} import {name}")
    return findings


def check_tree(tree, policy):
    findings = []
    seen = {}
    for root, dirs, files in os.walk(tree):
        for name in sorted(dirs + files):
            path = os.path.join(root, name)
            rel = os.path.relpath(path, tree)
            if not rel.isascii():
                findings.append(f"tree: non-ASCII path {rel!r}")
            key = unicodedata.normalize("NFKC", rel).casefold()
            if key in seen:
                findings.append(f"tree: {rel} collides with {seen[key]}")
            seen.setdefault(key, rel)
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode):
                findings.append(f"tree: symlink {rel}")
                continue
            if stat.S_ISDIR(st.st_mode):
                continue
            if not stat.S_ISREG(st.st_mode):
                findings.append(f"tree: special file {rel}")
                continue
            if name in BANNED_NAMES or name.endswith(BANNED_SUFFIXES):
                findings.append(f"tree: banned file {rel}")
            if st.st_mode & 0o111:
                findings.append(f"tree: executable {rel}")
            if st.st_size > MAX_SIZE:
                findings.append(f"tree: {rel} above 1 MiB")
                continue
            with open(path, "rb") as f:
                data = f.read()
            if data.startswith(LFS_POINTER):
                findings.append(f"tree: LFS pointer {rel}")
            if name.endswith(".py"):
                try:
                    parsed = ast.parse(data, filename=rel)
                except (SyntaxError, ValueError) as e:
                    findings.append(f"imports: {rel}: does not parse: {e}")
                    continue
                findings += check_imports(rel, parsed, root, tree, policy)
            else:
                for d in TEMPLATE_DUNDERS:
                    if d in data:
                        findings.append(f"template: {rel}: {d.decode()}")
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
    return findings


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True)
    p.add_argument("--imports", required=True)
    p.add_argument("--binaries-declared", action="store_true")
    a = p.parse_args()
    findings = check_tree(a.tree, parse_imports(a.imports, a.binaries_declared))
    if findings:
        print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
