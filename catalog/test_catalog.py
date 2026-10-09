import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from view import view

OWNER = "kadet-hub"


def record(d, yanked=None, description="Renders a ConfigMap", tags=("helm",)):
    return {"digest": "sha256:" + d * 64, "yanked": yanked, "advisories": [], "published": "2026-10-09T05:34:57Z",
            "description": description, "tags": list(tags), "license": "Apache-2.0", "kapitan": ">=0.36.3,<0.37",
            "krab": None, "tree": "0" * 40, "owners": [331675722], "binaries": [], "output_capabilities": [],
            "unparsed_outputs": [], "charts": [],
            "source": {"repo": "https://github.com/example/demo.git", "path": ".", "tag": "v1.0.0", "sha": "c" * 40}}


INDEX = {"serial": 7, "generators": {
    "demo": {"1.0.0": record("a", yanked="broken"), "1.10.0": record("b", description="<script>alert(1)</script>"),
             "1.2.0": record("c")},
    "old": {"0.1.0": record("d", yanked="entry removed", tags=())},
}}


def build(index, tmp):
    path = os.path.join(tmp, "index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f)
    out = os.path.join(tmp, "out")
    env = dict(os.environ, OWNER=OWNER, CATALOG_OFFLINE="1")
    subprocess.run([os.path.join(HERE, "build"), path, out], env=env, check=True)
    return out


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = build(INDEX, cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, *parts):
        with open(os.path.join(self.out, *parts, "index.html"), encoding="utf-8") as f:
            return f.read()

    def test_version_page_shows_pinned_entry_and_verification(self):
        html = self.page("generators", "demo")
        self.assertIn(f"source: ghcr.io/{OWNER}/demo@sha256:{'b' * 64}", html)
        self.assertIn(f"gh attestation verify oci://ghcr.io/{OWNER}/demo@sha256:{'b' * 64}", html)
        self.assertIn(f"https://github.com/{OWNER}/registry/.github/workflows/release.yml@refs/heads/main", html)
        self.assertLess(html.index(">1.10.0"), html.index(">1.2.0"))

    def test_yanked_version_shows_reason_and_no_entry(self):
        html = self.page("generators", "demo")
        self.assertIn("Yanked: broken", html)
        self.assertNotIn(f"source: ghcr.io/{OWNER}/demo@sha256:{'a' * 64}", html)
        self.assertIn("none, all versions yanked", self.page())

    def test_owner_without_login_shows_the_user_id(self):
        self.assertIn("<dd>331675722</dd>", self.page())

    def test_values_are_escaped(self):
        for html in (self.page(), self.page("generators", "demo")):
            self.assertNotIn("<script>alert", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_no_resource_from_another_origin(self):
        for html in (self.page(), self.page("generators", "demo"), self.page("generators", "old")):
            for ref in re.findall(r'<(?:script|link|img)\b[^>]*\b(?:src|href)="([^"]*)"', html):
                self.assertNotRegex(ref, r"^(https?:)?//", ref)

    def test_home_links_both_guides(self):
        html = self.page()
        for doc in ("consumers.md", "authors.md"):
            self.assertIn(f"https://github.com/{OWNER}/registry/blob/main/docs/{doc}", html)
        self.assertNotIn("No generators listed yet", html)

    def test_empty_index_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build({"serial": 1, "generators": {}}, tmp)
            with open(os.path.join(out, "index.html"), encoding="utf-8") as f:
                self.assertIn("No generators listed yet", f.read())


class View(unittest.TestCase):
    def test_display_data_from_the_api(self):
        answers = {"/repos/example/demo": {"stargazers_count": 0}, "/user/331675722": {"login": "someone"}}
        g = view(INDEX, OWNER, answers.get)["generators"][0]
        self.assertEqual((g["stars"], g["owners"]), ("0", [{"id": "331675722", "login": "someone"}]))
        self.assertEqual(g["latest"]["version"], "1.10.0")


if __name__ == "__main__":
    unittest.main()
