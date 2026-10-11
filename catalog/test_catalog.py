import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import urllib.parse
from html import unescape as _unescape

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from view import README_MAX, readme, view

OWNER = "kadet-hub"


def record(d, yanked=None, description="Renders a ConfigMap", tags=("helm",), advisories=()):
    return {"digest": "sha256:" + d * 64, "yanked": yanked, "advisories": list(advisories), "published": "2026-10-09T05:34:57Z",
            "description": description, "tags": list(tags), "license": "Apache-2.0", "kapitan": ">=0.36.3,<0.37",
            "krab": None, "tree": "0" * 40, "owners": [331675722], "binaries": [], "output_capabilities": [],
            "unparsed_outputs": [], "charts": [],
            "source": {"repo": "https://github.com/example/demo.git", "path": ".", "tag": "v1.0.0", "sha": "c" * 40}}


COMPAT = [{"software": "External Secrets Operator", "version": "2.11.0", "source": "https://github.com/external-secrets/external-secrets/tree/v2.11.0/config/crds/bases"}]

SCAN = {"at": "2026-10-10T08:00:00Z", "gate": "d" * 40, "run": "https://github.com/kadet-hub/registry/actions/runs/42",
        "exceptions": 1, "checks": [{"id": "secrets", "tool": "gitleaks 8.30.1"}, {"id": "sandbox", "tool": "gVisor 20261005, Kapitan 0.36.3"}]}

INDEX = {"serial": 7, "generators": {
    "demo": {"1.0.0": record("a", yanked="broken", advisories=["GHSA-2345-6789-cfgh"]), "1.10.0": dict(record("b", description="<script>alert(1)</script>"), scan=SCAN, compatibility=COMPAT),
             "1.2.0": record("c")},
    "old": {"0.1.0": record("d", yanked="entry removed", tags=())},
}}


README = """# Demo

Intro with <script>alert(2)</script> raw HTML and <b>bold</b>.

[docs](docs/usage.md) [site](https://example.org/x) [bad](javascript:alert(3)) [anchor](#usage)
[proto](//evil.example/x)

![diagram](img/arch.png)

## Usage

```yaml
parameters:
  demo: {}
```

| a | b |
|---|---|
| 1 | 2 |
"""


def artifact(path, files):
    with tarfile.open(path, "w") as t:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, __import__("io").BytesIO(data))


