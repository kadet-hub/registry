"""Unpack fetched files into a dependency's output_path (CON-1).

Usage: unpack.py SRC DEST

Each file in SRC that is a tar or zip archive is extracted into DEST, as
Kapitan does for OCI layers and `unpack: true`; any other file is copied.
Members must stay inside DEST, be regular files or directories, and add up
to at most MAX_TOTAL bytes per archive (CON-1c).
"""

import os
import shutil
import sys
import tarfile
import zipfile

MAX_TOTAL = 500 * 1024 * 1024


def check_total(name, total):
    if total > MAX_TOTAL:
        raise ValueError(f"{name}: members add up to more than {MAX_TOTAL} bytes")


def unpack(src, dest):
    os.makedirs(dest, exist_ok=True)
    for name in sorted(os.listdir(src)):
        path = os.path.join(src, name)
        if tarfile.is_tarfile(path):
            with tarfile.open(path) as t:
                for m in t.getmembers():
                    if not (m.isfile() or m.isdir()):
                        raise ValueError(f"{name}: {m.name} is not a regular file")
                check_total(name, sum(m.size for m in t.getmembers()))
                t.extractall(dest, filter="data")
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                for m in z.namelist():
                    target = os.path.realpath(os.path.join(dest, m))
                    if not target.startswith(os.path.realpath(dest) + os.sep):
                        raise ValueError(f"{name}: {m} leaves the output path")
                # zipfile stops each member at its declared file_size and fails its CRC check beyond it.
                check_total(name, sum(i.file_size for i in z.infolist()))
                z.extractall(dest)
        else:
            shutil.copyfile(path, os.path.join(dest, name))


if __name__ == "__main__":
    try:
        unpack(sys.argv[1], sys.argv[2])
    except (ValueError, tarfile.TarError, zipfile.BadZipFile) as e:
        print(f"CON-1: unpack: {e}")
        sys.exit(1)
