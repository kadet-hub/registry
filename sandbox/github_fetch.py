"""Download a file from GitHub for the sandbox image build (GI-6).

Usage: github_fetch.py URL OUT

URL is a release asset, https://github.com/<owner>/<repo>/releases/download/<tag>/<name>,
or a file on https://raw.githubusercontent.com/. With GH_TOKEN, the build's secret,
a release asset comes through the REST API, because github.com ignores a token on
its download URL, and a raw file with the token. Without GH_TOKEN the URL is
fetched as it is. The Dockerfile checks the SHA-256.
"""

import json
import os
import re
import shutil
import sys
import urllib.request

RELEASE = re.compile(r"https://github\.com/([^/]+/[^/]+)/releases/download/([^/]+)/([^/]+)")
RAW = "https://raw.githubusercontent.com/"


def request(url, token, accept=None):
    req = urllib.request.Request(url, headers={"Accept": accept} if accept else {})
    if token:
        # Unredirected: not sent on to the storage host a release asset redirects to.
        req.add_unredirected_header("Authorization", f"Bearer {token}")
    return req


def source(url, token):
    """The request that downloads URL."""
    release = RELEASE.fullmatch(url)
    if not release and not url.startswith(RAW):
        sys.exit(f"github_fetch.py: {url} is neither a release asset nor a raw.githubusercontent.com file")
    if not (release and token):
        return request(url, token)
    repo, tag, name = release.groups()
    api = request(f"https://api.github.com/repos/{repo}/releases/tags/{tag}", token, "application/vnd.github+json")
    with urllib.request.urlopen(api, timeout=60) as r:
        assets = {a["name"]: a["url"] for a in json.load(r)["assets"]}
    if name not in assets:
        sys.exit(f"github_fetch.py: release {tag} of {repo} has no asset {name}")
    return request(assets[name], token, "application/octet-stream")


def main(url, out):
    token = os.environ.get("GH_TOKEN")
    print(f"github_fetch.py: {url} {'with the token' if token else 'anonymously'}", file=sys.stderr)
    with urllib.request.urlopen(source(url, token), timeout=60) as r, open(out, "wb") as f:
        shutil.copyfileobj(r, f)


if __name__ == "__main__":
    main(*sys.argv[1:])
