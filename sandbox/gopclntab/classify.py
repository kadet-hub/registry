"""Compare each sandbox/.trivyignore.yaml entry with what its binary's .gopclntab holds (SEC-18).

Usage: classify.py IGNORE_JSON PCLN_JSON

IGNORE_JSON is the ignore file as JSON, PCLN_JSON the output of pclndump.go
for the binaries the entries name. Affected versions, packages and
functions come from vuln.go.dev. Prints one line per entry and binary;
exits 1 when a statement no longer matches the binary.
"""

import json
import re
import sys
import urllib.error
import urllib.request

VULNDB = "https://vuln.go.dev"
LEVELS = ["none", "package", "functions"]  # what .gopclntab holds of an advisory, least first


def osv(module, fixed, imports):
    return {"affected": [{"package": {"name": module},
                          "ranges": [{"events": [{"introduced": "0"}, {"fixed": fixed}]}],
                          "ecosystem_specific": {"imports": [{"path": p, "symbols": s} for p, s in imports.items()]}}]}


# Advisories without a vuln.go.dev entry: the functions their fix commits change
# and the exported functions that reach them. Used only while vuln.go.dev has none.
NO_REPORT = {
    "CVE-2026-116585": osv("github.com/go-jose/go-jose/v4", "4.1.5",  # fix commit 74114c2, cipher/cbc_hmac.go
                           {"github.com/go-jose/go-jose/v4/cipher": ["unpadBuffer", "cbcAEAD.Open"]}),
    "CVE-2026-116586": osv("github.com/go-jose/go-jose/v4", "4.1.5",  # fix commit a31af25, json/scanner.go
                           {"github.com/go-jose/go-jose/v4/json": ["stateBeginValue", "scanner.pushParseState",
                                                                   "Unmarshal", "Decoder.Decode"]}),
    "CVE-2026-116587": osv("github.com/go-jose/go-jose/v4", "4.1.6",  # fix commit a0111f8, jwk.go
                           {"github.com/go-jose/go-jose/v4": ["rawJSONWebKey.rsaPrivateKey", "JSONWebKey.UnmarshalJSON",
                                                              "ParseSigned", "ParseSignedJSON", "ParseSignedCompact"]}),
}

# "built with Go 1.27.1" and "<module path> v<version>" in a statement.
NAMED = re.compile(r"built with Go (\d+(?:\.\d+)+)|\b((?:[a-z0-9-]+\.)+[a-z]+/\S+?) (v\d+\.\d+\.\d+\S*?)(?=[.,]?(?:\s|$))")


