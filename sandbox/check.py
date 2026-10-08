"""Judge a gVisor strace log and the compile output (SEC-10, SEC-11).

Usage: check.py --log-dir DIR --out DIR --policy FILE --decoys FILE [--allow NAME ...]

Prints every finding; exits 1 if there is any. Only syscall entry lines are
judged, so failed attempts count. Format (gVisor pkg/sentry/strace): paths
are unquoted "0xADDR path", argv is Go %q strings, AT_FDCWD and directory
FDs carry their resolved path. A line that does not parse is a finding.
"""

import argparse
import ast
import base64
import os
import posixpath
import re
import sys

TRACE_CAP = 100 * 1024 * 1024
PYTHON = "/usr/local/bin/python3.13"
PYTHON_CODE = re.compile(
    r"from multiprocessing\.spawn import spawn_main; spawn_main\(tracker_fd=\d+, pipe_handle=\d+\)"
    r"|from multiprocessing\.resource_tracker import main;main\(\d+\)"
)
DECOY_DIRS = ("/home/gate/.aws", "/home/gate/.kube", "/home/gate/.ssh", "/home/gate/.gnupg")
PROC = re.compile(r"/proc/[^/]+/(environ|root|cwd)(/|$)")
WRITABLE = ("/out/", "/tmp/", "/dev/shm/")
WRITE_FLAGS = re.compile(r"\bO_(WRONLY|RDWR|CREAT|TRUNC)\b")
NEVER = ("execveat", "sendmmsg", "symlink", "symlinkat", "io_uring_setup")
LINKS = ("link", "linkat")
OPENS = ("open", "openat", "openat2", "creat")
TRACED = ("execve", "connect", "bind", "sendto", "sendmsg") + OPENS + LINKS + NEVER

NAMES = "|".join(TRACED)
LINE = re.compile(rf"strace\.go:\d+\] \[\s*\d+:\s*\d+\] (\S+) ([EX]) ({NAMES})\((.*)$")
MENTION = re.compile(rf"\b({NAMES})\(")
ADDR = r"0x[0-9a-f]+"
GO_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
OPEN_ARGS = {
    "open": rf"(){ADDR} (.*?), (O_[A-Z_|]+|0x0)",
    "creat": rf"(){ADDR} (.*?), (0o[0-7]+)",
    "openat": rf"(?:AT_FDCWD|{ADDR}) (.*?), {ADDR} (.*?), (O_[A-Z_|]+|0x0)",
    "openat2": rf"(?:AT_FDCWD|{ADDR}) (.*?), {ADDR} (.*?), {ADDR} flags (O_[A-Z_|]+|0x0)",
}
SOCKADDR = re.compile(r"\{Family: (\w+), (?:Addr: ([0-9a-f.:]+), Port: (\d+)|Addr: \"(?:[^\"\\]|\\.)*\")\}")


def parse_policy(path):
    """Lines: <name> <absolute path> <args...>; '*' ends with any args, '!flag' forbids a flag."""
    rules = []
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    for raw in lines:
        fields = raw.split("#", 1)[0].split()
        if fields:
            name, exe, *rest = fields
            rules.append((name, exe, [f for f in rest if not f.startswith("!")],
                          [f[1:] for f in rest if f.startswith("!")]))
    return rules


def parse_argv(text):
    """Parse '["a", "b"], 0x...' into (["a", "b"], ", 0x..."); None if malformed."""
    if not text.startswith("["):
        return None
    out, i = [], 1
    while not text.startswith("]", i):
        if out:
            if not text.startswith(", ", i):
                return None
            i += 2
        m = GO_STRING.match(text, i)
        if not m:
            return None
        try:
            out.append(ast.literal_eval(m.group(0)))
        except (ValueError, SyntaxError):
            return None
        i = m.end()
    return out, text[i + 1:]


def exec_allowed(exe, argv, rules, allow):
    if exe == PYTHON:
        return (len(argv) in (4, 5) and argv[1:3] == ["-B", "-c"] and bool(PYTHON_CODE.fullmatch(argv[3]))
                and argv[4:] in ([], ["--multiprocessing-fork"]))
    args = argv[1:]
    for name, rexe, rargs, forbidden in rules:
        if rexe != exe or name not in allow | {"kapitan-probe"}:
            continue
        if any(a == f or a.startswith(f + "=") for a in args for f in forbidden):
            continue
        if rargs[-1:] == ["*"] and args[: len(rargs) - 1] == rargs[:-1]:
            return True
        if args == rargs:
            return True
    return False


def judge_exec(args, rules, allow):
    m = re.match(rf"{ADDR} (.*?), {ADDR} (\[.*)$", args)
    parsed = parse_argv(m.group(2)) if m else None
    if not parsed or not re.match(rf", {ADDR} \[", parsed[1]):
        return "unparseable"
    exe, argv = m.group(1), parsed[0]
    return None if exec_allowed(exe, argv, rules, allow) else f"exec {exe} {argv}"


