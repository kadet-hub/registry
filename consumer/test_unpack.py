import io
import os
import sys
import tarfile
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unpack


class Unpack(unittest.TestCase):  # CON-1c
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "src")
        self.dest = os.path.join(self.tmp.name, "dest")
        os.mkdir(self.src)

    def tearDown(self):
        self.tmp.cleanup()

    def tar(self, *members):
        with tarfile.open(os.path.join(self.src, "a.tar"), "w") as t:
            for info, data in members:
                t.addfile(info, io.BytesIO(data) if data is not None else None)

    def file(self, name, data=b"x"):
        info = tarfile.TarInfo(name)
        info.size = len(data)
        return info, data

    def test_regular_tar_unpacks(self):
        self.tar(self.file("chart/Chart.yaml", b"name: demo\n"))
        unpack.unpack(self.src, self.dest)
        with open(os.path.join(self.dest, "chart", "Chart.yaml"), "rb") as f:
            self.assertEqual(f.read(), b"name: demo\n")

    def test_tar_symlink_fails(self):
        link = tarfile.TarInfo("chart/link")
        link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
        self.tar((link, None))
        with self.assertRaisesRegex(ValueError, "not a regular file"):
            unpack.unpack(self.src, self.dest)

    def test_zip_leaving_output_path_fails(self):
        with zipfile.ZipFile(os.path.join(self.src, "a.zip"), "w") as z:
            z.writestr("../escape", b"x")
        with self.assertRaisesRegex(ValueError, "leaves the output path"):
            unpack.unpack(self.src, self.dest)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "escape")))

    def test_archives_above_the_limit_fail(self):
        with zipfile.ZipFile(os.path.join(self.tmp.name, "b.zip"), "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("big", b"\0" * 2048)
        archives = {"a.tar": lambda: self.tar(self.file("big", b"\0" * 2048)),
                    "b.zip": lambda: os.rename(os.path.join(self.tmp.name, "b.zip"), os.path.join(self.src, "b.zip"))}
        for name, make in archives.items():
            with self.subTest(name=name), mock.patch.object(unpack, "MAX_TOTAL", 1024):
                for old in os.listdir(self.src):
                    os.remove(os.path.join(self.src, old))
                make()
                with self.assertRaisesRegex(ValueError, "more than 1024 bytes"):
                    unpack.unpack(self.src, self.dest)


if __name__ == "__main__":
    unittest.main()
