"""Compile diff of a pull request (CD-3, CD-7, CD-9).

Usage:
  compile_diff.py diff BASE HEAD OUT GLOB
  compile_diff.py render DIR CONCLUSION HEAD_SHA RUN_URL

diff compares the compiled/ directories BASE and HEAD and writes
OUT/<target>.diff for every target whose name matches GLOB and whose files
differ. render prints the pull request comment for the diffs in DIR, which
come from an artifact of a run the pull request controls and are treated as
untrusted text.
"""

import difflib
import fnmatch
import os
import re
import sys

MARKER = "<!-- kadet-hub-compile-diff -->"
LIMIT = 65536  # characters per GitHub comment
MAX_READ = 1024 * 1024
MIN_SHARE = 300


def files(root):
    """Relative path to full path of every file and symlink below root."""
    out = {}
    for d, dirs, names in os.walk(root):  # does not descend into symlinked directories
        for n in names + [x for x in dirs if os.path.islink(os.path.join(d, x))]:
            path = os.path.join(d, n)
            out[os.path.relpath(path, root)] = path
    return out


def content(path):
    if path is None:
        return None
    if os.path.islink(path):
        return b"symlink to " + os.fsencode(os.readlink(path)) + b"\n"
    with open(path, "rb") as f:
        return f.read()


def text_lines(data):
    """Lines with their newline, [] for a missing file, None for binary data."""
    if data is None:
        return []
    if b"\0" in data:
        return None
    try:
        parts = data.decode("utf-8").split("\n")
    except UnicodeDecodeError:
        return None
    return [p + "\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def file_diff(name, old, new):
    """Diff lines of one file below compiled/, [] when both sides are equal."""
    if old == new:
        return []
    a, b = text_lines(old), text_lines(new)
    src = f"a/{name}" if old is not None else "/dev/null"
    dst = f"b/{name}" if new is not None else "/dev/null"
    out = [f"diff --git a/{name} b/{name}\n", f"--- {src}\n", f"+++ {dst}\n"]
    if a is None or b is None:
        return out + ["Binary files differ\n"]
    for line in list(difflib.unified_diff(a, b))[2:]:
        out.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
    return out


def diff(base, head, out, glob):
    """Write OUT/<target>.diff per changed target; return the number written."""
    os.makedirs(out, exist_ok=True)
    targets = set()
    for root in (base, head):
        if os.path.isdir(root):
            targets.update(e.name for e in os.scandir(root) if e.is_dir(follow_symlinks=False))
    written = 0
    for target in sorted(t for t in targets if fnmatch.fnmatchcase(t, glob)):
        a, b = files(os.path.join(base, target)), files(os.path.join(head, target))
        lines = []
        for rel in sorted(a.keys() | b.keys()):
            lines += file_diff(f"{target}/{rel}", content(a.get(rel)), content(b.get(rel)))
        if lines:
            with open(os.path.join(out, target + ".diff"), "w", encoding="utf-8") as f:
                f.writelines(lines)
            written += 1
    return written


def safe(s):
    """Printable ASCII, tab and newline; everything else becomes ? (CD-7)."""
    return re.sub(r"[^\t\n\x20-\x7e]", "?", s)


def fence(s):
    return "`" * max(3, 1 + max((len(m) for m in re.findall(r"`+", s)), default=0))


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def file_list(diff_text):
    """A, D or M and the path of every file in one target's diff."""
    out = []
    lines = diff_text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("diff --git a/"):
            rest = line[len("diff --git a/"):]
            name = rest[: max(0, len(rest) - 3) // 2]  # rest is "<name> b/<name>"
            status = "A" if lines[i + 1:i + 2] == ["--- /dev/null"] else "D" if lines[i + 2:i + 3] == ["+++ /dev/null"] else "M"
            out.append(f"{status} {name}")
    return out


def read_diffs(d):
    """(target, diff text) of every regular file <target>.diff in d."""
    out = []
    if not os.path.isdir(d):
        return out
    for e in sorted(os.scandir(d), key=lambda e: e.name):
        if e.name.endswith(".diff") and e.is_file(follow_symlinks=False):
            with open(e.path, "rb") as f:
                data = f.read(MAX_READ)
            target = re.sub(r"[^A-Za-z0-9._-]", "?", e.name[: -len(".diff")])
            out.append((target, safe(data.decode("utf-8", "replace"))))
    return out


def block(target, files_, diff_text, share):
    """The <details> block of one target, cut to at most share characters if it can be."""
    lines = files_ + [""] + diff_text.rstrip("\n").split("\n")

    def build(n):
        shown = "\n".join(lines[:n])
        note = "" if n == len(lines) else f"\nCut after {n} of {len(lines)} lines; the artifact holds the full diff.\n"
        f = fence(shown)
        return (f"\n<details><summary>{target}: {plural(len(files_), 'file')}</summary>\n\n"
                f"{f}diff\n{shown}\n{f}\n{note}\n</details>\n")

    lo, hi = 0, len(lines)  # the longest prefix that fits; length grows with n
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(build(mid)) <= share:
            lo = mid
        else:
            hi = mid - 1
    return build(lo)


def render(d, conclusion, sha, run_url):
    sha = re.sub(r"[^0-9a-f]", "", sha)[:7]
    run = f"[run]({run_url})" if re.fullmatch(r"https://[A-Za-z0-9._/-]+", run_url) else "run"
    if conclusion != "success":
        return f"{MARKER}\n**compile diff: no result** at `{sha}`: the compile {run} ended with {safe(conclusion)}.\n"
    diffs = [(t, text, file_list(text)) for t, text in read_diffs(d)]
    if not diffs:
        return f"{MARKER}\n**compile diff: no change** in `compiled/` at `{sha}` ({run}).\n"
    nfiles = sum(len(f) for _, _, f in diffs)
    head = (f"{MARKER}\n**compile diff: {plural(len(diffs), 'target')} changed, {plural(nfiles, 'file')}** "
            f"at `{sha}`. Full diff: artifact `compile-diff` of the {run}.\n")
    budget = LIMIT - len(head) - 100  # room for the line about targets left out
    blocks = {}
    # Smallest first: what a small target does not use goes to the larger ones.
    for k, i in enumerate(sorted(range(len(diffs)), key=lambda i: len(diffs[i][1]))):
        share = budget // (len(diffs) - k)
        if share < MIN_SHARE:
            break
        target, text, files_ = diffs[i]
        blocks[i] = block(target, files_, text, share)
        budget -= len(blocks[i])
    body = head + "".join(blocks[i] for i in sorted(blocks))
    if len(blocks) < len(diffs):
        body += f"\n{plural(len(diffs) - len(blocks), 'more target')} changed; see the artifact.\n"
    if len(body) > LIMIT:  # only a block whose skeleton exceeds its share gets here
        body = head + "\nThe diff does not fit into a comment; see the artifact.\n"
    return body


def main(argv):
    if len(argv) == 6 and argv[1] == "diff":
        print(f"compile diff: {plural(diff(*argv[2:]), 'target')} changed")
    elif len(argv) == 6 and argv[1] == "render":
        sys.stdout.write(render(*argv[2:]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
