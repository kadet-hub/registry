"""Container images a generator or recipe tree pins by digest (CAT-39a). Standard library only.

Usage: images.py DIR

Prints one reference `<repository>:<tag>@sha256:<digest>` per line, sorted.
pinned_images() takes the {path: (executable, bytes)} of release/tree.py's
read_dir and read_tar, so the release build can list the images of a tar.
"""

import ast
import os
import re
import sys

COMPONENT = r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"
REFERENCE = re.compile(rf"(?:[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+(?::[0-9]+)?/)?{COMPONENT}(?:/{COMPONENT})*"
                       r":[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}@sha256:[0-9a-f]{64}")
IN_TEXT = re.compile(rf"(?<![\w./:@-]){REFERENCE.pattern}(?![\w.-])")
GENERATOR = re.compile(r"ghcr\.io/kadet-hub/[^/]+:")  # REC-6: a generator artifact, no image


def fold(node, names):
    """The value of a str expression made of literals, module constants, + and f-strings, else None."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.Name):
        return names.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = fold(node.left, names), fold(node.right, names)
        return None if left is None or right is None else left + right
    if isinstance(node, ast.JoinedStr):
        parts = [fold(v.value, names) if isinstance(v, ast.FormattedValue) and v.conversion == -1 and v.format_spec is None
                 else fold(v, names) for v in node.values]
        return None if None in parts else "".join(parts)
    return None


def python_strings(source):
    """Every str expression of a module that folds, outermost first; parts of one that does not fold are left out."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    names = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
            value = fold(stmt.value, names)
            if value is not None:
                names[stmt.targets[0].id] = value
    found, stack = [], [tree]
    while stack:
        node = stack.pop()
        value = fold(node, names) if isinstance(node, ast.expr) else None
        if value is not None:
            found.append(value)
        elif not isinstance(node, (ast.BinOp, ast.JoinedStr)):  # "registry/" + name: a fragment, not a reference
            stack.extend(ast.iter_child_nodes(node))
    return found


def pinned_images(files):
    """Sorted references pinned by digest in the files outside tests/; Markdown is documentation, not a pin."""
    found = set()
    for path, (_, data) in files.items():
        parts = path.removeprefix("./").split("/")
        if "tests" in parts[:-1] or path.endswith(".md"):
            continue
        text = data.decode("utf-8", errors="replace")
        if path.endswith(".py"):
            found.update(s for s in python_strings(text) if REFERENCE.fullmatch(s))
        else:
            found.update(m.group() for m in IN_TEXT.finditer(text))
    return sorted(r for r in found if not GENERATOR.match(r))


def main():
    root = sys.argv[1]
    if not os.path.isdir(root):  # a tree that was not written is not a tree without images
        sys.exit(f"images.py: {root}: no directory")
    files = {}
    for top, dirs, names in os.walk(root):
        dirs.sort()
        for name in names:
            with open(os.path.join(top, name), "rb") as f:
                files[os.path.relpath(os.path.join(top, name), root).replace(os.sep, "/")] = (False, f.read())
    for ref in pinned_images(files):
        print(ref)
    return 0


if __name__ == "__main__":
    sys.exit(main())
