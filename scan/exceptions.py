"""Apply an entry's exceptions to a static scan report (SEC-14).

Usage: exceptions.py --tree DIR --exceptions FILE --report FILE --rc N

FILE holds the entry's exceptions as JSON, [{"rule", "path", "sha256"}].
Prints the report with excepted findings as "excepted:" lines first; exits
1 if a finding remains, or if static-scan failed (N > 0) without any finding.
"""

import argparse
import hashlib
import json
import os
import re
import sys

PATH = r"(?P<path>[A-Za-z0-9._/-]+)"
FORMATS = [
    (re.compile(rf"gitleaks: (?P<rule>[A-Za-z0-9._-]+): {PATH}:\d+$"), "gitleaks:{rule}"),
    (re.compile(rf"semgrep: (?P<rule>[A-Za-z0-9._-]+): {PATH}:\d+$"), "semgrep:{rule}"),
    (re.compile(rf"imports: {PATH}(:\d+)?: "), "imports"),
    (re.compile(rf"template: {PATH}: "), "template"),
    (re.compile(rf"ruff: {PATH}:\d+:\d+: (?P<rule>[A-Z]+[0-9]+) "), "ruff:{rule}"),
    (re.compile(rf"tree: executable {PATH}$"), "tree:executable"),
    (re.compile(rf"tree: banned file {PATH}$"), "tree:banned"),
    (re.compile(rf"tree: {PATH} above 1 MiB$"), "tree:large"),
]


def key(line):
    for pattern, rule in FORMATS:
        m = pattern.match(line)
        if m and m.group("rule" if "{rule}" in rule else "path") != "error":
            return rule.format(**m.groupdict()), m.group("path")
    return None


def digest(tree, path):
    if path.startswith("/") or ".." in path.split("/"):
        return None
    full = os.path.join(tree, path)
    real = os.path.realpath(full)
    if os.path.islink(full) or not os.path.isfile(full) or not real.startswith(os.path.realpath(tree) + os.sep):
        return None
    with open(full, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def apply(lines, tree, exceptions, rc):
    excepted, rest, used, findings = [], [], set(), 0
    for line in lines:
        if not line.strip() or line.startswith(("review: ", "warning: ")):
            rest.append(line)
            continue
        k = key(line)
        match = [i for i, e in enumerate(exceptions) if k and (e["rule"], e["path"]) == k]
        if match:
            used.add(match[0])
            if digest(tree, k[1]) == exceptions[match[0]]["sha256"]:
                excepted.append(f"excepted: {line} (SEC-14)")
                continue
            line += f" (SEC-14: the exception lapsed, {k[1]} changed)"
        rest.append(line)
        findings += 1
    rest += [f"warning: exception {e['rule']} {e['path']} matched no finding"
             for i, e in enumerate(exceptions) if i not in used]
    failed = findings > 0 or (rc != 0 and not excepted)
    return excepted + rest, failed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tree", required=True)
    p.add_argument("--exceptions", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--rc", type=int, required=True)
    a = p.parse_args()
    with open(a.exceptions, encoding="utf-8") as f:
        exceptions = json.load(f) or []
    with open(a.report, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    out, failed = apply(lines, a.tree, exceptions, a.rc)
    print("\n".join(out))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
