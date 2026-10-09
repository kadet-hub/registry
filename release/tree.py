"""Normalized artifact tar and git tree IDs (PUB-1). Standard library only.

Usage: tree.py TAR   prints the git tree ID of the tar's contents.

The tar holds regular files only, sorted, mode 0644, mtime 0, owner 0. The
tree ID is computed the way git hashes a tree, so the sign job compares it
with `git rev-parse <sha>:<path>` of its own fetch.
"""

import hashlib
import io
import os
import sys
import tarfile


def _hash(kind, data):
    return hashlib.sha1(b"%s %d\0" % (kind, len(data)) + data).digest()


def tree_id(files):
    """files: {relative path: (executable, bytes)} -> hex git tree ID."""
    root = {}
    for rel, (exe, data) in files.items():
        node = root
        *dirs, name = rel.split("/")
        for d in dirs:
            node = node.setdefault(d, {})
        node[name] = (b"100755" if exe else b"100644", _hash(b"blob", data))

    def write(node):
        def key(item):
            name, value = item
            return name + "/" if isinstance(value, dict) else name
        body = b""
        for name, value in sorted(node.items(), key=key):
            mode, oid = (b"40000", write(value)) if isinstance(value, dict) else value
            body += mode + b" " + name.encode() + b"\0" + oid
        return _hash(b"tree", body)

    return write(root).hex()


def read_dir(path):
    files = {}
    for root, dirs, names in os.walk(path):
        dirs.sort()
        for name in names:
            full = os.path.join(root, name)
            with open(full, "rb") as f:
                files[os.path.relpath(full, path).replace(os.sep, "/")] = (bool(os.stat(full).st_mode & 0o111), f.read())
    return files


def write_tar(files, out):
    with tarfile.open(out, "w", format=tarfile.PAX_FORMAT) as tar:
        for rel in sorted(files):
            data = files[rel][1]
            info = tarfile.TarInfo(rel)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tar.addfile(info, io.BytesIO(data))


def read_tar(path):
    files = {}
    with tarfile.open(path) as tar:
        for m in tar.getmembers():
            if not m.isreg():
                raise ValueError(f"not a regular file in the tar: {m.name!r}")
            files[m.name] = (bool(m.mode & 0o111), tar.extractfile(m).read())
    return files


if __name__ == "__main__":
    print(tree_id(read_tar(sys.argv[1])))
