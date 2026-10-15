"""Fixture output diff against the approved version (SEC-13, PUB-9).

Usage: output_diff.py --old DIR --new DIR --compile-log FILE --full FILE [--max-bytes N] [--json FILE]

Prints the size in files and hunks and the first lines of the diff, files
with a SEC-12 match in --compile-log first; writes the whole diff to --full,
cut after the last whole line within --max-bytes with a closing line that
names the cut. --json receives files, hunks and the sha256 of --full.
Standard library only; the outputs are read as data.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import sys

REPORT_LINES = 150
LINE_WIDTH = 200
SEC12 = re.compile(r"^SEC-12: (?:declared )?[a-z-]+: (\S+): ")


def files(root):
    out = {}
    for dirpath, _, names in os.walk(root):
        for n in names:
            path = os.path.join(dirpath, n)
            if os.path.isfile(path) and not os.path.islink(path):
                out[os.path.relpath(path, root)] = path
    return out


def read(path):
    if path is None:
        return []
    with open(path, "rb") as f:
        data = f.read()
    try:
        return data.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return [f"<binary, {len(data)} bytes>\n"]


def diff(old, new, flagged):
    a, b = files(old), files(new)
    sections = []
    for rel in sorted(set(a) | set(b), key=lambda r: (r not in flagged, r)):
        lines = list(difflib.unified_diff(read(a.get(rel)), read(b.get(rel)), f"a/{rel}", f"b/{rel}"))
        if lines:
            sections.append((rel, [ln if ln.endswith("\n") else ln + "\n" for ln in lines]))
    return sections


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--old", required=True)
    p.add_argument("--new", required=True)
    p.add_argument("--compile-log", required=True)
    p.add_argument("--full", required=True)
    p.add_argument("--max-bytes", type=int)
    p.add_argument("--json")
    a = p.parse_args()
    with open(a.compile_log, encoding="utf-8", errors="replace") as f:
        flagged = {m.group(1) for line in f if (m := SEC12.match(line))}
    sections = diff(a.old, a.new, flagged)
    text = [ln for _, lines in sections for ln in lines]
    hunks = sum(ln.startswith("@@") for ln in text)
    data = "".join(text).encode()
    if a.max_bytes is not None and len(data) > a.max_bytes:
        mark = b"... output diff truncated at %d bytes\n" % a.max_bytes
        keep = data[:a.max_bytes - len(mark)]
        data = keep[:keep.rfind(b"\n") + 1] + mark
    with open(a.full, "wb") as f:
        f.write(data)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"files": len(sections), "hunks": hunks, "sha256": hashlib.sha256(data).hexdigest()}, f)
    print(f"SEC-13: output diff against the approved version: {len(sections)} files, {hunks} hunks"
          + (f"; SEC-12 matches first: {', '.join(sorted(flagged & {r for r, _ in sections}))}" if flagged else ""))
    for ln in text[:REPORT_LINES]:
        ln = ln.rstrip("\n")
        print(ln if len(ln) <= LINE_WIDTH else ln[:LINE_WIDTH] + " [cut]")
    if len(text) > REPORT_LINES:
        print(f"... {len(text) - REPORT_LINES} more lines in output.diff in the gate-report artifact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
