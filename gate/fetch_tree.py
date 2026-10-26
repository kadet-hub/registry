"""Write the git tree <rev>:<path> to a directory without git checkout (PUB-1, SEC-5, REC-4).

Usage: fetch_tree.py --git-dir D --rev SHA (--path P | --recipe NAME | --targets NAME...) --out DIR

Reads objects with `git ls-tree` and `git cat-file`, so no checkout,
attributes, filters, hooks or LFS run. Symlinks and submodules are reported
instead of written; executables keep their mode so SEC-5 sees them.
--recipe writes every recipe directory of the commit to DIR/<recipe>
without tests/, and of NAME also tests/target.yml, tests/values.yaml and,
when the commit has it, an empty tests/smoke; no other file below tests/
is read. --targets writes only NAME/tests/target.yml of each recipe, for
the included recipes REC-8 compiles.
Exits 1 on a finding or when the tree exceeds its limits.
"""

import argparse
import os
import re
import subprocess
import sys

MAX_FILES = 5000
MAX_TOTAL = 50 * 1024 * 1024
RECIPE = re.compile(rb"^[a-z][a-z0-9-]{1,38}$")
RECIPE_TESTS = (b"tests/target.yml", b"tests/values.yaml")


def git(git_dir, *args, data=None):
    return subprocess.run(["git", f"--git-dir={git_dir}", *args], input=data, capture_output=True, check=True).stdout


def ls_tree(git_dir, tree, recursive=True):
    """(mode, kind, object, path) of every entry of tree."""
    listing = git(git_dir, "ls-tree", *(["-r"] if recursive else []), "-z", "--full-tree", tree)
    out = []
    for e in listing.split(b"\0"):
        if e:
            meta, raw_path = e.split(b"\t", 1)
            out.append((*meta.decode().split(), raw_path))
    return out


def recipe_entries(git_dir, rev, name):
    """REC-4, REC-5: the recipe directories of rev without tests/, NAME with the files check lint needs."""
    out = []
    for _, kind, _, d in ls_tree(git_dir, rev, recursive=False):
        if kind != "tree" or not RECIPE.match(d):
            continue
        entries = ls_tree(git_dir, f"{rev}:{d.decode()}")
        if not any(p == b"init.yml" and k == "blob" for _, k, _, p in entries):
            continue
        for mode, kind, obj, p in entries:
            if not p.startswith(b"tests/") or (d == name and p in RECIPE_TESTS):
                out.append((mode, kind, obj, d + b"/" + p))
            elif d == name and p == b"tests/smoke":
                out.append(("100644", "empty", "", d + b"/" + p))
    return out


def target_entries(git_dir, rev, names):
    """REC-4, REC-8: tests/target.yml of each recipe in names, from a listing of its tests/ only."""
    return [(mode, kind, obj, n + b"/tests/" + p) for n in names if RECIPE.match(n)
            for mode, kind, obj, p in ls_tree(git_dir, f"{rev}:{n.decode()}/tests", recursive=False)
            if p == b"target.yml" and kind == "blob"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--git-dir", required=True)
    p.add_argument("--rev", required=True)
    where = p.add_mutually_exclusive_group(required=True)
    where.add_argument("--path")
    where.add_argument("--recipe")
    where.add_argument("--targets", nargs="+")
    p.add_argument("--out", required=True)
    a = p.parse_args()
    tree = a.rev if a.path in (".", "") else f"{a.rev}:{a.path}"
    try:
        if a.targets:
            entries = target_entries(a.git_dir, a.rev, [t.encode() for t in a.targets])
        else:
            entries = recipe_entries(a.git_dir, a.rev, a.recipe.encode()) if a.recipe else ls_tree(a.git_dir, tree)
    except subprocess.CalledProcessError:
        entries = []
    if a.targets and len(entries) != len(a.targets):
        print(f"fetch: not every recipe of {' '.join(a.targets)[:200]} has tests/target.yml at {a.rev}")
        return 1
    if not a.targets and not any(a.recipe is None or e[3].startswith(a.recipe.encode() + b"/") for e in entries):
        print(f"fetch: {a.recipe or a.path} is not a directory at {a.rev}")
        return 1
    if len(entries) > MAX_FILES:
        print(f"fetch: tree has more than {MAX_FILES} files")
        return 1
    findings, total = [], 0
    os.makedirs(a.out, exist_ok=True)
    for mode, kind, obj, raw_path in entries:
        rel = raw_path.decode("utf-8", "replace")
        if kind == "commit":
            findings.append(f"tree: submodule {rel}")
            continue
        if mode == "120000":
            findings.append(f"tree: symlink {rel}")
            continue
        parts = raw_path.split(b"/")
        if any(x in (b"", b".", b"..", b".git") for x in parts):
            findings.append(f"tree: unsafe path {rel!r}")
            continue
        size = int(git(a.git_dir, "cat-file", "-s", obj)) if kind == "blob" else 0
        total += size
        if total > MAX_TOTAL:
            print("fetch: tree above 50 MiB")
            return 1
        dest = os.path.join(os.fsencode(a.out), raw_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(git(a.git_dir, "cat-file", "blob", obj) if kind == "blob" else b"")
        os.chmod(dest, 0o755 if mode == "100755" else 0o644)
    if findings:
        print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
