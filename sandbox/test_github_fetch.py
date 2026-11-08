"""GI-6: github_fetch.py sends the build's token to GitHub only, a release asset through the API."""

import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import github_fetch

ASSET = "https://github.com/o/r/releases/download/v1.0.0/a.tgz"
RAW = "https://raw.githubusercontent.com/o/r/v1.0.0/LICENSE"
API = "https://api.github.com/repos/o/r/releases/assets/7"


class Fetch(unittest.TestCase):
    def fetch(self, url, token, *bodies):
        """The requests main() sends, each answered with the next body, and what it wrote."""
        requests, bodies = [], list(bodies)

        def urlopen(req, timeout):
            requests.append(req)
            return io.BytesIO(bodies.pop(0))

        env = {k: v for k, v in os.environ.items() if k != "GH_TOKEN"} | ({"GH_TOKEN": token} if token else {})
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(github_fetch.urllib.request, "urlopen", urlopen):
            out = os.path.join(d, "out")
            github_fetch.main(url, out)
            with open(out, "rb") as f:
                return requests, f.read()

    def test_release_asset_through_the_api(self):
        release = json.dumps({"assets": [{"name": "b.tgz", "url": API + "0"}, {"name": "a.tgz", "url": API}]}).encode()
        requests, data = self.fetch(ASSET, "t", release, b"asset")
        self.assertEqual([r.full_url for r in requests], ["https://api.github.com/repos/o/r/releases/tags/v1.0.0", API])
        self.assertEqual(requests[1].get_header("Accept"), "application/octet-stream")
        for r in requests:
            self.assertEqual(r.unredirected_hdrs, {"Authorization": "Bearer t"})
            self.assertNotIn("Authorization", r.headers)
        self.assertEqual(data, b"asset")

    def test_raw_file_with_the_token(self):
        requests, data = self.fetch(RAW, "t", b"text")
        self.assertEqual([(r.full_url, r.unredirected_hdrs) for r in requests], [(RAW, {"Authorization": "Bearer t"})])
        self.assertEqual(data, b"text")

    def test_without_a_token_the_url_as_it_is(self):
        for url in (ASSET, RAW):
            requests, data = self.fetch(url, None, b"body")
            self.assertEqual([(r.full_url, r.unredirected_hdrs, r.headers) for r in requests], [(url, {}, {})])
            self.assertEqual(data, b"body")

    def test_missing_asset_fails(self):
        with self.assertRaises(SystemExit):
            self.fetch(ASSET, "t", json.dumps({"assets": [{"name": "b.tgz", "url": API}]}).encode())

    def test_other_hosts_get_no_request(self):
        for url in ("https://example.org/a.tgz", "https://github.com/o/r/archive/v1.tar.gz"):
            with self.assertRaises(SystemExit):
                self.fetch(url, "t")


if __name__ == "__main__":
    unittest.main()