def semver(v):
    """Sort key of a Go or module version: 1.27.0-0 < 1.27.0 < 1.27.1."""
    core, _, pre = v.removeprefix("v").split("+")[0].partition("-")
    nums = [int(x) for x in core.split(".")]
    nums += [0] * (3 - len(nums))
    if not pre:
        return nums, [1]
    return nums, [0, *((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split("."))]


def affected(version, events):
    """Whether version lies in an OSV range given as introduced and fixed events."""
    v, lo = semver(version), None
    for e in events:
        if "introduced" in e:
            lo = semver("0.0.0-0" if e["introduced"] == "0" else e["introduced"])
        elif "fixed" in e and lo is not None:
            if lo <= v < semver(e["fixed"]):
                return True
            lo = None
    return lo is not None and lo <= v


def go_release(version):
    """1.27.1 from the build info's go1.27.1."""
    return re.match(r"go(\d+(?:\.\d+)*)", version).group(1)


def linked(dump, module):
    return go_release(dump["go"]) if module == "stdlib" else dump["modules"].get(module)


def stated(statement):
    """What the statement says .gopclntab holds, read from its sentence with ".gopclntab holds"."""
    for sentence in re.split(r"\.\s+", statement):
        _, found, rest = sentence.partition(".gopclntab holds ")
        if found:
            if rest.startswith(("no ", "nothing ")):
                return "none"
            if re.search(r" without |, not |, none of ", rest):
                return "package"
            return "functions"
    return None


def named(statement):
    """(module, version) pairs the statement names, "stdlib" for the Go release."""
    return [("stdlib", m[1]) if m[1] else (m[2], m[3]) for m in NAMED.finditer(statement)]


def file_pattern(module, pkg):
    if module == "stdlib":
        return re.compile(rf"(?:^|/src/){re.escape(pkg)}/[^/]+\.go$")
    sub = pkg[len(module):].lstrip("/")
    tail = re.escape(sub) + "/" if sub else ""
    return re.compile(rf"(?:^|/)(?:vendor/)?{re.escape(module)}(?:@[^/]+)?/{tail}[^/]+\.go$")


def symbol_pattern(pkg, sym):
    """Function names of sym in pkg: T.M also as (*T).M, generic ones with [...]."""
    p = re.escape(pkg)
    typ, dot, meth = sym.partition(".")
    if dot:
        t = re.escape(typ) + r"(?:\[\.\.\.\])?"
        return re.compile(rf"{p}\.(?:\(\*{t}\)|{t})\.{re.escape(meth)}")
    return re.compile(rf"{p}\.{re.escape(sym)}(?:\[\.\.\.\])?")


def holds(dump, module, version, imp):
    """What .gopclntab holds of one affected package (imp) or, for imp None, module."""
    if imp is None:
        prefix = f"{module}@{version}/"
        dirs = {f.split(prefix, 1)[1].rpartition("/")[0] for f in dump["files"] if prefix in f}
        # Vendored and GOPATH builds record file paths without @version, so function names count too.
        names = [n for n in dump["funcnames"] if n.startswith((module + ".", module + "/"))]
        return (("functions" if dirs or names else "none"),
                f"{module}: {len(dirs)} package dirs, {len(names)} functions, the advisory lists no packages")
    pkg, goos, syms = imp["path"], imp.get("goos"), imp.get("symbols") or []
    names = [n for n in dump["funcnames"] if n.startswith(pkg + ".")]
    files = [f for f in dump["files"] if file_pattern(module, pkg).search(f)]
    # For code of other systems only their source files count; the function names exist on Linux too.
    if goos and "linux" not in goos and not any(re.search(rf"_(?:{'|'.join(goos)})(?:_\w+)?\.go$", f) for f in files):
        return "none", f"{pkg}: no source file for {','.join(goos)}"
    if not syms:
        return ("functions" if names or files else "none"), f"{pkg}: {len(names)} functions, {len(files)} files, the advisory lists no functions"
    hits = []
    for s in syms:
        rx = symbol_pattern(pkg, s)
        matched = [n for n in names if rx.fullmatch(n)]
        if matched:
            hits.append(s if any(n in dump["funcs"] for n in matched) else f"{s} (inlined only)")
    if hits:
        return "functions", f"{pkg}: {len(hits)}/{len(syms)} listed functions [{'; '.join(hits)}]"
    if names or files:
        return "package", f"{pkg}: {len(names)} functions, {len(files)} files, none of the {len(syms)} listed"
    return "none", f"{pkg}: no function, no source file"


def found(dump, reports):
    """What .gopclntab holds of the affected packages and why; None when no affected version is linked."""
    level, why = None, []
    for report in reports:
        for a in report["affected"]:
            module = a["package"]["name"]
            have = linked(dump, module)
            if have is None or not any(affected(have, r["events"]) for r in a["ranges"]):
                continue
            for imp in a.get("ecosystem_specific", {}).get("imports") or [None]:
                lv, w = holds(dump, module, have, imp)
                level = lv if level is None else max(level, lv, key=LEVELS.index)
                why.append(w)
    return level, " | ".join(why)


def check(statement, dump, reports):
    """What .gopclntab holds, what no longer matches the statement, and the evidence."""
    level, why = found(dump, reports)
    problems = []
    if not reports:
        problems.append("no vuln.go.dev entry")
    elif level is None:
        problems.append("the binary links no affected version")
    elif level != stated(statement):
        problems.append(f"the statement says {stated(statement) or 'nothing'}")
    for module, v in named(statement):
        if (have := linked(dump, module)) != v:
            problems.append(f"{'Go' if module == 'stdlib' else module} is {have or 'not linked'}, the statement says {v}")
    return level or "-", problems, why


def fetch(path):
    with urllib.request.urlopen(VULNDB + path, timeout=60) as r:
        return json.load(r)


def entry(go_id):
    """The advisory's vuln.go.dev entry; None when it has none, so its row reports that."""
    try:
        return fetch(f"/ID/{go_id}.json")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        entries = json.load(f)["vulnerabilities"]
    with open(sys.argv[2], encoding="utf-8") as f:
        dumps = json.load(f)
    for d in dumps.values():
        d["funcs"] = set(d["funcs"])
    ids = {}
    for v in fetch("/index/vulns.json"):
        for alias in v.get("aliases") or []:
            ids.setdefault(alias, []).append(v["id"])
    rows, failed = [("binary", "advisory", "go id", "statement", "binary holds", "result")], False
    for e in entries:
        gos = [e["id"]] if e["id"].startswith("GO-") else ids.get(e["id"], [])
        reports = [r for r in map(entry, gos) if r] or [r for r in [NO_REPORT.get(e["id"])] if r]
        for path in e["paths"]:
            b = path.rsplit("/", 1)[-1]
            level, problems, why = check(e["statement"], dumps[b], reports)
            failed = failed or bool(problems)
            rows.append((b, e["id"], ",".join(gos) or "-", stated(e["statement"]) or "-", level,
                         "; ".join(["FAIL: " + p for p in problems]) or f"ok: {why}"))
    widths = [max(len(r[i]) for r in rows) for i in range(5)]
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)), r[5])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
