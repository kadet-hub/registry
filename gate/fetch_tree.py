"""Write the git tree <rev>:<path> to a directory without git checkout (PUB-1, SEC-5).

Usage: fetch_tree.py --git-dir D --rev SHA --path P --out DIR

Reads objects with `git ls-tree` and `git cat-file`, so no checkout,
attributes, filters, hooks or LFS run. Symlinks and submodules are reported
instead of written; executables keep their mode so SEC-5 sees them.
Exits 1 on a finding or when the tree exceeds its limits.
"""

import argparse
import os
import subprocess
import sys

MAX_FILES = 5000
MAX_TOTAL = 50 * 1024 * 1024


def git(git_dir, *args, data=None):
    return subprocess.run(["git", f"--git-dir={git_dir}", *args], input=data, capture_output=True, check=True).stdout


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--git-dir", required=True)
    p.add_argument("--rev", required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    tree = a.rev if a.path in (".", "") else f"{a.rev}:{a.path}"
    try:
        listing = git(a.git_dir, "ls-tree", "-r", "-z", "--full-tree", tree)
    except subprocess.CalledProcessError:
        print(f"fetch: {a.path} is not a directory at {a.rev}")
        return 1
    entries = [e for e in listing.split(b"\0") if e]
    if len(entries) > MAX_FILES:
        print(f"fetch: tree has more than {MAX_FILES} files")
        return 1
    findings, total = [], 0
    os.makedirs(a.out, exist_ok=True)
    for e in entries:
        meta, raw_path = e.split(b"\t", 1)
        mode, kind, obj = meta.decode().split()
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
        size = int(git(a.git_dir, "cat-file", "-s", obj))
        total += size
        if total > MAX_TOTAL:
            print("fetch: tree above 50 MiB")
            return 1
        dest = os.path.join(os.fsencode(a.out), raw_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(git(a.git_dir, "cat-file", "blob", obj))
        os.chmod(dest, 0o755 if mode == "100755" else 0o644)
    if findings:
        print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