def judge_open(call, args):
    m = re.match(OPEN_ARGS[call], args)
    # A second separator means a path contains one: ambiguous.
    if not m or len(re.findall(rf", {ADDR} ", args)) != {"open": 0, "creat": 0, "openat": 1, "openat2": 2}[call]:
        return ["unparseable"]
    base, path, flags = m.group(1) or "/", m.group(2), m.group(3)
    if not base.startswith("/"):
        return ["unparseable"]
    full = posixpath.normpath(posixpath.join(base, path))
    findings = []
    if any(full == d or full.startswith(d + "/") for d in DECOY_DIRS):
        findings.append(f"decoy {full}")
    if PROC.search(full):
        findings.append(f"through {full}")
    if (call == "creat" or WRITE_FLAGS.search(flags)) and not (full == "/dev/null" or full.startswith(WRITABLE)):
        findings.append(f"write outside writable dirs {full}")
    return findings


def judge_link(call, args):
    """Hard links stay on one mount; allow them only inside the writable dirs."""
    pattern = rf"{ADDR} (.*?), {ADDR} (.*?)\)?$" if call == "link" else rf"{ADDR} \S+, {ADDR} (.*?), {ADDR}, {ADDR} (.*?), {ADDR}\)?$"
    m = re.match(pattern, args)
    if not m or len(re.findall(rf", {ADDR} ", args)) != (1 if call == "link" else 2):
        return "unparseable"
    paths = [posixpath.normpath(p) for p in m.groups()]
    return None if all(p.startswith(WRITABLE) for p in paths) else f"link {paths}"


def judge_socket(call, args):
    if call == "sendmsg":
        m = re.search(r"\{name=(0x[0-9a-f]+), namelen=(\d+),", args)
        if not m:
            return "unparseable"
        return "internet destination" if m.group(1) != "0x0" and m.group(2) in ("16", "28") else None
    addrs = list(SOCKADDR.finditer(args))
    if not addrs:
        return None if call == "sendto" and re.search(r", null, 0x[0-9a-f]+$", args.rstrip(")")) else "unparseable address"
    for a in addrs:
        family, ip, port = a.groups()
        if family == "AF_UNIX":
            continue
        if call == "bind" and family in ("AF_INET", "AF_INET6") and ip in ("127.0.0.1", "::1") and port == "0":
            continue
        return f"{family} {ip}:{port}"
    return None


def judge(call, args, rules, allow):
    """Findings for one traced syscall entry."""
    if call in NEVER:
        why = ["not allowed"]
    elif call == "execve":
        why = [judge_exec(args, rules, allow)]
    elif call in OPENS:
        why = judge_open(call, args)
    elif call in LINKS:
        why = [judge_link(call, args)]
    else:
        why = [judge_socket(call, args)]
    # Exec lines carry the environment, so only the judged part is printed.
    return [f"{call}: {w[:300]}" + ("" if call == "execve" else f": {args[:200]}") for w in why if w]


def check_trace(log_dir, rules, allow):
    files = [os.path.join(log_dir, f) for f in sorted(os.listdir(log_dir))]
    if not files:
        return ["trace: no log written"]
    if sum(os.path.getsize(f) for f in files) > TRACE_CAP:
        return ["trace: log above size cap"]
    findings = []
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as lines:
            for line in lines:
                line = line.rstrip("\n")
                m = LINE.search(line)
                if m and m.group(2) == "E":
                    findings += judge(m.group(3), m.group(4), rules, allow)
                elif not m and "strace.go" in line and MENTION.search(line):
                    findings.append(f"trace: unparseable line: {line[:300]}")
    return sorted(set(findings))


def encodings(value):
    raw = value.encode()
    yield from (raw, raw.hex().encode(), raw.hex().upper().encode())
    for pad in range(3):
        for enc in (base64.b64encode, base64.urlsafe_b64encode):
            b = enc(b"\0" * pad + raw)
            # Drop the characters that depend on neighbouring bytes.
            yield b[(pad * 4 + 2) // 3: len(b) - 4]


def check_output(out_dir, values):
    findings = []
    for root, _, names in os.walk(out_dir):
        for n in names:
            path = os.path.join(root, n)
            with open(path, "rb") as fh:
                data = fh.read()
            if any(e in data for v in values for e in encodings(v)):
                findings.append(f"output: decoy value in {os.path.relpath(path, out_dir)}")
    return sorted(findings)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--log-dir", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--policy", required=True)
    p.add_argument("--decoys", required=True, help="file with one decoy value per line")
    p.add_argument("--allow", action="append", default=[], help="declared binary, e.g. helm-template")
    a = p.parse_args()
    with open(a.decoys, encoding="utf-8") as f:
        values = f.read().split()
    findings = check_trace(a.log_dir, parse_policy(a.policy), set(a.allow)) + check_output(a.out, values)
    if findings:
        print("\n".join(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