def build(index, tmp, artifacts=None, sboms=None, rekor=None, discussions=None, pages=None):
    path = os.path.join(tmp, "index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f)
    out = os.path.join(tmp, "out")
    env = dict(os.environ, OWNER=OWNER, CATALOG_OFFLINE="1", CATALOG_ARTIFACTS=artifacts or os.path.join(tmp, "none"),
               CATALOG_SBOMS=sboms or os.path.join(tmp, "none"), CATALOG_REKOR=rekor or os.path.join(tmp, "none.json"),
               CATALOG_DISCUSSIONS=discussions or os.path.join(tmp, "none.json"),
               CATALOG_PAGES=pages or os.path.join(tmp, "none"))
    subprocess.run([os.path.join(HERE, "build"), path, out], env=env, check=True)
    return out


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        arts = os.path.join(cls.tmp.name, "artifacts")
        os.mkdir(arts)
        artifact(os.path.join(arts, "demo.tar"), {"README.md": README, "kapitan-generator.yaml": "name: demo\n"})
        artifact(os.path.join(arts, "old.tar"), {"README.md": "# Old readme\n"})
        sboms = os.path.join(cls.tmp.name, "sboms", "demo")
        os.makedirs(sboms)
        with open(os.path.join(sboms, "1.10.0.spdx.json"), "w", encoding="utf-8") as f:
            f.write('{"spdxVersion": "SPDX-2.3"}')
        rekor = os.path.join(cls.tmp.name, "rekor.json")
        with open(rekor, "w", encoding="utf-8") as f:
            json.dump({"demo": {"1.10.0": "3202022821", "1.0.0": "17", "1.2.0": "not-a-number"}}, f)
        discussions = os.path.join(cls.tmp.name, "discussions.json")
        with open(discussions, "w", encoding="utf-8") as f:
            json.dump({"demo": {"url": f"https://github.com/{OWNER}/registry/discussions/5", "up": 3},
                       "old": {"url": "https://evil.example/x", "up": 1}}, f)
        pages = os.path.join(cls.tmp.name, "pages")
        os.mkdir(pages)
        with open(os.path.join(pages, "demo.html"), "w", encoding="utf-8") as f:
            f.write('<span class="h6">Total downloads</span>\n<h3 title="1215">1.2k</h3>')
        cls.out = build(INDEX, cls.tmp.name, arts, os.path.dirname(sboms), rekor, discussions, pages)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, *parts):
        with open(os.path.join(self.out, *parts, "index.html"), encoding="utf-8") as f:
            return f.read()

    def pages(self):
        return [self.page(), self.page("generators", "demo"), self.page("generators", "old")]

    def readme_html(self):
        html = self.page("generators", "demo")
        return html[html.index('class="readme"'):html.index('class="versions"')]

    def test_version_page_shows_pinned_entry_and_verification(self):
        html = self.page("generators", "demo")
        self.assertIn(f"source: ghcr.io/{OWNER}/demo@sha256:{'b' * 64}", html)
        self.assertIn(f"gh attestation verify \\\n  oci://ghcr.io/{OWNER}/demo@sha256:{'b' * 64}", html)
        self.assertIn(f"https://github.com/{OWNER}/registry/.github/workflows/release.yml@refs/heads/main", html)
        self.assertLess(html.index(">1.10.0"), html.index(">1.2.0"))

    def test_yanked_version_shows_reason_and_no_entry(self):
        html = self.page("generators", "demo")
        self.assertIn("Yanked: broken", html)
        self.assertIn(f"https://github.com/{OWNER}/registry/security/advisories/GHSA-2345-6789-cfgh", html)
        self.assertIn(f"<code>sha256:{'a' * 64}</code>", html)
        self.assertNotIn(f"source: ghcr.io/{OWNER}/demo@sha256:{'a' * 64}", html)
        old_card = self.card("old")
        self.assertIn('<p class="meta-line">no listed version, all yanked</p>', old_card)

    def test_owner_without_login_shows_the_user_id(self):
        self.assertIn("<dt>Maintainer</dt><dd>331675722</dd>", self.page())

    def test_values_are_escaped(self):
        for html in (self.page(), self.page("generators", "demo")):
            self.assertNotIn("<script>alert", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_no_resource_from_another_origin(self):
        for html in self.pages():
            for ref in re.findall(r'<(?:script|link|img)\b[^>]*\b(?:src|href)="([^"]*)"', html):
                if 'rel="canonical"' not in html[html.rfind("<", 0, html.index(ref)):html.index(ref)]:
                    self.assertNotRegex(ref, r"^(https?:)?//", ref)
            self.assertNotIn(' style="', html)  # the CSP blocks inline styles

    def test_readme_of_the_latest_version_without_raw_html(self):
        html = self.readme_html()
        self.assertIn("<h2", html)  # README headings sit below the page's h1
        self.assertNotIn("<script", html)
        self.assertIn("<!-- raw HTML omitted -->alert(2)", html)
        self.assertNotIn("<b>", html)
        self.assertNotIn("javascript:", html)
        self.assertNotIn("evil.example", html)
        self.assertIn(f'href="https://github.com/example/demo/blob/{"c" * 40}/docs/usage.md"', html)
        self.assertIn('href="https://example.org/x" rel="nofollow noopener"', html)
        self.assertIn('href="#readme-usage"', html)
        self.assertIn('id="readme-usage"', html)
        self.assertNotIn("<img", html)
        self.assertIn(f'href="https://github.com/example/demo/blob/{"c" * 40}/img/arch.png"', html)
        self.assertIn('class="chroma"', html)
        self.assertNotIn("Old readme", self.page("generators", "old"))  # every version yanked

    def test_tags_link_to_the_filtered_home_page(self):
        self.assertIn('href="../../?tags=helm"', self.page("generators", "demo"))
        home = self.page()
        self.assertIn('href="./?tags=helm"', home)
        self.assertIn('data-tag="helm" aria-pressed="false"', home)

    def test_copy_buttons_and_wrapping(self):
        html = self.page("generators", "demo")
        for block in re.findall(r'<pre id="([^"]+)">', html):
            self.assertIn(f'data-copy="{block}"', html)
        self.assertGreaterEqual(html.count('class="copy icon-button"'), 4)
        with open(os.path.join(self.out, "style.css"), encoding="utf-8") as f:
            css = f.read()
        self.assertRegex(css, r"pre \{[^}]*white-space: pre-wrap")
        self.assertRegex(css, r"pre \{[^}]*overflow-x: hidden")

    def test_issue_forms_are_linked(self):
        links = [__import__("html").unescape(h) for h in re.findall(r'href="([^"]*issues/new[^"]*)"', self.page("generators", "demo"))]
        self.assertIn(f"https://github.com/{OWNER}/registry/issues/new?generator=demo&template=generator-report.yml&title=%5Breport%5D+demo%3A+&version=1.10.0", links)
        self.assertIn(f"https://github.com/{OWNER}/registry/issues/new?template=generator-request.yml", self.page())
        for form in ("generator-report", "generator-request"):
            self.assertTrue(os.path.isfile(os.path.join(HERE, "..", ".github", "ISSUE_TEMPLATE", f"{form}.yml")))

    def test_tags_page_and_glossary(self):
        with open(os.path.join(HERE, "..", "policy", "tags.yaml"), encoding="utf-8") as f:
            tags, tag = {}, None  # top-level keys and their fields; no PyYAML on the runner's python
            for line in f:
                if m := re.match(r"^([a-z]+):$", line):
                    tag = tags.setdefault(m.group(1), set())
                elif (m := re.match(r"^  ([a-z]+): \S", line)) and tag is not None:
                    tag.add(m.group(1))
        with open(os.path.join(HERE, "..", "policy", "manifest.schema.json"), encoding="utf-8") as f:
            enum = json.load(f)["properties"]["tags"]["items"]["enum"]
        self.assertEqual(sorted(tags), sorted(enum))
        for name, fields in tags.items():
            self.assertTrue({"title", "means", "assign", "not"} <= fields, name)
        page = self.page("tags")
        for tag in enum:
            self.assertIn(f'id="{tag}"', page)
        self.assertIn('href="../?tags=helm">1 generator tagged helm</a>', page)
        self.assertIn("No generator tagged ci yet.", page)
        home = self.page()
        self.assertIn('data-tag="helm" aria-pressed="false" title="Renders a Helm chart or builds on one."><svg class="icon" aria-hidden="true"><use href="#i-tag-helm"/></svg>helm <span class="count">(1)</span>', home)
        self.assertIn('href="./tags/"', home)
        glossary = self.page("glossary")
        self.assertIn('href="https://kapitan.dev/"', glossary)
        self.assertIn('id="index"', glossary)

    def test_legal_pages_and_notices(self):
        for html in self.pages():
            self.assertIn("not affiliated with or endorsed by the Kapitan project or kapicorp", html)
            self.assertIn("as is and on a best-effort basis: use at your own risk", html)
            for href in ("privacy/", "imprint/", "registry/blob/main/TERMS.md", "SECURITY.md#removal-requests"):
                self.assertIn(href, html)
        demo = self.page("generators", "demo")
        install = demo[demo.index('id="install"'):demo.index('class="readme"')]
        self.assertIn("use at your own risk", install)
        privacy = self.page("privacy")
        self.assertIn("GitHub Pages", privacy)
        self.assertIn("localStorage", privacy)
        self.assertIn("Art. 77", privacy)
        self.assertIn("§ 5 DDG", self.page("imprint"))
        with open(os.path.join(HERE, "..", "README.md"), encoding="utf-8") as f:
            self.assertIn("not affiliated with or endorsed by\nthe Kapitan project or kapicorp", f.read())

    def test_scan_record_and_sbom(self):
        html = self.page("generators", "demo")
        latest = html[html.index('id="checks"'):html.index('id="details"')]
        self.assertIn('href="https://github.com/kadet-hub/registry/actions/runs/42">release run</a>', latest)
        self.assertIn("<code>dddddddddddd</code>, with 1 reviewed exception.", latest)
        self.assertIn("<strong>Secrets</strong> <span class=\"tool\">gitleaks 8.30.1</span>", latest)
        self.assertIn('href="../../generators/demo/1.10.0.spdx.json" download', latest)
        self.assertNotRegex(latest, r"(?i)\bsecure\b|score")
        with open(os.path.join(self.out, "generators", "demo", "1.10.0.spdx.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["spdxVersion"], "SPDX-2.3")
        older = html[html.index('id="v1.2.0"'):html.index('id="v1.0.0"')]
        self.assertIn("No scan record", older)
        self.assertIn("No SBOM attestation for this version.", older)
        self.assertIn("<dt>Scanned</dt><dd>2026-10-10</dd>", self.page())

    def test_llms_txt(self):
        with open(os.path.join(self.out, "llms.txt"), encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("# kadet-hub\n\n> "))
        for link in ("generator-template/blob/main/AGENTS.md", "docs/authors.md", "policy/imports.txt", "policy/tags.yaml", "kadet-hub.org/glossary/"):
            self.assertIn(link, text)

    def test_built_for(self):
        self.assertIn('<dt>Built for</dt><dd class="built-for"><span>External Secrets Operator 2.11.0</span></dd>', self.page())
        html = self.page("generators", "demo")
        self.assertIn('<a href="https://github.com/external-secrets/external-secrets/tree/v2.11.0/config/crds/bases">External Secrets Operator 2.11.0</a>', html)
        older = html[html.index('id="v1.2.0"'):html.index('id="v1.0.0"')]
        self.assertIn("<dt>Built for</dt><dd>not recorded</dd>", older)

    def test_tag_pages_feed_og_and_guides(self):
        page = self.page("tags", "helm")
        self.assertIn("Helm generators for Kapitan", page)
        self.assertIn('data-name="demo"', page)  # the card partial
        self.assertIn("No generator is tagged ci yet.", self.page("tags", "ci"))
        with open(os.path.join(self.out, "index.xml"), encoding="utf-8") as f:
            feed = f.read()
        self.assertTrue(feed.startswith('<?xml version="1.0" encoding="utf-8"?>'))
        __import__("xml.dom.minidom").dom.minidom.parseString(feed)
        self.assertLess(feed.index("demo 1.10.0"), feed.index("old 0.1.0 (yanked)") if "old 0.1.0" in feed else len(feed))
        self.assertIn("https://kadet-hub.org/generators/demo/#v1.10.0", feed)
        for html in self.pages():
            self.assertIn('<meta property="og:image" content="https://kadet-hub.org/og.png">', html)
        self.assertTrue(os.path.isfile(os.path.join(self.out, "og.png")))
        guides = self.page("guides")
        for slug in ("writing-a-kapitan-generator", "generator-helm-or-jinja2", "supply-chain-security-for-kapitan-generators"):
            self.assertIn(f"guides/{slug}/", guides)
            self.page("guides", slug)

    def test_version_permalinks_and_transparency_log(self):
        html = self.page("generators", "demo")
        for v in ("1.10.0", "1.2.0", "1.0.0"):
            self.assertIn(f'id="v{v}"', html)
            self.assertIn(f'<a class="permalink" href="#v{v}" aria-label="Link to version {v}">#</a>', html)
        self.assertIn('href="https://search.sigstore.dev/?logIndex=3202022821">Rekor entry 3202022821</a>', html)
        self.assertIn('href="https://search.sigstore.dev/?logIndex=17">Rekor entry 17</a>', html)  # yanked keeps its entry
        self.assertNotIn("not-a-number", html)
        main = html[html.index('id="install"'):html.index('id="readme"')]
        self.assertIn("gh attestation verify \\\n  oci://ghcr.io/kadet-hub/demo@sha256:", main)
        self.assertIn("\n  --owner kadet-hub \\\n  --cert-identity https://", main)

    def test_one_column_with_table_of_contents(self):
        html = self.page("generators", "demo")
        self.assertNotIn("<aside", html)
        self.assertIn('<nav class="toc" aria-labelledby="toc">\n<details open>', html)  # open without JavaScript
        self.assertLess(html.index('class="toc"'), html.index('class="generator-body"'))  # beside the column, not in it
        start = html.index('id="toc"')
        toc = html[start:html.index("</nav>", start)]
        links = ["install", "verify", "checks", "details", "readme", "versions"]
        self.assertEqual(re.findall(r'href="#([a-z]+)"', toc), links)
        positions = [html.index(f'id="{a}"') for a in links]
        self.assertEqual(positions, sorted(positions))
        old = self.page("generators", "old")  # every version yanked: no install, no readme
        self.assertEqual(re.findall(r'href="#([a-z]+)"', old[old.index('id="toc"'):old.index("</nav>", old.index('id="toc"'))]), ["versions"])

    def card(self, name):
        home = self.page()
        start = home.index(f'data-name="{name}"')
        return home[start:home.index("</li>", start)]

    def test_cards_show_the_same_fields_in_the_same_order(self):
        for name in ("demo", "old"):
            card = self.card(name)
            order = ['class="stretched"', 'class="meta-line"', 'class="description"',
                     "<dt>Built for</dt>", "<dt>Maintainer</dt>", "<dt>Popularity</dt>", "<dt>Scanned</dt>"]
            positions = [card.index(marker) for marker in order]
            self.assertEqual(positions, sorted(positions), name)
            self.assertNotIn("Apache-2.0", card)  # CAT-22: license only on the page
            self.assertEqual(card.count("<a "), 1 + card.count('class="tag"') + card.count('class="fact-link"'))
        self.assertIn("<dt>Built for</dt><dd>not recorded</dd>", self.card("old"))
        self.assertIn("<dt>Scanned</dt><dd>not scanned</dd>", self.card("old"))
        self.assertIn('<p class="meta-line">1.10.0 · <time datetime="2026-10-09T05:34:57Z">2026-10-09</time></p>', self.card("demo"))

    def test_maintainer_links_to_the_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = os.path.join(tmp, "site")
            shutil.copytree(os.path.join(HERE, "site"), site)
            os.makedirs(os.path.join(site, "data"))
            shutil.copy(os.path.join(HERE, "..", "policy", "tags.yaml"), os.path.join(site, "data", "tags.yaml"))
            with open(os.path.join(site, "data", "catalog.json"), "w", encoding="utf-8") as f:
                json.dump(view(INDEX, OWNER, {"/user/331675722": {"login": "someone"}}.get), f)
            subprocess.run(["hugo", "--quiet", "--source", site, "--destination", os.path.join(tmp, "out")], check=True)
            with open(os.path.join(tmp, "out", "index.html"), encoding="utf-8") as f:
                home = f.read()
        self.assertIn('<dt>Maintainer</dt><dd><a class="fact-link" href="https://github.com/someone">someone</a></dd>', home)

    def test_request_a_feature_goes_to_the_source_repository(self):
        html = self.page("generators", "demo")
        link = re.search(r'<a class="button" href="([^"]+)">Request a feature</a>', html).group(1)
        self.assertTrue(link.startswith("https://github.com/example/demo/issues/new?"))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(_unescape(link)).query)
        self.assertEqual(query["title"], ["[demo] "])
        self.assertIn("Version: 1.10.0", query["body"][0])
        self.assertIn("Catalog: https://kadet-hub.org/generators/demo/", query["body"][0])
        gitlab = dict(INDEX, generators={"g": {"1.0.0": dict(record("e"), source=dict(record("e")["source"], repo="https://gitlab.com/group/proj.git"))}})
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(build(gitlab, tmp), "generators", "g", "index.html"), encoding="utf-8") as f:
                page = f.read()
        link = re.search(r'<a class="button" href="([^"]+)">Request a feature</a>', page).group(1)
        self.assertTrue(link.startswith("https://gitlab.com/group/proj/-/issues/new?"))
        self.assertIn("issue[title]", urllib.parse.unquote(_unescape(link)))

    def test_sort_keys(self):
        home = self.page()
        self.assertIn('<select id="sort">', home)
        self.assertIn('data-name="demo" data-published="2026-10-09T05:34:57Z" data-popularity="40"', home)
        self.assertIn('<option value="popularity">Popularity</option>', home)
        self.assertNotIn('value="stars"', home)

    def test_popularity_score(self):
        from view import pulls, score
        # 10·log2(1+3) + 4·log2(1+0) + 2·log2(1+1200) = 20 + 0 + 20.46
        self.assertEqual(score(3, 0, 1, 1200), 40)
        self.assertEqual(score(0, 0, 6, 229), 16)
        self.assertEqual(score(10, 0, 1, 5), 40)
        self.assertEqual(score(0, 12, 6, 0), 6)  # 12 stars shared by 6 generators count as 2
        with tempfile.TemporaryDirectory() as tmp:
            page = os.path.join(tmp, "p.html")
            for text, expected in (("Total downloads 229", 229), ("Total downloads</span> <h3>1.2k</h3>", 1200),
                                   ("Total downloads 3,456", 3456), ("Total downloads 2M", 2000000), ("no count", None)):
                with open(page, "w", encoding="utf-8") as f:
                    f.write(text)
                self.assertEqual(pulls(page), expected, text)
            self.assertIsNone(pulls(os.path.join(tmp, "missing.html")))

    def test_previous_build_supplies_the_readme_of_an_unchanged_digest(self):
        from view import load_previous
        with tempfile.TemporaryDirectory() as tmp:
            prev = os.path.join(tmp, "catalog.json")
            digest = INDEX["generators"]["demo"]["1.10.0"]["digest"]
            with open(prev, "w", encoding="utf-8") as f:
                json.dump({"generators": [{"name": "demo", "latest": {"digest": digest}, "readme": "# Kept"},
                                          {"name": "big", "latest": {"digest": "sha256:x"}, "readme": "x" * (README_MAX + 1)}]}, f)
            previous = load_previous(prev)
        self.assertEqual(previous, {("demo", digest): "# Kept"})  # oversized README dropped
        g = view(INDEX, OWNER, lambda _: None, previous=previous)["generators"][0]
        self.assertEqual(g["readme"], "# Kept")
        moved = {"generators": dict(INDEX["generators"], demo=dict(INDEX["generators"]["demo"], **{"1.11.0": record("f")}))}
        self.assertIsNone(view(moved, OWNER, lambda _: None, previous=previous)["generators"][0]["readme"])  # new digest
        with open(os.path.join(self.out, "catalog.json"), encoding="utf-8") as f:
            self.assertIn("demo", [g["name"] for g in json.load(f)["generators"]])  # published for the next build

    def test_popularity_page_and_links(self):
        page = self.page("popularity")
        self.assertIn("score = round( 10 · log2(1 + 👍)", page)
        self.assertIn('<tr id="demo"><th scope="row"><a href="../generators/demo/">demo</a></th><td>3</td><td>0 ÷ 1</td><td>1200</td><td>40</td></tr>', page)
        self.assertIn("<td>not read</td>", page)  # old: no package page
        self.assertIn('<dt>Popularity</dt><dd><a class="fact-link" href="./popularity/#demo">40</a></dd>', self.page())
        self.assertIn("· 1200 pulls</dd>", self.page("generators", "demo"))

    def test_thumbs_up_from_discussions(self):
        self.assertIn(f'<a href="https://github.com/{OWNER}/registry/discussions/5">👍 3</a> on GitHub Discussions', self.page("generators", "demo"))
        self.assertNotIn("evil.example", self.page("generators", "old"))  # CAT-20: only this registry's discussions
        self.assertNotIn("Thumbs up</dt>", self.page("generators", "old"))

    def test_seo(self):
        for parts in ((), ("generators", "demo"), ("generators", "old"), ("tags",), ("glossary",), ("tags", "helm"), ("tags", "observability"),
                      ("guides",), ("privacy",), ("imprint",), ("guides", "writing-a-kapitan-generator"), ("guides", "supply-chain-security-for-kapitan-generators")):
            html = self.page(*parts)
            title = re.search(r"<title>([^<]*)</title>", html).group(1)
            desc = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
            self.assertTrue(30 <= len(title) <= 65, title)
            self.assertTrue(50 <= len(__import__("html").unescape(desc)) <= 160, desc)
            self.assertEqual(html.count("<h1"), 1)
            self.assertIn(f'<link rel="canonical" href="https://kadet-hub.org/{"/".join(parts) + "/" if parts else ""}">', html)
        with open(os.path.join(self.out, "sitemap.xml"), encoding="utf-8") as f:
            sitemap = f.read()
        for name in ("demo", "old"):
            self.assertIn(f"<loc>https://kadet-hub.org/generators/{name}/</loc>", sitemap)
        with open(os.path.join(self.out, "robots.txt"), encoding="utf-8") as f:
            self.assertIn("Sitemap: https://kadet-hub.org/sitemap.xml", f.read())
        ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', self.page("generators", "demo"), re.S).group(1)
        self.assertNotIn("<", ld)
        self.assertEqual(json.loads(ld)["description"], "<script>alert(1)</script>")

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
    def test_readme_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            small, big, none = (os.path.join(tmp, n) for n in ("small.tar", "big.tar", "none.tar"))
            artifact(small, {"./README.md": "# hi\n"})
            artifact(big, {"README.md": "x" * (README_MAX + 1)})
            artifact(none, {"docs/README.md": "# nested\n"})
            self.assertEqual(readme(small), "# hi\n")
            self.assertIsNone(readme(big))
            self.assertIsNone(readme(none))
            self.assertIsNone(readme(os.path.join(tmp, "missing.tar")))

    def test_display_data_from_the_api(self):
        answers = {"/repos/example/demo": {"stargazers_count": 0}, "/user/331675722": {"login": "someone"}}
        g = view(INDEX, OWNER, answers.get)["generators"][0]
        self.assertEqual((g["stars"], g["owners"]), ("0", [{"id": "331675722", "login": "someone"}]))
        self.assertEqual(g["latest"]["version"], "1.10.0")
        self.assertIsNone(g["stars_shared"])

    def test_shared_stars_are_labelled(self):
        index = {"generators": dict(INDEX["generators"], two={"1.0.0": record("e")})}
        gens = {g["name"]: g for g in view(index, OWNER, {"/repos/example/demo": {"stargazers_count": 9}}.get)["generators"]}
        self.assertEqual((gens["demo"]["stars_shared"], gens["two"]["stars_shared"]), (2, 2))
        self.assertEqual(gens["old"]["stars_shared"], 2)  # all yanked: not counted, but its repo's stars are shared
        g = view(index, OWNER, lambda _: None)["generators"][0]
        self.assertIsNone(g["stars_shared"])  # no stars, no label


class Discussions(unittest.TestCase):
    """catalog/discussions against a fake gh (CAT-20)."""

    def run_with(self, categories, nodes):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        log = self.log = os.path.join(tmp.name, "log")
        state = os.path.join(tmp.name, "nodes.json")
        with open(state, "w", encoding="utf-8") as f:
            json.dump(nodes, f)
        gh = os.path.join(tmp.name, "gh")
        with open(gh, "w", encoding="utf-8") as f:
            f.write(f"""#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
query = next(a.split("=", 1)[1] for a in args if a.startswith("query="))
fields = dict(a.split("=", 1) for a in args if "=" in a and not a.startswith("query="))
nodes = json.load(open({state!r}))
if "createDiscussion" in query:
    open({log!r}, "a").write(fields["t"] + "\\n")
    open({log!r} + ".body", "w").write(fields["b"])
    nodes.append({{"title": fields["t"], "url": "https://github.com/kadet-hub/registry/discussions/" + str(len(nodes) + 1),
                  "author": {{"login": "github-actions"}}, "reactions": {{"totalCount": 0}}}})
    json.dump(nodes, open({state!r}, "w"))
    print("{{}}")
elif "discussionCategories" in query:
    print(json.dumps({{"id": "R_1", "discussionCategories": {{"nodes": {categories!r}}}}}))
else:
    print(json.dumps({{"pageInfo": {{"hasNextPage": False}}, "nodes": nodes}}))
""")
        os.chmod(gh, 0o755)
        index = os.path.join(tmp.name, "index.json")
        with open(index, "w", encoding="utf-8") as f:
            json.dump({"generators": dict(INDEX["generators"], keda={"1.0.0": record("e")}, squatted={"1.0.0": record("f")})}, f)
        env = dict(os.environ, OWNER=OWNER, PATH=tmp.name + os.pathsep + os.environ["PATH"])
        p = subprocess.run([os.path.join(HERE, "discussions"), index], env=env, capture_output=True, text=True, check=True)
        created = []
        if os.path.exists(log):
            with open(log, encoding="utf-8") as f:
                created = f.read().split()
        return json.loads(p.stdout), created, p.stderr

    def test_opens_missing_counts_only_its_own(self):
        url = "https://github.com/kadet-hub/registry/discussions/"
        nodes = [{"title": "keda", "url": url + "1", "author": {"login": "github-actions"}, "reactions": {"totalCount": 4}},
                 {"title": "squatted", "url": url + "2", "author": {"login": "someone"}, "reactions": {"totalCount": 99}}]
        result, created, _ = self.run_with([{"id": "C_1", "name": "Generators"}], nodes)
        self.assertEqual(created, ["demo"])  # not old (all yanked), not keda or squatted (title exists)
        with open(self.log + ".body", encoding="utf-8") as f:
            body = f.read()
        self.assertIn("👍 this post if you use **demo**", body)
        self.assertIn("(https://kadet-hub.org/generators/demo/)", body)
        self.assertIn(f"(https://github.com/{OWNER}/registry/issues/new?template=generator-report.yml&generator=demo)", body)
        self.assertEqual(result, {"keda": {"url": url + "1", "up": 4}, "demo": {"url": url + "3", "up": 0}})

    def test_without_the_category_nothing_is_opened(self):
        result, created, err = self.run_with([{"id": "C_0", "name": "General"}], [])
        self.assertEqual((result, created), ({}, []))
        self.assertIn('no "Generators" discussion category', err)


if __name__ == "__main__":
    unittest.main()
