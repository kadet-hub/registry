"""Turn rescan findings into one issue per generator and rule (SEC-15, SEC-16).

Usage: rescan_issues.py FINDINGS RUN_URL

FINDINGS has lines "<kind>\t<name>\t<version or tag>\t<text>" from
scan/rescan. Prints a JSON list of {"title", "body"}; standard library only.
"""

import json
import re
import sys

WITH_RULE_ID = ("gitleaks", "semgrep", "guarddog")


def rule(text):
    tool, _, rest = text.partition(": ")
    return f"{tool}: {rest.partition(': ')[0]}" if tool in WITH_RULE_ID else tool


def clean(text):
    return re.sub(r"[^\x09\x0a\x20-\x7e]", "?", text)


def issues(rows, run_url):
    groups = {}
    for kind, name, ref, text in rows:
        if kind == "drift":
            title = f"tag drift: {name} {ref}"
        else:
            title = f"rescan: {name} {ref}: {rule(text)}"
        title = re.sub(r"[^A-Za-z0-9._:/ -]", "?", title)[:200]
        groups.setdefault(title, []).append(clean(text))
    out = []
    for title, lines in groups.items():
        report = "\n".join(lines)[-60000:]
        fence = "`" * max(3, 1 + max((len(m) for m in re.findall(r"`+", report)), default=0))
        what = "SEC-16" if title.startswith("tag drift: ") else "SEC-15"
        body = (f"The daily rescan ({run_url}) reports ({what}):\n\n{fence}\n{report}\n{fence}\n\n"
                "A finding does not yank the version; confirm it and follow INC-1.")
        out.append({"title": title, "body": body})
    return out


def main():
    with open(sys.argv[1], encoding="utf-8", errors="replace") as f:
        rows = [ln.rstrip("\n").split("\t", 3) for ln in f if ln.count("\t") >= 3]
    json.dump(issues(rows, sys.argv[2]), sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
