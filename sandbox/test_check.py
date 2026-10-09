import base64
import os
import tempfile
import unittest

import check

POLICY = check.parse_policy(os.path.join(os.path.dirname(__file__), "..", "policy", "binaries.txt"))
PREFIX = "I1008 12:00:00.000000       1 strace.go:567] [   2:   2] "
ENV = '0x7f00 ["HOME=/home/gate"]'


def trace(*lines, allow=()):
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "runsc.log.boot"), "w") as f:
            f.write("".join(PREFIX + line + "\n" for line in lines))
        return check.check_trace(d, POLICY, set(allow))


def execve(path, argv, comm="python3.13"):
    quoted = ", ".join('"' + a.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"' for a in argv)
    return f"{comm} E execve(0x7f01 {path}, 0x7f02 [{quoted}], {ENV})"


class Exec(unittest.TestCase):
    def test_kapitan_baseline_passes(self):
        self.assertEqual(trace(
            execve("/usr/local/sbin/git", ["git", "version"]),
            execve("/usr/bin/uname", ["uname", "-p"]),
            execve("/usr/local/bin/python3.13", ["/usr/local/bin/python3.13", "-B", "-c",
                   "from multiprocessing.spawn import spawn_main; spawn_main(tracker_fd=6, pipe_handle=12)",
                   "--multiprocessing-fork"], comm="kapitan"),
            execve("/usr/local/bin/python3.13", ["/usr/local/bin/python3.13", "-B", "-c",
                   "from multiprocessing.resource_tracker import main;main(5)"], comm="kapitan"),
        ), [])

    def test_krab_python_only_for_krab_and_its_runner(self):
        lines = [execve(check.KRAB_PYTHON, [check.KRAB_PYTHON, *argv], comm="krab") for argv in check.KRAB_PROBES]
        lines.append(execve(check.KRAB_PYTHON, [check.KRAB_PYTHON, "/tmp/xdg/cache/krab/kadet-runner/cf897a5b4b08724c/kadet_runner.py"], comm="krab"))
        self.assertEqual(trace(*lines, allow=["krab-kadet"]), [])
        self.assertEqual(len(trace(*lines)), 3)
        for argv in (["-c", "import os"], ["/tmp/x.py"], ["/tmp/xdg/cache/krab/kadet-runner/cf897a5b4b08724c/kadet_runner.py", "-x"]):
            self.assertTrue(trace(execve(check.KRAB_PYTHON, [check.KRAB_PYTHON, *argv]), allow=["krab-kadet"]), argv)

    def test_python_with_other_code_fails(self):
        self.assertTrue(trace(execve("/usr/local/bin/python3.13", ["python3", "-c", "import os"])))

    def test_declared_binary(self):
        line = execve("/usr/local/bin/helm", ["helm", "template", "x", "/chart"])
        self.assertEqual(trace(line, allow=["helm-template"]), [])
        self.assertTrue(trace(line))

    def test_forbidden_flag_after_long_padding(self):
        line = execve("/usr/local/bin/helm", ["helm", "template", "x", "--set", "a=" + "p" * 5000,
                                              "--post-renderer=/tmp/x"])
        self.assertTrue(trace(line, allow=["helm-template"]))

    def test_symlink_path_and_execveat_fail(self):
        self.assertTrue(trace(execve("/tmp/h", ["helm", "version"]), allow=["helm-version"]))
        self.assertTrue(trace('python3.13 E execveat(0x3 /usr/local/bin, 0x7f helm, 0x7f ["helm"], ' + ENV + ", 0x0)"))

    def test_escaped_quotes_in_argv_cannot_forge_allowed_args(self):
        self.assertTrue(trace(execve("/usr/bin/uname", ["uname", '-p"], 0x1 ["x'])))

    def test_path_with_separator_fails(self):
        self.assertTrue(trace('python3.13 E execve(0x7f01 /tmp/a, 0x1 ["git", "version"], 0x7f02 ["git", "version"], ' + ENV + ")"))

    def test_unparseable_line_fails(self):
        self.assertTrue(trace("python3.13 E execve(0x7f01 /usr/bin/uname"))
        self.assertTrue(trace("odd name E execve(0x7f01 /usr/bin/uname, 0x7f02 [\"uname\", \"-p\"], " + ENV + ")"))


class Open(unittest.TestCase):
    def test_relative_decoy_after_chdir_fails(self):
        self.assertTrue(trace("python3.13 E openat(AT_FDCWD /home/gate/.aws, 0x7f01 credentials, O_RDONLY|O_CLOEXEC, 0o0)"))

    def test_proc_environ_and_root_fail(self):
        self.assertTrue(trace("python3.13 E openat(AT_FDCWD /, 0x7f01 /proc/1/environ, O_RDONLY|O_CLOEXEC, 0o0)"))
        self.assertTrue(trace("python3.13 E open(0x7f01 /proc/self/root/home/gate/.ssh/id_ed25519, O_RDONLY, 0o0)"))

    def test_write_outside_writable_dirs_fails(self):
        self.assertTrue(trace("python3.13 E openat(AT_FDCWD /project, 0x7f01 x.txt, O_WRONLY|O_CREAT|O_TRUNC, 0o644)"))
        self.assertEqual(trace("python3.13 E openat(AT_FDCWD /project, 0x7f01 /out/a/x.yml, O_WRONLY|O_CREAT|O_TRUNC, 0o644)",
                               "python3.13 E openat(AT_FDCWD /project, 0x7f01 /dev/null, O_RDWR|O_CLOEXEC, 0o0)",
                               "python3.13 E openat(AT_FDCWD /project, 0x7f01 inventory/targets/a.yml, O_RDONLY|O_CLOEXEC, 0o0)"), [])

    def test_ambiguous_path_fails(self):
        self.assertTrue(trace("python3.13 E openat(AT_FDCWD /tmp/a, 0x1 b, 0x7f01 c, O_RDONLY, 0o0)"))


class Network(unittest.TestCase):
    def test_kapitan_ipv6_probe_passes(self):
        self.assertEqual(trace("kapitan E bind(0x3 socket:[1], 0x7f01 {Family: AF_INET6, Addr: ::1, Port: 0}, 0x1c)"), [])

    def test_internet_connect_sendto_sendmsg_fail(self):
        self.assertTrue(trace("python E connect(0x3 socket:[1], 0x7f01 {Family: AF_INET, Addr: 203.0.113.1, Port: 443}, 0x10)"))
        self.assertTrue(trace("python E sendto(0x3 socket:[2], 0x7f01, 0x1, 0x0, 0x7f02 {Family: AF_INET, Addr: 203.0.113.1, Port: 53}, 0x10)"))
        self.assertTrue(trace("python E sendmsg(0x3 socket:[3], 0x7f01 {name=0x7f02, namelen=16, iovecs=0x7f03 {base=0x7f04, len=1, \"x\"}, control={0x0 }, flags=0}, 0x0)"))
        self.assertTrue(trace("python E bind(0x3 socket:[1], 0x7f01 {Family: AF_INET, Addr: 0.0.0.0, Port: 8080}, 0x10)"))

    def test_unix_and_connected_sends_pass(self):
        self.assertEqual(trace(
            'python E connect(0x3 socket:[1], 0x7f01 {Family: AF_UNIX, Addr: "/tmp/s"}, 0x10)',
            "python E sendto(0x3 socket:[2], 0x7f01, 0x1, 0x0, null, 0x0)",
            "python E sendmsg(0x3 socket:[3], 0x7f01 {name=0x0, namelen=0, iovecs=0x7f03 {base=0x7f04, len=1, \"x\"}, control={0x0 }, flags=0}, 0x0)",
        ), [])

    def test_forged_unix_address_in_fd_name_fails(self):
        self.assertTrue(trace('python E connect(0x3 /tmp/{Family: AF_UNIX, Addr: "x"}, 0x7f01 {Family: AF_INET, Addr: 203.0.113.1, Port: 443}, 0x10)'))

    def test_hard_links(self):
        self.assertEqual(trace("python E link(0x7f01 /dev/shm/sem.4WBUdR, 0x7f02 /dev/shm/sem.mp-43_hqkjo)"), [])
        self.assertTrue(trace("python E link(0x7f01 /home/gate/.aws/credentials, 0x7f02 /tmp/c)"))
        self.assertTrue(trace("python E linkat(0x3 /home/gate/.aws, 0x7f01 credentials, 0x4, 0x7f02 /tmp/c, 0x0)"))

    def test_never_allowed(self):
        for line in ("python E symlink(0x7f01 /usr/local/bin/helm, 0x7f02 /tmp/h)",
                     "python E sendmmsg(0x3 socket:[1], 0x7f01, 0x1, 0x0)",
                     "python E io_uring_setup(0x8, 0x7f01)"):
            self.assertTrue(trace(line), line)


class Output(unittest.TestCase):
    def test_decoy_in_any_encoding_is_found(self):
        value = "decoy-4f1c2a9b7e"
        for data in (value, value.encode().hex(), "x" + base64.b64encode(b"ab" + value.encode() + b"z").decode()):
            with tempfile.TemporaryDirectory() as d:
                os.makedirs(os.path.join(d, "t"))
                with open(os.path.join(d, "t", "cm.yml"), "w") as f:
                    f.write("data: " + data)
                self.assertEqual(check.check_output(d, [value]), ["output: decoy value in t/cm.yml"], data)

    def test_clean_output_passes(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "a.yml"), "w") as f:
                f.write("ok: true")
            self.assertEqual(check.check_output(d, ["decoy-4f1c2a9b7e"]), [])


if __name__ == "__main__":
    unittest.main()
