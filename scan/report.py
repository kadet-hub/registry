"""Turn scanner output into finding, "review:" and "warning:" lines.

Usage: report.py <tool> <file> [prefix]
Exits 1 when the output holds a finding or cannot be read (GI-7).
"""

import json
import sys
from datetime import datetime, timedelta, timezone


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def gitleaks(path, prefix):
    data = load(path)
    if data is None:
        return ["gitleaks: no result"], True
    return [f"gitleaks: {f['RuleID']}: {f['File'].removeprefix(prefix)}:{f['StartLine']}" for f in data], bool(data)


def semgrep(path, prefix, kind):
    data = load(path)
    if data is None:
        return ["semgrep: no result"], True
    lines, bad = [], False
    for r in data["results"]:
        line = f"semgrep: {r['check_id'].rsplit('.', 1)[-1]}: {r['path'].removeprefix(prefix)}:{r['start']['line']}"
        lines.append(line if kind == "blocking" else "review: " + line)
        bad |= kind == "blocking"
    for e in data["errors"]:
        lines.append(f"semgrep: error: {e.get('type')}: {str(e.get('path', '')).removeprefix(prefix)}")
        bad = True
    return lines, bad


def guarddog(path):
    data = load(path)
    if data is None:
        return ["guarddog: no result"], True
    lines = [f"guarddog: error: {e}" for e in data.get("errors") or {}]
    bad = bool(lines)
    for rule, hits in (data.get("results") or {}).items():
        if not hits:
            continue
        count = len(hits) if isinstance(hits, list) else 1
        if rule.startswith("capability-"):
            lines.append(f"review: guarddog: {rule}: {count}")
        else:
            lines.append(f"guarddog: {rule}: {count}")
            bad = True
    return lines, bad


def clamav_age(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("built: "):
                built = datetime.strptime(line[7:].strip(), "%d %b %Y %H:%M %z")
                if datetime.now(timezone.utc) - built > timedelta(days=2):
                    return [f"warning: ClamAV database built {built:%Y-%m-%d}, older than two days"], False
                return [], False
    return ["warning: ClamAV database age unknown"], False


def main():
    tool, path, *rest = sys.argv[1:]
    prefix = rest[0] if rest else ""
    if tool == "gitleaks":
        lines, bad = gitleaks(path, prefix)
    elif tool in ("semgrep-blocking", "semgrep-review"):
        lines, bad = semgrep(path, prefix, tool.split("-")[1])
    elif tool == "guarddog":
        lines, bad = guarddog(path)
    elif tool == "clamav-age":
        lines, bad = clamav_age(path)
    else:
        sys.exit(f"unknown tool {tool}")
    if lines:
        print("\n".join(lines))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
