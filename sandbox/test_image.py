"""SEC-17 on the image itself; run inside the sandbox image (selftest.yml)."""

import importlib.util
import os
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402

KRAB_PYTHON = os.environ.get("KRAB_PYTHON", "")


@unittest.skipUnless(KRAB_PYTHON == check.KRAB_PYTHON, "runs in the sandbox image")
class Image(unittest.TestCase):
    def test_no_shell(self):
        found = [n for n in ("sh", "bash", "dash", "busybox") if shutil.which(n)]
        self.assertEqual(found + [p for p in ("/bin/sh", "/usr/bin/sh") if os.path.lexists(p)], [])

    def test_no_installer_or_package_manager(self):
        found = [n for n in ("pip", "pip3", "uv", "apt", "apt-get", "dpkg", "apk") if shutil.which(n)]
        self.assertEqual(found, [])
        self.assertIsNone(importlib.util.find_spec("pip"))
        probe = "import importlib.util; print(importlib.util.find_spec('pip') is None)"
        self.assertEqual(subprocess.run([KRAB_PYTHON, "-I", "-c", probe], capture_output=True, text=True,
                                        check=True).stdout.strip(), "True")

    def test_paths_match_the_trace_policy(self):
        # check.py judges these exec paths (SEC-10); a base change must keep them.
        with open(shutil.which("kapitan"), encoding="utf-8") as f:
            self.assertEqual(f.readline().strip(), "#!" + check.PYTHON)
        self.assertTrue(os.path.exists(check.PYTHON))
        self.assertEqual(shutil.which("helm"), "/usr/local/bin/helm")
        self.assertEqual([d for d in os.environ["PATH"].split(":") if not os.path.isdir(d)], [])


if __name__ == "__main__":
    unittest.main()
