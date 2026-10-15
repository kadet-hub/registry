"""Check every HTML page of a built catalog site against CAT-8a and CAT-11 to CAT-11c (CAT-11d). Standard library only.

Usage: seo_check.py <site dir>
Prints one finding per line as `<requirement>: <path>: <message>` and exits 1
on any. A Hugo alias page (a meta refresh to the page's new URL) is a
redirect, not a page, and is not checked.
"""
import json
import os
import re
import sys
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

HEADINGS = {f"h{n}": n for n in range(1, 7)}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = self.description = self.canonical = self.text = None
        self.redirect = self.touch_icon = False
        self.headings, self.hrefs, self.ld, self.findings = [], [], [], []
        self.cards = 0  # ul depth inside a card list

    def handle_starttag(self, tag, attrs):
        a = {k: v or "" for k, v in attrs}
        rel = a.get("rel", "").split()
        if "href" in a:
            self.hrefs.append(a["href"])
        if tag == "title" and self.title is None:
            self.title, self.text = "", "title"
        elif tag == "script" and a.get("type") == "application/ld+json":
            self.ld.append("")
            self.text = "ld"
        elif tag == "meta" and a.get("name") == "description":
            self.description = a.get("content", "")
        elif tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            self.redirect = True
        elif tag == "link" and "canonical" in rel:
            self.canonical = a.get("href", "")
        elif tag == "link" and "apple-touch-icon" in rel:
            self.touch_icon = True
        elif tag == "img" and not a.get("alt", "").strip():
            self.findings.append(("CAT-11c", f"img {a.get('src', '')} has no alt text"))
        elif tag == "ul" and (self.cards or "cards" in a.get("class", "").split()):
            if not self.cards and self.headings[-1:] != [2]:
                self.findings.append(("CAT-11b", "card list does not follow an h2"))
            self.cards += 1
        elif tag in HEADINGS:
            level, prev = HEADINGS[tag], (self.headings or [0])[-1]
            if level > prev + 1:
                self.findings.append(("CAT-11b", f"h{level} follows {f'h{prev}' if prev else 'no heading'}"))
            if self.cards:
                self.findings.append(("CAT-11b", f"h{level} inside a card list"))
            self.headings.append(level)

    def handle_endtag(self, tag):
        if tag in ("title", "script"):
            self.text = None
        elif tag == "ul" and self.cards:
            self.cards -= 1

    def handle_data(self, data):
        if self.text == "title":
            self.title += data
        elif self.text == "ld":
            self.ld[-1] += data


def length(found, what, text, low, high):
    if text is None:
        found(f"no {what}")
    elif not low <= len(text) <= high:
        found(f"{what} has {len(text)} characters, not {low} to {high}: {text}")


def ld_types(blocks):
    types = set()
    for block in blocks:
        data = json.loads(block)
        for node in [data, *data.get("@graph", [])]:
            t = node.get("@type", [])
            types.update([t] if isinstance(t, str) else t)
    return types


def check(site):
    out = []
    pages = {}
    for root, _, files in os.walk(site):
        for name in files:
            if name.endswith(".html"):
                path = os.path.join(root, name)
                page = Page()
                with open(path, encoding="utf-8") as f:
                    page.feed(f.read())
                page.close()
                if not page.redirect:
                    pages[os.path.relpath(path, site).replace(os.sep, "/")] = page
    if "index.html" not in pages:
        return ["CAT-11a: index.html: no home page"]
    for path, page in sorted(pages.items()):
        def found(message, req="CAT-11"):
            out.append(f"{req}: {path}: {message}")
        length(found, "title", page.title, 30, 65)
        length(found, "meta description", page.description, 50, 160)
        if page.headings.count(1) != 1:
            found(f"{page.headings.count(1)} h1, not one")
        url = urlsplit(page.canonical or "")
        here = path.removesuffix("index.html")
        if url.scheme not in ("http", "https") or not url.netloc or not url.path.endswith("/" + here):
            found(f"canonical URL {page.canonical} is not the absolute URL of this page")
        if not page.touch_icon:
            found("no apple-touch-icon link", "CAT-11c")
        for href in page.hrefs:
            link = urlsplit(href)
            if link.netloc in ("", url.netloc) and "tags" in parse_qs(link.query, keep_blank_values=True):
                found(f"internal link with ?tags=: {href}", "CAT-8a")
        for req, message in page.findings:
            found(message, req)
    home = pages["index.html"]
    length(lambda m: out.append(f"CAT-11a: index.html: {m}"), "title", home.title, 50, 60)
    try:
        types = ld_types(home.ld)
    except (ValueError, AttributeError, TypeError) as e:
        types = set()
        out.append(f"CAT-11a: index.html: JSON-LD does not parse: {e}")
    for t in ("WebSite", "Organization"):
        if t not in types:
            out.append(f"CAT-11a: index.html: no {t} JSON-LD")
    try:
        with open(os.path.join(site, "sitemap.xml"), encoding="utf-8") as f:
            locs = {unescape(loc) for loc in re.findall(r"<loc>\s*([^<]*?)\s*</loc>", f.read())}
        for path, page in sorted(pages.items()):
            if re.fullmatch(r"generators/[^/]+/index\.html", path) and page.canonical not in locs:
                out.append(f"CAT-11: {path}: not in sitemap.xml")
    except FileNotFoundError:
        out.append("CAT-11: sitemap.xml: missing")
    sitemap = urljoin(home.canonical or "", "sitemap.xml")
    try:
        with open(os.path.join(site, "robots.txt"), encoding="utf-8") as f:
            if sitemap not in re.findall(r"(?mi)^sitemap:\s*(\S+)", f.read()):
                out.append(f"CAT-11: robots.txt: does not name {sitemap}")
    except FileNotFoundError:
        out.append("CAT-11: robots.txt: missing")
    return out


if __name__ == "__main__":
    findings = check(sys.argv[1])
    for line in findings:
        print(line)
    sys.exit(1 if findings else 0)
