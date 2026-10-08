# Hostile probes for AC-4 / SEC-10: each swallows its error, so only the
# gVisor trace can show it happened.
import _posixsubprocess
import os
import shutil
import socket
import subprocess

TARGET = "203.0.113.1"  # RFC 5737, unroutable

for attempt in (
    lambda: socket.create_connection((TARGET, 443), timeout=1),
    lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b"x", (TARGET, 53)),
    lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendmsg([b"x"], [], 0, (TARGET, 53)),
):
    try:
        attempt()
    except OSError as e:
        print("network probe failed as expected:", e)

# Process start that bypasses subprocess.Popen and its audit event.
argv = [b"/usr/bin/id"]
pid = _posixsubprocess.fork_exec(
    argv, argv, True, (), None, None,
    -1, -1, -1, -1, -1, -1, *os.pipe(), False, False,
    -1, None, None, None, -1, None, False,
)
os.waitpid(pid, 0)

# Executable dropped on a writable mount must not run (noexec).
shutil.copy("/usr/bin/id", "/tmp/x")
os.chmod("/tmp/x", 0o755)
try:
    subprocess.run(["/tmp/x"], check=True)
    raise SystemExit("UNEXPECTED: /tmp/x ran")
except OSError as e:
    print("exec from /tmp blocked as expected:", e)
