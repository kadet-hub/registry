"""Unpack fetched files into a dependency's output_path (CON-1).

Usage: unpack.py SRC DEST

Each file in SRC that is a tar or zip archive is extracted into DEST, as
Kapitan does for OCI layers and `unpack: true`; any other file is copied.
Members must stay inside DEST and be regular files or directories.
"""

import os
import shutil
import sys
import tarfile
import zipfile


def unpack(src, dest):
    os.makedirs(dest, exist_ok=True)
    for name in sorted(os.listdir(src)):
        path = os.path.join(src, name)
        if tarfile.is_tarfile(path):
            with tarfile.open(path) as t:
                for m in t.getmembers():
                    if not (m.isfile() or m.isdir()):
                        raise ValueError(f"{name}: {m.name} is not a regular file")
                t.extractall(dest, filter="data")
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                for m in z.namelist():
                    target = os.path.realpath(os.path.join(dest, m))
                    if not target.startswith(os.path.realpath(dest) + os.sep):
                        raise ValueError(f"{name}: {m} leaves the output path")
                z.extractall(dest)
        else:
            shutil.copyfile(path, os.path.join(dest, name))


if __name__ == "__main__":
    try:
        unpack(sys.argv[1], sys.argv[2])
    except (ValueError, tarfile.TarError, zipfile.BadZipFile) as e:
        print(f"CON-1: unpack: {e}")
        sys.exit(1)
