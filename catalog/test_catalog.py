import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import unittest.mock
import urllib.parse
import xml.etree.ElementTree as ET
from html import unescape as _unescape

HERE = os.path.dirname(os.path.abspath(__file__))
SEO_CHECK = os.path.join(HERE, "seo_check.py")
sys.path.insert(0, HERE)
from view import README_MAX, readme, releases, schema_kinds, view

OWNER = "kadet-hub"


def record(d, yanked=None, description="Renders a ConfigMap", tags=("helm",), advisories=()):
    return {"digest": "sha256:" + d * 64, "yanked": yanked, "advisories": list(advisories), "published": "2026-10-09T05:34:57Z",
            "description": description, "tags": list(tags), "license": "Apache-2.0", "kapitan": ">=0.36.3,<0.37",
            "krab": None, "tree": "0" * 40, "owners": [331675722], "binaries": [], "output_capabilities": [],
            "unparsed_outputs": [], "charts": [],
            "source": {"repo": "https://github.com/example/demo.git", "path": ".", "tag": "v1.0.0", "sha": "c" * 40}}


COMPAT = [{"software": "External Secrets Operator", "version": "2.11.0", "source": "https://github.com/external-secrets/external-secrets/tree/v2.11.0/config/crds/bases"},
          {"software": "External Secrets Operator", "version": "2.11.0", "source": "https://github.com/external-secrets/external-secrets/tree/v2.11.0/config/crds/other"}]

SCAN = {"at": "2026-10-10T08:00:00Z", "gate": "d" * 40, "run": "https://github.com/kadet-hub/registry/actions/runs/42",
        "exceptions": 1, "checks": [{"id": "secrets", "tool": "gitleaks 8.30.1"}, {"id": "sandbox", "tool": "gVisor 20261005, Kapitan 0.36.3"}]}

# CAT-27: 200 lines with markup and control characters.
DIFF = ("--- a/compiled/t/cm.yml\n+++ b/compiled/t/cm.yml\n@@ -1 +1,196 @@\n-<script>alert(4)</script>\n"
        + "".join(f"+line {i}\x1b[31m\u202e\r\n" for i in range(196)))
OUTPUT_DIFF = {"base": "1.2.0", "files": 1, "hunks": 1, "sha256": hashlib.sha256(DIFF.encode()).hexdigest()}

# PUB-10: the kinds record of demo 1.10.0, with entries view.py drops (CAT-29).
KINDS = [{"group": "gateway.networking.k8s.io", "version": "v1", "kind": "HTTPRoute"}, {"group": "", "version": "v1", "kind": "ConfigMap"},
         {"group": "<b>", "version": "v1", "kind": "X"}, {"group": "", "version": "v1", "kind": "Bad Kind"},
         {"group": "", "version": "1", "kind": "Y"}, {"group": "", "version": "v1"}, "ConfigMap"]

INDEX = {"serial": 7, "generators": {
    "demo": {"1.0.0": record("a", yanked="broken", advisories=["GHSA-2345-6789-cfgh"]),
             "1.10.0": dict(record("b", description="<script>alert(1)</script>"), scan=SCAN, compatibility=COMPAT, output_diff=OUTPUT_DIFF,
                           kinds=KINDS, backends=["reclass-rs", "omegaconf"], krab="compatible"),
             "1.2.0": record("c")},
    "old": {"0.1.0": record("d", yanked="entry removed", tags=())},
}}
# Site only: a listed generator without scan record or compatibility, its description with line breaks and control characters.
PLAIN = "Renders a [ConfigMap](x)\r\n## Not a heading\t\x9b31m\u202e*bold*"  # characters XML allows: the feed lists it
SITE_INDEX = {**INDEX, "generators": {**INDEX["generators"], "plain": {"0.2.0": dict(record("e", tags=(), description=PLAIN), published="2026-09-30T23:59:59Z",
                                                                                    output_diff={"base": None, "error": "no earlier listed version"})}}}

# CAT-31: open requests as the build writes them, with a body view.py drops and an entry it rejects.
WANTED = [{"number": 7, "title": "[request] <script>alert(5)</script>\x1b[31m\u202e  cert-manager", "up": 2, "created": "2026-10-03T09:00:00Z",
           "updated": "2026-10-12T10:00:00Z", "body": "<b>body text</b>"},
          {"number": 9, "title": "[request] loki", "up": 5, "created": "2026-10-05T09:00:00Z", "updated": "2026-10-06T10:00:00Z"},
          {"number": 4, "title": "[request] keycloak", "up": 2, "created": "2026-10-01T09:00:00Z", "updated": "2026-10-01T09:00:00Z"},
          {"number": "8", "title": "not a number", "up": 1, "created": "2026-10-01T09:00:00Z", "updated": "2026-10-01T09:00:00Z"}]



def gate_comment(verdict, kind, report):
    """CAT-33: a version of the gate comment as the comment job writes it (REV-2)."""
    head = {"new": [f"New entry; source tree: https://github.com/example/demo/tree/{'c' * 40}", ""],
            "update": [f"Code diff since the approved version: https://github.com/example/demo/compare/{'a' * 40}...{'c' * 40}", ""]}
    return "\n".join(["<!-- kadet-hub-gate -->", f"**gate: {verdict}** ([run](https://github.com/{OWNER}/registry/actions/runs/1))", ""]
                     + head.get(kind, []) + ["````", report, "````"])


# CAT-33: lines of the finding form the gate prints when the checks pass.
PASSING = ("## Registration\n## Sandbox compile\n### backend reclass-rs\nQA-6: tag kubernetes: compiled/t/cm.yml\nreview: REG-3: demo is one edit away from deno\n"
           "QA-7: validated against Calico 3.33.0\nQA-10: validated against kube-apiserver v1.37.1: 1 built-in documents, 0 skipped\n"
           "SEC-12: declared admission: a ValidatingWebhookConfiguration\n### krab\nCMP-4: krab compatible\n## Output diff\n"
           "SEC-13: output diff against the approved version: 1 files, 1 hunks")
# CAT-33: pull requests as the build writes them, with comments and pull requests view.py does not count.
GATE = [
    {"number": 1, "files": ["generators/demo.yaml"], "comments": [{"author": "github-actions", "versions": [
        gate_comment("passed", "new", PASSING),
        gate_comment("failed", "new", "## Static checks\nguarddog: threat-filesystem-destruction: 1\n" + PASSING),
        gate_comment("failed", None, "REG-1: tag v1.0.0 resolves to nothing, entry pins " + "c" * 40)]}]},
    {"number": 2, "files": ["generators/demo.yaml"], "comments": [
        {"author": "renovate", "versions": ["looks good"]},
        {"author": "github-actions", "versions": [gate_comment("failed", "update", (
            "REG-1: tag v1.1.0 resolves to nothing, entry pins " + "c" * 40 + "\nSEC-3: <script>alert(6)</script>\nXSS-1: no gate requirement\n"
            "QA-6: tag helm: no chart in the manifest and no helm template in binaries\nQA-10: compiled/t/d.yml: Deployment d: unknown field\n"
            + PASSING.replace("CMP-4", "CMP-5: output differs with --cache on omegaconf:\nCMP-4")
            + "\nSEC-13: the approved version's compile reported, not judged:\nQA-11: compiled/t/x.yml: X x: rejected"))]}]},
    {"number": 3, "files": ["generators/old.yaml"], "comments": [{"author": "github-actions", "versions": [
        gate_comment("failed", None, "## Registration\nREG-9: removing old must add it to policy/reserved-names.txt")]}]},
    {"number": 4, "files": ["catalog/view.py", "generators/README.md"], "comments": [{"author": "github-actions", "versions": [
        gate_comment("failed", None, "GI-2: one entry per pull request")]}]},
    {"number": 5, "files": ["generators/evil.yaml"], "comments": [{"author": "mallory", "versions": [gate_comment("failed", "new", "SEC-9: forged")]}]},
    {"number": 6, "files": ["generators/plain.yaml"], "comments": [{"author": "github-actions", "versions": [
        gate_comment("passed", "update", PASSING), "<!-- kadet-hub-gate --> no newline"]}]},
    {"number": 7, "files": ["generators/plain.yaml"], "comments": []},
    "x", {"number": 8}, {"number": 9, "files": "generators/a.yaml", "comments": "x"},
]


README = """# Demo

Intro with <script>alert(2)</script> raw HTML and <b>bold</b>.

[docs](docs/usage.md) [site](https://example.org/x) [bad](javascript:alert(3)) [anchor](#usage)
[proto](//evil.example/x)

![diagram](img/arch.png)

## Usage

#### Skipped level

```yaml
parameters:
  demo: {}
```

| a | b |
|---|---|
| 1 | 2 |

{{< nonexistent >}} {{% nonexistent %}} {{< diagram name="x" >}}

`{{< inline >}}`
"""


# CAT-29: SBOM file names; only schemas/<group>/<kind>_<version>.json count.
SBOM_FILES = ["./README.md", "./schemas/sources.yaml", "./schemas/gateway.networking.k8s.io/httproute_v1.json",
              "./schemas/gateway.networking.k8s.io/httproute_v1beta1.json", "./schemas/core/configmap_v1.json",
              "./schemas/gateway.networking.k8s.io/crds/httproutes.yaml", "./schemas/terraform/hashicorp_aws_6.68.0.json",
              "./schemas/terraform/x_v1.json", "./schemas/<script>/x_v1.json", "./schemas/../evil_v1.json",
              "./schemas/apps/Deployment_v1.json", "./lib/schemas/apps/deployment_v1.json"]


def sbom(path, names):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"spdxVersion": "SPDX-2.3", "files": [{"fileName": n} for n in names]}, f)


def artifact(path, files):
    with tarfile.open(path, "w") as t:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, __import__("io").BytesIO(data))


# CAT-37: the recipe files as in kadet-hub/examples recipes/inventory/classes, a comment with markup.
RECIPE_GENERATORS = {"postgresql": ["cloudnative-pg"], "keycloak": ["cloudnative-pg", "certmanager", "keycloak"], "valkey": [],
                     "kafka": ["strimzi"], "rabbitmq": ["rabbitmq"], "external-dns-powerdns": []}


def recipe_classes(root):
    """Writes the classes of every recipe page under root (an assets/classes or inventory/classes directory)."""
    os.makedirs(os.path.join(root, "recipes", "lib"), exist_ok=True)
    pins = sorted({g for gs in RECIPE_GENERATORS.values() for g in gs} | {"kubernetes"})
    with open(os.path.join(root, "generators.yml"), "w", encoding="utf-8") as f:
        f.write("# pins\nparameters:\n  kapitan:\n    dependencies:\n" + "".join(
            f"      - type: oci\n        source: ghcr.io/{OWNER}/{g}:1.0.0@sha256:{'e' * 64}\n        output_path: lib/{g}\n" for g in pins))
    for g in pins:
        with open(os.path.join(root, "recipes", "lib", f"{g}.yml"), "w", encoding="utf-8") as f:
            f.write(f"# Compiles {g}.\nparameters:\n  kapitan:\n    compile:\n      - {{input_type: kadet, input_paths: [lib/{g}], output_path: {g}/}}\n")
    for name, gens in RECIPE_GENERATORS.items():
        with open(os.path.join(root, "recipes", f"{name}.yml"), "w", encoding="utf-8") as f:
            f.write(f"# {name} <script>alert(7)</script> in place of\n# a Bitnami chart.\nclasses:\n"
                    + "".join(f"  - recipes.lib.{g}\n" for g in ["kubernetes"] + gens) + f"\nparameters:\n  {name}: {{a: <b>}}\n")


def build(index, tmp, artifacts=None, sboms=None, rekor=None, discussions=None, pages=None, diffs=None, wanted=None, gate=None, recipes=None, capture=False):
    path = os.path.join(tmp, "index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f)
    out = os.path.join(tmp, "out")
    env = dict(os.environ, OWNER=OWNER, CATALOG_OFFLINE="1", CATALOG_ARTIFACTS=artifacts or os.path.join(tmp, "none"),
               CATALOG_SBOMS=sboms or os.path.join(tmp, "none"), CATALOG_REKOR=rekor or os.path.join(tmp, "none.json"),
               CATALOG_DISCUSSIONS=discussions or os.path.join(tmp, "none.json"),
               CATALOG_PAGES=pages or os.path.join(tmp, "none"), CATALOG_DIFFS=diffs or os.path.join(tmp, "none"),
               CATALOG_WANTED=wanted or os.path.join(tmp, "none.json"), CATALOG_GATE=gate or os.path.join(tmp, "none.json"))
    if recipes is None:
        recipes = os.path.join(tmp, "recipes")
        recipe_classes(os.path.join(recipes, "inventory", "classes"))
    env["CATALOG_RECIPES"] = recipes
    subprocess.run([os.path.join(HERE, "build"), path, out], env=env, check=True, capture_output=capture, text=capture)
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
        sbom(os.path.join(sboms, "1.10.0.spdx.json"), SBOM_FILES)
        sbom(os.path.join(cls.tmp.name, "sboms", "plain", "0.2.0.spdx.json"),  # no kinds record: the SBOM's schemas
             ["./schemas/core/configmap_v1.json", "./schemas/gateway.networking.k8s.io/httproute_v1.json"])
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
        diffs = os.path.join(cls.tmp.name, "diffs", "demo")
        os.makedirs(diffs)
        with open(os.path.join(diffs, "1.10.0.output.diff"), "w", encoding="utf-8", newline="") as f:
            f.write(DIFF)
        wanted = os.path.join(cls.tmp.name, "wanted.json")
        with open(wanted, "w", encoding="utf-8") as f:
            json.dump(WANTED, f)
        gate = os.path.join(cls.tmp.name, "gate.json")
        with open(gate, "w", encoding="utf-8") as f:
            json.dump(GATE, f)
        cls.out = build(SITE_INDEX, cls.tmp.name, arts, os.path.dirname(sboms), rekor, discussions, pages, os.path.dirname(diffs), wanted, gate)

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
        self.assertIn(f"source: ghcr.io/{OWNER}/demo:1.10.0@sha256:{'b' * 64}", html)
        self.assertIn(f"gh attestation verify \\\n  oci://ghcr.io/{OWNER}/demo@sha256:{'b' * 64}", html)
        self.assertIn(f"https://github.com/{OWNER}/registry/.github/workflows/release.yml@refs/heads/main", html)
        self.assertLess(html.index(">1.10.0"), html.index(">1.2.0"))

    def test_yanked_version_shows_reason_and_no_entry(self):
        html = self.page("generators", "demo")
        self.assertIn("Yanked: broken", html)
        self.assertIn(f"https://github.com/{OWNER}/registry/security/advisories/GHSA-2345-6789-cfgh", html)
        self.assertIn(f"<code>sha256:{'a' * 64}</code>", html)
        self.assertNotIn(f"sha256:{'a' * 64}\n        output_path", html)
        self.assertNotIn('data-name="old"', self.page())  # CAT-26

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
        self.assertIn("<p>{{&lt; nonexistent &gt;}} {{% nonexistent %}} {{&lt; diagram name=&ldquo;x&rdquo; &gt;}}</p>", html)  # no shortcode call
        self.assertIn("<code>{{\\&lt; inline &gt;}}</code>", html)  # the escape shows in code
        self.assertNotIn("Old readme", self.page("generators", "old"))  # every version yanked

    def test_tags_link_to_the_tag_page(self):
        self.assertIn('href="../../tags/helm/"', self.page("generators", "demo"))
        home = self.page()
        self.assertIn('href="./tags/helm/"', home)
        self.assertIn('data-tag="helm" aria-pressed="false"', home)
        for html in [*self.pages(), self.page("tags"), self.page("tags", "helm")]:
            self.assertNotRegex(html, r'href="[^"]*\?tags=')

    def test_images_have_alt_and_touch_icon(self):
        for html in [*self.pages(), self.page("tags"), self.page("privacy")]:
            for img in re.findall(r"<img\b[^>]*>", html):
                self.assertRegex(img, r'alt="[^"]+"', img)
            self.assertRegex(html, r'<link rel="apple-touch-icon" href="[^"]*apple-touch-icon.png">')
        self.assertTrue(os.path.exists(os.path.join(self.out, "apple-touch-icon.png")))

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
        self.assertIn('href="../tags/helm/">1 generator tagged helm</a>', page)
        self.assertIn("No generator tagged ci yet.", page)
        home = self.page()
        self.assertIn('data-tag="helm" aria-pressed="false" title="Renders a Helm chart or builds on one."><svg class="icon" aria-hidden="true"><use href="#i-tag-helm"/></svg>helm <span class="count">(1)</span>', home)
        self.assertIn('href="./tags/"', home)
        glossary = self.page("glossary")
        self.assertIn('href="https://kapitan.dev/"', glossary)
        self.assertIn('id="index"', glossary)

    def test_glossary(self):  # CAT-13a
        html = self.page("glossary")
        terms = re.findall(r'<dt id="([^"]*)">([^<]*)</dt>', html)
        ids = [i for i, _ in terms]
        self.assertGreaterEqual(len(ids), 23)
        self.assertEqual(len(ids), len(set(ids)))
        for i in ids:
            self.assertRegex(i, r"^[a-z]+(-[a-z]+)*$")
        ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        (terms_ld,) = [b for b in ld if b.get("@type") == "DefinedTermSet"]
        self.assertEqual([(t["@type"], t["url"], t["name"]) for t in terms_ld["hasDefinedTerm"]],
                         [("DefinedTerm", f"https://kadet-hub.org/glossary/#{i}", n) for i, n in terms])
        for t in terms_ld["hasDefinedTerm"]:
            self.assertTrue(t["description"], t["name"])
            self.assertNotRegex(t["description"], r"</?(?:a|code)\b|&\w+;", t["name"])  # plain text
        for other in ("index.html", os.path.join("generators", "demo", "index.html")):
            with open(os.path.join(self.out, other), encoding="utf-8") as f:
                self.assertNotIn("DefinedTermSet", f.read())
        title = re.search(r"<title>(.*?)</title>", html).group(1)
        desc = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        for text in (title, desc):  # CAT-11a
            self.assertIn("Kapitan", text)
            self.assertIn("Kubernetes", text)
        linked = set()
        for root, _, files in os.walk(self.out):
            for name in files:
                if name == "index.html" and os.path.relpath(root, self.out) != "glossary":
                    with open(os.path.join(root, name), encoding="utf-8") as f:
                        linked.update(re.findall(r'href="[^"]*glossary/#([a-z-]+)"', f.read()))
        self.assertEqual(sorted(set(ids) - linked), [])
        self.assertEqual(sorted(linked - set(ids)), [])

    def test_legal_pages_and_notices(self):
        for html in self.pages():
            self.assertIn("not affiliated with or endorsed by the Kapitan project or kapicorp", html)
            self.assertIn("as is and on a best-effort basis: use at your own risk", html)
            for href in ("privacy/", "imprint/", "registry/blob/main/TERMS.md", "SECURITY.md#removal-requests"):
                self.assertIn(href, html)
        demo = self.page("generators", "demo")
        versions = demo[demo.index('id="versions"'):demo.index('id="v1.10.0"')]
        self.assertIn("use at your own risk", versions)
        privacy = self.page("privacy")
        self.assertIn("GitHub Pages", privacy)
        self.assertIn("localStorage", privacy)
        self.assertIn("Art. 77", privacy)
        self.assertIn("§ 5 DDG", self.page("imprint"))
        imprint = self.page("imprint")
        for heading in ("Consumer dispute resolution", "Liability for content", "Liability for links", "Copyright"):  # LEG-1a
            self.assertIn(f">{heading}</h2>", imprint)
        self.assertIn("§ 36 VSBG", imprint)
        with open(os.path.join(HERE, "..", "README.md"), encoding="utf-8") as f:
            self.assertIn("not affiliated with or endorsed by\nthe Kapitan project or kapicorp", f.read())

    def test_scan_record_and_sbom(self):
        html = self.page("generators", "demo")
        latest = html[html.index('id="v1.10.0"'):html.index('id="v1.2.0"')]
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

    def test_output_diff(self):  # CAT-27
        html = self.page("generators", "demo")
        latest = html[html.index('id="v1.10.0"'):html.index('id="v1.2.0"')]
        self.assertIn('Fixture output against <a href="#v1.2.0">1.2.0</a>: 1 file, 1 hunk.', latest)
        code = re.search(r'<pre class="diff"><code>(.*?)</code></pre>', latest, re.S).group(1)
        self.assertIn("-&lt;script&gt;alert(4)&lt;/script&gt;", code)  # text, not markup
        self.assertNotIn("<", code)
        clean = DIFF.replace("\x1b", "").replace("\u202e", "").replace("\r", "")
        self.assertEqual(_unescape(code), "\n".join(clean.split("\n")[:150]))  # control characters removed, 150 lines
        self.assertIn("Truncated after 150 lines; 50 more in the download.", latest)
        self.assertIn('href="../../generators/demo/1.10.0.output.diff" download', latest)
        with open(os.path.join(self.out, "generators", "demo", "1.10.0.output.diff"), encoding="utf-8", newline="") as f:
            self.assertEqual(f.read(), DIFF)  # the attested text unchanged
        older = html[html.index('id="v1.2.0"'):html.index('id="v1.0.0"')]
        self.assertIn("No output diff recorded", older)
        self.assertIn("No output diff: no earlier listed version.", self.page("generators", "plain"))
        with tempfile.TemporaryDirectory() as tmp:  # a record without a verified text
            with open(os.path.join(build({"serial": 1, "generators": {"g": {"1.0.0": dict(record("e"), output_diff=OUTPUT_DIFF)}}}, tmp),
                                   "generators", "g", "index.html"), encoding="utf-8") as f:
                page = f.read()
        self.assertIn("The diff text has no verified attestation.", page)
        self.assertNotIn("output.diff", page)

    def test_llms_txt(self):  # CAT-16
        with open(os.path.join(self.out, "llms.txt"), encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("# kadet-hub\n\n> "))
        for link in ("generator-template/blob/main/AGENTS.md", "docs/authors.md", "policy/imports.txt", "policy/tags.yaml", "kadet-hub.org/glossary/"):
            self.assertIn(link, text)
        self.assertEqual(re.findall(r"(?m)^## (.+)$", text)[-4:], ["Generators", "Guides", "Recipes", "Optional"])
        self.assertIn("\n- [Kafka on Kubernetes without Bitnami, with Kapitan](https://kadet-hub.org/recipes/kafka/index.md): Bitnami kafka Helm chart alternative: a Kapitan", text)  # CAT-37b
        self.assertEqual(text.count("](https://kadet-hub.org/recipes/"), len(RECIPE_GENERATORS))
        self.assertIn("\n- [demo](https://kadet-hub.org/generators/demo/index.md): <script>alert(1)</script>\n", text)  # text, as typed
        self.assertIn("\n- [plain](https://kadet-hub.org/generators/plain/index.md): Renders a [ConfigMap](x) ## Not a heading 31m*bold*\n", text)
        self.assertNotIn("generators/old/", text)  # CAT-26: no listed version
        self.assertIn("\n- [Writing a Kapitan generator](https://kadet-hub.org/guides/writing-a-kapitan-generator/index.md): How to write a reusable", text)
        self.assertEqual(text.count("](https://kadet-hub.org/guides/"), 11)
        self.assertIn("\n- [Kinds](https://kadet-hub.org/kinds/): ", text)  # CAT-29: the index, not kind pages
        self.assertIn("\n- [Compatibility](https://kadet-hub.org/compatibility/): ", text)  # CAT-30
        self.assertIn("\n- [Wanted generators](https://kadet-hub.org/wanted/): ", text)  # CAT-31
        self.assertIn("\n- [Statistics](https://kadet-hub.org/stats/): ", text)  # CAT-33
        self.assertNotIn("kinds/gateway", text)

    def markdown(self, *parts):
        with open(os.path.join(self.out, *parts, "index.md"), encoding="utf-8") as f:
            return f.read()

    def test_markdown_variants(self):  # CAT-28
        demo, html = self.markdown("generators", "demo"), self.page("generators", "demo")
        self.assertTrue(demo.startswith("# demo\n\n> <script>alert(1)</script>\n\n- Latest version: 1.10.0, published 2026-10-09\n"))
        self.assertIn("\n- Built for (schema-checked): External Secrets Operator 2.11.0\n", demo)
        self.assertIn("\n- Page: https://kadet-hub.org/generators/demo/\n", demo)
        for block in ("entry-0", "verify-0"):  # the latest version's entry and command, as on the page
            text = _unescape(re.search(rf'<pre id="{block}"><code>(.*?)</code></pre>', html, re.S).group(1))
            self.assertIn(f"\n```{'yaml' if block == 'entry-0' else 'sh'}\n{text}\n```\n", demo)
        self.assertIn(f"Relative links in the README resolve against https://github.com/example/demo/blob/{'c' * 40}/.\n\n" + README, demo)
        self.assertTrue(self.markdown("generators", "plain").startswith("# plain\n\n> Renders a [ConfigMap](x) ## Not a heading 31m*bold*\n"))
        self.assertEqual(self.markdown("generators", "old"), "# old\n\nNo listed version; every version is yanked:\n\n- 0.1.0: entry removed\n\n"
                                                             "Page: https://kadet-hub.org/generators/old/\n")
        with open(os.path.join(HERE, "site", "content", "guides", "writing-a-kapitan-generator.md"), encoding="utf-8") as f:
            body = f.read().split("---\n", 2)[2]
        self.assertEqual(self.markdown("guides", "writing-a-kapitan-generator"), f"# Writing a Kapitan generator\n\n{body.strip()}\n")
        for parts in ((), ("guides",), ("tags", "helm"), ("privacy",), ("kinds",), ("compatibility",)):
            self.assertFalse(os.path.exists(os.path.join(self.out, *parts, "index.md")), parts)
        with open(os.path.join(self.out, "sitemap.xml"), encoding="utf-8") as f:
            self.assertNotIn(".md<", f.read())

    def test_built_for(self):
        self.assertIn('<dt>Built for</dt><dd class="built-for"><span>External Secrets Operator 2.11.0</span></dd>', self.page())
        html = self.page("generators", "demo")
        self.assertIn('<a href="https://github.com/external-secrets/external-secrets/tree/v2.11.0/config/crds/bases">External Secrets Operator 2.11.0</a>', html)
        older = html[html.index('id="v1.2.0"'):html.index('id="v1.0.0"')]
        self.assertIn("<dt>Built for (schema-checked)</dt><dd>not recorded</dd>", older)

    def test_compatibility_page(self):  # CAT-30, CAT-26, CAT-9
        page = self.page("compatibility")
        self.assertEqual(re.findall(r'<tr id="([^"]+)">', page), ["demo", "plain"])  # old has no listed version
        self.assertIn('<thead><tr><th scope="col">Generator</th><th scope="col">Kapitan declared</th><th scope="col">Kapitan checked</th>'
                      '<th scope="col">Backends checked</th><th scope="col">With --cache</th><th scope="col">krab</th>'
                      '<th scope="col">Built for (schema-checked)</th></tr></thead>', page)
        self.assertIn('<tr id="demo"><th scope="row"><a href="../generators/demo/#v1.10.0">demo</a> 1.10.0</th>'
                      '<td data-label="Kapitan declared">&gt;=0.36.3,&lt;0.37</td><td data-label="Kapitan checked">0.36.3</td>'
                      '<td data-label="Backends checked">reclass-rs, omegaconf</td><td data-label="With --cache">passed</td>'
                      '<td data-label="krab">compatible</td><td data-label="Built for (schema-checked)"><a href="https://github.com/'
                      'external-secrets/external-secrets/tree/v2.11.0/config/crds/bases">External Secrets Operator 2.11.0</a></td></tr>', page)
        plain = re.search(r'<tr id="plain">.*?</tr>', page).group(0)  # no scan, backends, krab or compatibility record
        self.assertEqual(re.findall(r'<td data-label="[^"]+">([^<]*)</td>', plain), [">=0.36.3,<0.37".replace(">", "&gt;").replace("<", "&lt;")]
                         + ["not recorded"] * 5)
        self.assertIn('<section class="prose-page prose wide">', page)  # .prose tables wrap
        with open(os.path.join(self.out, "style.css"), encoding="utf-8") as f:
            css = f.read()
        self.assertRegex(css, r"@media \(max-width: 60rem\) \{[^@]*\.compat tr, \.compat th, \.compat td \{ display: block; \}")
        self.assertRegex(css, r"\.compat td::before \{ content: attr\(data-label\)")
        for html in self.pages() + [page]:
            self.assertRegex(html, r'(?s)<nav>.*<a href="[./]*compatibility/">Compatibility</a>.*</nav>')
            self.assertRegex(html, r'(?s)<nav>.*<a href="[./]*recipes/">Recipes</a>.*</nav>')  # CAT-37

    def test_compatibility_facts_are_the_same_on_page_details_and_markdown(self):  # CAT-30, CAT-28
        def text(h):
            return _unescape(re.sub(r"<[^>]+>", "", h.replace("<br>", ", ")))
        facts = [("Kapitan declared", ">=0.36.3,<0.37"), ("Kapitan checked", "0.36.3"), ("Backends checked", "reclass-rs, omegaconf"),
                 ("With --cache", "passed"), ("krab", "compatible"), ("Built for (schema-checked)", "External Secrets Operator 2.11.0")]
        row = re.search(r'<tr id="demo">.*?</tr>', self.page("compatibility")).group(0)
        self.assertEqual([(k, text(v)) for k, v in re.findall(r'<td data-label="([^"]+)">(.*?)</td>', row)], facts)
        html = self.page("generators", "demo")
        latest = html[html.index('id="v1.10.0"'):html.index('id="v1.2.0"')]
        self.assertEqual([(k, text(v)) for k, v in re.findall(r"<dt>([^<]+)</dt><dd>(.*?)</dd>", latest)[:6]], facts)
        self.assertIn("".join(f"- {k}: {v}\n" for k, v in facts), self.markdown("generators", "demo"))
        older = html[html.index('id="v1.2.0"'):html.index('id="v1.0.0"')]
        for label in ("Kapitan checked", "Backends checked", "With --cache", "krab"):
            self.assertIn(f"<dt>{label}</dt><dd>not recorded</dd>", older)

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
        for slug in ("writing-a-kapitan-generator", "generator-helm-or-jinja2", "supply-chain-security-for-kapitan-generators",
                     "checking-custom-resources-against-crds", "ingress-nginx-to-gateway-api", "how-kadet-hub-works",
                     "bitnami-chart-alternatives", "helm-alternatives-for-kubernetes", "talos-machine-config", "helm-vs-terraform", "argocd-vs-flux"):
            self.assertIn(f"guides/{slug}/", guides)
            self.page("guides", slug)
        self.assertIn('<h2 id="generator-contract">Generator contract</h2>', self.page("guides", "writing-a-kapitan-generator"))  # CAT-24

    def test_recipes(self):  # CAT-37, CAT-37b
        index = self.page("recipes")
        self.assertEqual(sorted(re.findall(r'<li><a href="[./]*recipes/([^/]+)/">', index)), sorted(RECIPE_GENERATORS))
        self.assertIn("<title>Bitnami chart replacements on Kubernetes with Kapitan</title>", index)  # CAT-11a
        self.assertIn("<title>PostgreSQL on Kubernetes without Bitnami, with Kapitan</title>", self.page("recipes", "postgresql"))  # no room for the suffix
        page = self.page("recipes", "keycloak")
        self.assertIn("<title>Keycloak on Kubernetes without Bitnami, with Kapitan · kadet-hub</title>", page)
        self.assertIn('<p class="lead">keycloak &lt;script&gt;alert(7)&lt;/script&gt; in place of a Bitnami chart.</p>', page)
        self.assertNotIn("<script>alert(7)", page)
        self.assertIn("<li>Replaces the Bitnami charts: <code>keycloak</code></li>", page)
        self.assertIn('<li>Generators: <a href="../../generators/kubernetes/">kubernetes</a>, <a href="../../generators/cloudnative-pg/">cloudnative-pg</a>, '
                      '<a href="../../generators/certmanager/">certmanager</a>, <a href="../../generators/keycloak/">keycloak</a></li>', page)
        self.assertIn("<li>Operators: Keycloak Operator, CloudNativePG, cert-manager</li>", page)
        with open(os.path.join(self.tmp.name, "recipes", "inventory", "classes", "recipes", "keycloak.yml"), encoding="utf-8") as f:
            cls = f.read()
        self.assertIn(f'<pre id="class"><code>{cls.replace("<", "&lt;").replace(">", "&gt;")}</code></pre>', page)
        pins = _unescape(re.search(r'<pre id="pins"><code>(.*?)</code></pre>', page, re.S).group(1))
        self.assertEqual(re.findall(r"output_path: lib/(\S+)", pins), ["certmanager", "cloudnative-pg", "keycloak", "kubernetes"])
        self.assertNotIn("strimzi", pins)
        self.assertIn('<pre id="lib-3"><code># Compiles keycloak.', page)
        self.assertIn(f'<a href="https://github.com/{OWNER}/examples/blob/main/recipes/tests/keycloak/chainsaw-test.yaml">', page)
        self.assertIn(f'<a href="https://github.com/{OWNER}/examples/tree/main/recipes">kadet-hub/examples</a>', page)
        self.assertIn("fails unless the Keycloak is <code>Ready</code> and", page)
        self.assertIn('<li>Operators: none</li>', self.page("recipes", "valkey"))
        md = self.markdown("recipes", "keycloak")
        self.assertTrue(md.startswith("# Keycloak on Kubernetes without Bitnami, with Kapitan\n\n> keycloak <script>"))
        self.assertIn(f"\n## inventory/classes/recipes/keycloak.yml\n\n```yaml\n{cls.strip()}\n```\n", md)
        self.assertIn("\n## inventory/classes/recipes/lib/strimzi.yml\n", self.markdown("recipes", "kafka"))
        self.assertFalse(os.path.exists(os.path.join(self.out, "recipes", "index.md")))
        guide = self.page("guides", "bitnami-chart-alternatives")
        for name in RECIPE_GENERATORS:
            self.assertIn(f'href="../../recipes/{name}/"', guide)
        with open(os.path.join(self.out, "sitemap.xml"), encoding="utf-8") as f:
            self.assertIn("https://kadet-hub.org/recipes/kafka/<", f.read())

    def test_recipe_file_missing_fails_the_build(self):  # CAT-37a
        with tempfile.TemporaryDirectory() as tmp:
            recipes = os.path.join(tmp, "recipes")
            recipe_classes(os.path.join(recipes, "inventory", "classes"))
            os.remove(os.path.join(recipes, "inventory", "classes", "recipes", "lib", "strimzi.yml"))
            with self.assertRaises(subprocess.CalledProcessError) as failed:
                build({"serial": 1, "generators": {}}, tmp, recipes=recipes, capture=True)
            self.assertIn("strimzi", failed.exception.stderr)  # CAT-1: Hugo's error is printed

    def test_blog(self):  # CAT-36
        slug = "kapitan-generators-as-supply-chain-artifacts"
        blog = self.page("blog")
        self.assertIn(f'<a href="../blog/{slug}/">Kapitan generators as supply-chain artifacts</a> <time datetime="2026-10-17">', blog)
        self.assertIn('<link rel="alternate" type="application/atom+xml" title="kadet-hub blog" href="../blog/index.xml">', blog)
        self.assertIn("<title>Kapitan on Kubernetes: a first platform from four generators</title>", self.page("blog", "first-platform"))  # CAT-11a
        post = self.page("blog", slug)
        self.assertIn('<time datetime="2026-10-17">17 October 2026</time>', post)
        self.assertIn('<a href="../../guides/checking-custom-resources-against-crds/">', post)  # internal, so no rel=nofollow
        self.assertNotIn('<link rel="alternate" type="application/atom+xml" title="kadet-hub blog"', self.page("guides"))
        self.assertTrue(self.markdown("blog", slug).startswith("# Kapitan generators as supply-chain artifacts\n\n[Kapitan](/glossary/#kapitan)'s [kadet](/glossary/#kadet)"))
        with open(os.path.join(self.out, "blog", "index.xml"), encoding="utf-8") as f:
            feed = __import__("xml.dom.minidom").dom.minidom.parseString(f.read())
        self.assertIn(f"https://kadet-hub.org/blog/{slug}/", [e.getElementsByTagName("id")[0].firstChild.data for e in feed.getElementsByTagName("entry")])
        with open(os.path.join(self.out, "index.xml"), encoding="utf-8") as f:
            self.assertNotIn("/blog/", f.read())  # the release feed stays as it is
        self.assertIn('href="../blog/"', self.page("guides"))

    def test_blog_post_page(self):  # CAT-36a
        post = self.page("blog", "kapitan-generators-as-supply-chain-artifacts")
        self.assertRegex(post, r'<p class="byline">By <a href="https://github.com/[^"]+">kadet-hub maintainers</a> · Published <time datetime="2026-10-17">17 October 2026</time> · \d+ min read</p>')
        self.assertIn('<meta property="og:type" content="article">', post)
        ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', post, re.S)]
        self.assertEqual([(b["@type"], b["datePublished"], b["author"]["@type"]) for b in ld], [("BlogPosting", "2026-10-17T00:00:00Z", "Organization")])
        self.assertIn('<h2 id="what-a-version-goes-through">What a version goes through <a class="anchor" href="#what-a-version-goes-through" aria-label="Link to What a version goes through"></a></h2>', post)  # "#" only from CSS
        self.assertIn('/registry/blob/main/catalog/site/content/blog/kapitan-generators-as-supply-chain-artifacts.md">Edit this post</a>', post)
        self.assertNotIn('class="anchor"', self.page("guides", "writing-a-kapitan-generator"))
        self.assertIn('<meta property="og:type" content="website">', self.page("blog"))
        with tempfile.TemporaryDirectory() as tmp:  # a second, longer post with code: copy button, contents, pager, related
            site = os.path.join(tmp, "site")
            shutil.copytree(os.path.join(HERE, "site"), site)
            body = "\n\n".join(f"## Part {i}\n\n" + "word " * 150 for i in range(6))
            with open(os.path.join(site, "content", "blog", "second.md"), "w", encoding="utf-8") as f:
                f.write("---\ntitle: A second post on the gate\ndate: 2000-01-01\nlastmod: 2000-01-03\ntopics: [gate]\n"
                        "description: A second post for the test of the post page, with code and enough words for contents.\n---\n\n"
                        f"{body}\n\n```bash\necho hi\n```\n")
            os.makedirs(os.path.join(site, "data"))
            shutil.copy(os.path.join(HERE, "..", "policy", "tags.yaml"), os.path.join(site, "data", "tags.yaml"))
            recipe_classes(os.path.join(site, "assets", "classes"))
            with open(os.path.join(site, "data", "catalog.json"), "w", encoding="utf-8") as f:
                json.dump(view(INDEX, OWNER, lambda _: None), f)
            subprocess.run(["hugo", "--quiet", "--source", site, "--destination", os.path.join(tmp, "out")], check=True)
            with open(os.path.join(tmp, "out", "blog", "second", "index.html"), encoding="utf-8") as f:
                second = f.read()
            with open(os.path.join(tmp, "out", "blog", "kapitan-generators-as-supply-chain-artifacts", "index.html"), encoding="utf-8") as f:
                first = f.read()
            with open(os.path.join(tmp, "out", "guides", "writing-a-kapitan-generator", "index.html"), encoding="utf-8") as f:
                guide = f.read()
        self.assertIn('· Updated <time datetime="2000-01-03">3 January 2000</time>', second)
        self.assertIn('<summary><h2 id="toc">On this page</h2></summary>', second)
        self.assertNotIn('id="toc"', first)  # under 800 words
        self.assertRegex(second, r'<div class="snippet"><div id="code-0"><div class="highlight"><pre[^>]*><code class="language-bash"')
        self.assertIn('data-copy="code-0"', second)
        self.assertNotIn('class="snippet"><div id="code-', guide)
        self.assertIn('<a rel="next" href="../../blog/', second)  # the oldest post has a newer one
        self.assertNotIn('rel="prev"', second.split('class="pager"')[1])
        self.assertIn('rel="prev"', first.split('class="pager"')[1])
        self.assertIn('<h2 id="related">Related posts</h2>', first)  # shares the topic gate

    def test_how_kadet_hub_works(self):  # CAT-35, CAT-35a, CAT-28, CAT-11b
        html = self.page("guides", "how-kadet-hub-works")
        main = html[html.index("<main"):html.index("</main>")]
        figures = re.findall(r'<figure class="diagram" role="img" aria-labelledby="diagram-([a-z]+)-title" aria-describedby="diagram-\1-desc">'
                             r'<svg\b[^>]*>\s*<title id="diagram-\1-title">[^<]+</title><desc id="diagram-\1-desc">[^<]+</desc>', main)
        self.assertEqual(figures, ["overview", "listing", "release", "consuming", "upstream", "withdraw"])
        for name in figures[1:]:  # every process: its diagram, then its steps
            after = main.split(f'aria-labelledby="diagram-{name}-title"')[1].split("</figure>", 1)[1]
            self.assertTrue(after.lstrip().startswith("<ol>"), name)
        self.assertNotRegex(main, r"<style\b| style=|<\?xml|<!DOCTYPE")
        table = main[main.index("<table>"):main.index("</table>")]
        self.assertIn(">REG-1 to REG-6, REG-8</a>", table)
        text = re.sub(r"<[^>]+>", " ", main.replace(table, ""))  # requirement IDs only in the stage table
        self.assertNotRegex(text, r"\b(?:GI|REG|SEC|QA|CMP|PUB|CON|CAT|UPD|INC|DEC)-\d")
        md = self.markdown("guides", "how-kadet-hub-works")
        self.assertTrue(md.startswith("# How kadet-hub works\n\nA [generator](/glossary/#generator) lives in its author's repository."))
        self.assertRegex(md, r"\n## Listing a new generator\n+1\. The author creates a repository from\n")
        for gone in ("{{", "<svg", "<figure", 'name="'):
            self.assertNotIn(gone, md)
        listing = self.page()[self.page().index('<h2 id="listing">'):]
        self.assertIn('<a href="./guides/how-kadet-hub-works/">How kadet-hub works</a>', listing.split("<h3>")[0])

    def test_version_permalinks_and_transparency_log(self):
        html = self.page("generators", "demo")
        for v in ("1.10.0", "1.2.0", "1.0.0"):
            self.assertIn(f'id="v{v}"', html)
            self.assertIn(f'<a class="permalink" href="#v{v}" aria-label="Link to version {v}">#</a>', html)
        self.assertIn('href="https://search.sigstore.dev/?logIndex=3202022821">Rekor entry 3202022821</a>', html)
        self.assertIn('href="https://search.sigstore.dev/?logIndex=17">Rekor entry 17</a>', html)  # yanked keeps its entry
        self.assertNotIn("not-a-number", html)
        newest = html[html.index('id="v1.10.0"'):html.index('id="v1.2.0"')]
        self.assertIn("gh attestation verify \\\n  oci://ghcr.io/kadet-hub/demo@sha256:", newest)
        self.assertIn("\n  --owner kadet-hub \\\n  --cert-identity https://", newest)
        for gone in ('id="install"', 'id="verify"', 'id="checks"', 'id="details"'):
            self.assertNotIn(gone, html)  # CAT-19: the newest version is shown once, under Versions
        self.assertEqual(html.count("gh attestation verify \\\n  oci://ghcr.io/kadet-hub/demo@sha256:" + "b" * 64), 1)

    def test_one_column_with_table_of_contents(self):
        html = self.page("generators", "demo")
        self.assertNotIn("<aside", html)
        self.assertIn('<nav class="toc" aria-labelledby="toc">\n<details open>', html)  # open without JavaScript
        self.assertLess(html.index('class="toc"'), html.index('class="generator-body"'))  # beside the column, not in it
        start = html.index('id="toc"')
        toc = html[start:html.index("</nav>", start)]
        links = ["readme", "versions"]
        self.assertEqual(re.findall(r'href="#([a-z]+)"', toc), links)
        positions = [html.index(f'id="{a}"') for a in links]
        self.assertEqual(positions, sorted(positions))
        old = self.page("generators", "old")  # every version yanked: no readme
        self.assertEqual(re.findall(r'href="#([a-z]+)"', old[old.index('id="toc"'):old.index("</nav>", old.index('id="toc"'))]), ["versions"])

    def card(self, name):
        home = self.page()
        start = home.index(f'data-name="{name}"')
        return home[start:home.index("</li>", start)]

    def test_cards_show_the_same_fields_in_the_same_order(self):
        for name in ("demo", "plain"):
            card = self.card(name)
            order = ['class="stretched"', 'class="meta-line"', 'class="description"',
                     "<dt>Built for</dt>", "<dt>Maintainer</dt>", "<dt>Popularity</dt>", "<dt>Scanned</dt>"]
            positions = [card.index(marker) for marker in order]
            self.assertEqual(positions, sorted(positions), name)
            self.assertNotIn("Apache-2.0", card)  # CAT-22: license only on the page
            self.assertEqual(card.count("<a "), 1 + card.count('class="tag"') + card.count('class="fact-link"'))
        self.assertIn("<dt>Built for</dt><dd>not recorded</dd>", self.card("plain"))
        self.assertIn("<dt>Scanned</dt><dd>not scanned</dd>", self.card("plain"))
        self.assertIn('<p class="meta-line">1.10.0 · <time datetime="2026-10-09T05:34:57Z">2026-10-09</time></p>', self.card("demo"))

    def test_maintainer_is_text_on_the_card_and_linked_on_the_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            site = os.path.join(tmp, "site")
            shutil.copytree(os.path.join(HERE, "site"), site)
            os.makedirs(os.path.join(site, "data"))
            shutil.copy(os.path.join(HERE, "..", "policy", "tags.yaml"), os.path.join(site, "data", "tags.yaml"))
            recipe_classes(os.path.join(site, "assets", "classes"))
            with open(os.path.join(site, "data", "catalog.json"), "w", encoding="utf-8") as f:
                json.dump(view(INDEX, OWNER, {"/user/331675722": {"login": "someone"}}.get), f)
            subprocess.run(["hugo", "--quiet", "--source", site, "--destination", os.path.join(tmp, "out")], check=True)
            with open(os.path.join(tmp, "out", "index.html"), encoding="utf-8") as f:
                home = f.read()
            with open(os.path.join(tmp, "out", "generators", "demo", "index.html"), encoding="utf-8") as f:
                page = f.read()
        self.assertIn('<dt>Maintainer</dt><dd>someone</dd>', home)  # CAT-22: linked only on the page
        self.assertIn('<dt>Owners</dt><dd><a href="https://github.com/someone">someone</a></dd>', page)

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
        own = dict(INDEX, generators={"g": {"1.0.0": dict(record("e"), source=dict(record("e")["source"], repo=f"https://github.com/{OWNER}/generators.git"))}})
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(build(own, tmp), "generators", "g", "index.html"), encoding="utf-8") as f:
                page = f.read()
        link = re.search(r'<a class="button" href="([^"]+)">Request a feature</a>', page).group(1)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(_unescape(link)).query)
        self.assertTrue(link.startswith(f"https://github.com/{OWNER}/generators/issues/new?"))
        self.assertEqual((query["template"], query["generator"], query["version"]), (["feature-request.yml"], ["g"], ["1.0.0"]))

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
                json.dump({"generators": [{"name": "demo", "latest": {"digest": digest}, "readme": "# Kept", "changelog": {"1.10.0": "- kept", "1.2.0": 1}},
                                          {"name": "big", "latest": {"digest": "sha256:x"}, "readme": "x" * (README_MAX + 1)}]}, f)
            previous = load_previous(prev)
        self.assertEqual(previous, {("demo", digest): {"readme": "# Kept", "changelog": {"1.10.0": "- kept"}}})  # oversized README dropped
        g = view(INDEX, OWNER, lambda _: None, previous=previous)["generators"][0]
        self.assertEqual((g["readme"], g["changelog"]), ("# Kept", {"1.10.0": "- kept"}))  # CAT-36b
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

    def test_badge(self):  # CAT-32, CAT-32a
        for name, message, color in (("demo", "1.10.0", "blue"), ("old", "not listed", "lightgrey")):
            with open(os.path.join(self.out, "generators", name, "badge.json"), encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"schemaVersion": 1, "label": "kadet-hub", "message": message, "color": color})
        self.assertFalse(os.path.exists(os.path.join(self.out, "guides", "writing-a-kapitan-generator", "badge.json")))
        html = self.page("generators", "demo")
        section = html[html.index('<details class="badge-snippet">'):html.index("</details>", html.index('<details class="badge-snippet">'))]
        self.assertLess(html.index('<details class="badge-snippet">'), html.index('class="toc"'))  # below the actions, not a section
        code = _unescape(re.search(r'<pre id="badge-markdown"><code>(.*?)</code></pre>', section, re.S).group(1))
        self.assertEqual(code, "[![kadet-hub](https://img.shields.io/endpoint?url=https://kadet-hub.org/generators/demo/badge.json)]"
                               "(https://kadet-hub.org/generators/demo/)")
        self.assertIn('data-copy="badge-markdown"', section)
        self.assertNotIn("badge-snippet", self.page("generators", "old"))  # no listed version, no snippet
        for page in (html, self.page("generators", "old")):
            self.assertNotRegex(page, r"<img\b[^>]*shields")
            csp = re.search(r'Content-Security-Policy" content="([^"]*)"', page).group(1)
            self.assertEqual(csp, "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' https://stats.kadet-hub.org; "
                                  "connect-src https://stats.kadet-hub.org; base-uri 'none'; form-action 'none'")
        with open(os.path.join(self.out, "sitemap.xml"), encoding="utf-8") as f:
            self.assertNotIn("badge.json", f.read())

    def test_wanted_page(self):  # CAT-31, CAT-3
        page = self.page("wanted")
        items = re.findall(rf'<li><a href="https://github.com/{OWNER}/registry/issues/(\d+)">([^<]*)</a>', page)
        self.assertEqual(items, [("9", "loki"), ("4", "keycloak"), ("7", "&lt;script&gt;alert(5)&lt;/script&gt;[31m cert-manager")])
        self.assertIn('👍 5 · last activity <time datetime="2026-10-06T10:00:00Z">2026-10-06</time> · opened '
                      '<time datetime="2026-10-05T09:00:00Z">2026-10-05</time>', page)
        for gone in ("body text", "not a number", "<script>alert(5)", "\u202e", "\x1b"):
            self.assertNotIn(gone, page)
        self.assertIn('<a class="button" href="https://github.com/kadet-hub/registry/issues/new?template=generator-request.yml">Request a generator</a>'
                      '<a class="button" href="./wanted/">Wanted generators</a>', self.page())

    def test_wanted_page_without_requests(self):  # CAT-31
        texts = []
        for wanted in ([], None):
            with tempfile.TemporaryDirectory() as tmp:
                path = None
                if wanted is not None:
                    path = os.path.join(tmp, "wanted.json")
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(wanted, f)
                with open(os.path.join(build(INDEX, tmp, wanted=path), "wanted", "index.html"), encoding="utf-8") as f:
                    texts.append(f.read())
        empty, unread = texts
        self.assertIn("No generator request is open.", empty)
        self.assertIn(f'href="https://github.com/{OWNER}/registry/issues/new?template=generator-request.yml"', empty)
        self.assertIn("The open requests could not be read when this page was built.", unread)
        for page in texts:
            self.assertNotIn("<ol", page)

    def rows(self, page, section):
        """The rows of the tables in a section of a page, each as its cell texts."""
        part = page.split(f'<h2 id="{section}">')[1].split("<h2")[0]
        return [re.findall(r"<t[hd][^>]*>(?:<a [^>]*>)?([^<]*)", row) for row in re.findall(r"<tr>(.*?)</tr>", part)]

    def test_stats_page(self):  # CAT-33, CAT-3, CAT-25
        page = self.page("stats")
        self.assertRegex(page, r'<p>Built <time datetime="\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ">\d{4}-\d\d-\d\d \d\d:\d\d UTC</time> '
                               r"from index serial 7, the generators' package pages on GitHub and the gate's comments")
        self.assertEqual(self.rows(page, "pulls"), [["Generator", "Pulls"], ["demo", "1200"], ["old", "not read"], ["plain", "not read"],
                                                    ["All generators", "1200"]])
        self.assertIn('<a href="../generators/old/">old</a>', page)
        self.assertEqual(self.rows(page, "versions"), [["Month", "Versions published", "Of these yanked"], ["2026-10", "4", "2"], ["2026-09", "1", "0"]])
        self.assertEqual(self.rows(page, "gate"), [
            ["Entry pull requests", "With a gate result", "Rejected at least once"],
            ["New entries", "1", "1"], ["Updates", "2", "1"], ["Other, such as removals", "1", "1"], ["All", "4", "3"],
            ["Requirement", "Rejected pull requests"],
            ["REG-1", "2"], ["CMP-5", "1"], ["QA-6", "1"], ["QA-10", "1"], ["REG-9", "1"], ["SEC-3", "1"], ["No requirement ID in the report", "1"]])
        with open(os.path.join(self.out, "catalog.json"), encoding="utf-8") as f:
            published = f.read()
        for gone in ("alert(6)", "XSS-1", "SEC-9", "GI-2", "QA-11", "guarddog", "mallory", "looks good"):  # CAT-3: IDs and counts only
            self.assertNotIn(gone, page)
            self.assertNotIn(gone, published)
        self.assertNotIn("goatcounter.com/api", page)
        self.assertIn('<a href="./stats/">Statistics</a>', self.page())

    def test_stats_page_without_data(self):  # CAT-33
        texts = []
        for gate in (None, [], [GATE[5]]):
            with tempfile.TemporaryDirectory() as tmp:
                path = None
                if gate is not None:
                    path = os.path.join(tmp, "gate.json")
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(gate, f)
                with open(os.path.join(build({"serial": 1, "generators": {}}, tmp, gate=path), "stats", "index.html"), encoding="utf-8") as f:
                    texts.append(f.read())
        unread, empty, passed = texts
        self.assertIn("The gate results could not be read when this page was built.", unread)
        self.assertIn("No entry pull request has a gate result yet.", empty)
        self.assertIn("The gate rejected no entry pull request.", passed)
        self.assertIn("<tr><th scope=\"row\">All</th><td>1</td><td>0</td></tr>", passed)
        for page in texts:
            self.assertIn("No generator is published yet.", page)
            self.assertIn("No version is published yet.", page)
            self.assertNotIn("<th scope=\"col\">Requirement</th>", page)

    def test_thumbs_up_from_discussions(self):
        self.assertIn(f'<a href="https://github.com/{OWNER}/registry/discussions/5">👍 3</a> on GitHub Discussions', self.page("generators", "demo"))
        self.assertNotIn("evil.example", self.page("generators", "old"))  # CAT-20: only this registry's discussions
        self.assertNotIn("Thumbs up</dt>", self.page("generators", "old"))

    def test_seo(self):
        result = subprocess.run([sys.executable, "-I", SEO_CHECK, self.out], capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout), (0, ""))  # CAT-11d: every page
        self.assertIn('<link rel="canonical" href="https://kadet-hub.org/">', self.page())
        ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', self.page("generators", "demo"), re.S).group(1)
        self.assertNotIn("<", ld)
        self.assertEqual(json.loads(ld)["description"], "<script>alert(1)</script>")

    def test_seo_check_finds_violations(self):
        with tempfile.TemporaryDirectory() as tmp:
            arts = os.path.join(tmp, "artifacts")
            os.mkdir(arts)
            artifact(os.path.join(arts, "demo.tar"), {"README.md": "# Demo\n\n### Skips a level\n"})
            out = build({"serial": 1, "generators": {"demo": {"1.0.0": record("a")}}}, tmp, arts)
            path = os.path.join(out, "privacy", "index.html")
            with open(path, encoding="utf-8") as f:
                html = f.read()
            with open(path, "w", encoding="utf-8") as f:
                f.write(html.replace("</main>", '<h1>Again</h1><h4>Deep</h4><img src="x.png" alt=""><a href="../?tags=helm">helm</a>'
                                        '<h2>Cards</h2><ul class="cards"><li><h3>name</h3></li></ul></main>'))
            os.makedirs(os.path.join(out, "generators", "renamed"))  # a Hugo alias page is not checked
            with open(os.path.join(out, "generators", "renamed", "index.html"), "w", encoding="utf-8") as f:
                f.write('<!DOCTYPE html><html><head><title>https://kadet-hub.org/generators/demo/</title>'
                        '<meta http-equiv="refresh" content="0; url=https://kadet-hub.org/generators/demo/"></head></html>')
            result = subprocess.run([sys.executable, "-I", SEO_CHECK, out], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.splitlines(), [
            "CAT-11: privacy/index.html: 2 h1, not one",
            "CAT-8a: privacy/index.html: internal link with ?tags=: ../?tags=helm",
            "CAT-11b: privacy/index.html: h4 follows h1",  # the README's skip is clamped (CAT-11e)
            "CAT-11c: privacy/index.html: img x.png has no alt text",
            "CAT-11b: privacy/index.html: h3 inside a card list",
        ])

    def test_home_links_both_guides(self):
        html = self.page()
        for doc in ("consumers.md", "authors.md"):
            self.assertIn(f"https://github.com/{OWNER}/registry/blob/main/docs/{doc}", html)
        self.assertNotIn("No generators listed yet", html)

    def test_home_identity_schema_and_title(self):
        html = self.page()
        title = re.search(r"<title>([^<]*)</title>", html).group(1)
        self.assertTrue(50 <= len(title) <= 60, title)
        self.assertIn("Kubernetes", title)  # CAT-11a: "kapitan" alone is ambiguous in search
        self.assertRegex(self.page(), r"<h1>Kapitan generators for Kubernetes and Terraform[^<]*Helm alternative</h1>")
        self.assertIn("Helm alternative", title)  # CAT-11f
        desc = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        self.assertTrue("Helm" in desc and "Kustomize" in desc, desc)
        for slug, start in (("ingress-nginx-to-gateway-api", "Migrate ingress-nginx"), ("generator-helm-or-jinja2", "Kapitan generator vs Helm"),
                            ("bitnami-chart-alternatives", "Bitnami chart alternatives"),
                            ("helm-alternatives-for-kubernetes", "Helm alternatives for Kubernetes"),
                            ("talos-machine-config", "Talos machine config"),
                            ("helm-vs-terraform", "Helm vs Terraform for Kubernetes"),
                            ("argocd-vs-flux", "Argo CD vs Flux")):
            self.assertIn(f"<h1>{start}", self.page("guides", slug))
        ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
        types = {node["@type"]: node for node in ld["@graph"]}
        self.assertEqual(types["WebSite"]["url"], "https://kadet-hub.org/")
        self.assertEqual(types["Organization"]["sameAs"], [f"https://github.com/{OWNER}"])
        self.assertEqual(types["WebSite"]["publisher"]["@id"], types["Organization"]["@id"])

    def test_headings_skip_no_level(self):
        for parts in ((), ("generators", "demo"), ("tags", "helm"), ("tags",), ("guides", "writing-a-kapitan-generator"), ("kinds",),
                      ("compatibility",), ("wanted",), ("stats",), ("guides", "how-kadet-hub-works"), ("blog",),
                      ("blog", "kapitan-generators-as-supply-chain-artifacts")):
            levels = [int(h) for h in re.findall(r"<h([1-6])\b", self.page(*parts))]
            self.assertEqual(levels[0], 1, parts)
            for before, after in zip(levels, levels[1:]):
                self.assertLessEqual(after, before + 1, parts)
        for parts in ((), ("tags", "helm")):
            cards = self.page(*parts).split('<ul class="cards')[1]
            self.assertIn('<p class="card-name"><a class="stretched"', cards)
            self.assertNotRegex(cards.split("</ul>")[0], r"<h[1-6]\b")  # CAT-11b: card names are no headings
        home = self.page()
        self.assertIn('<h2 id="listing">How a version gets listed</h2>', home)
        self.assertLessEqual(len(re.findall(r"<h[1-6]\b", home)), 8)

    def test_no_counter_without_a_goatcounter_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["HUGO_PARAMS_GOATCOUNTER"] = ""
            try:
                out = build(INDEX, tmp)
            finally:
                del os.environ["HUGO_PARAMS_GOATCOUNTER"]
            for parts in ((), ("privacy",)):
                with open(os.path.join(out, *parts, "index.html"), encoding="utf-8") as f:
                    html = f.read()
                self.assertNotIn("count.js", html)
                self.assertNotIn("goatcounter.com/count", html)
                self.assertNotIn("connect-src", html)
            self.assertIn("The site runs no analytics or tracking.", html)

    def test_site_counts_on_its_own_instance(self):
        self.assertIn('<script data-goatcounter="https://stats.kadet-hub.org/count" async src="./count.js"></script>', self.page())

    def test_goatcounter_counts_from_the_own_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["HUGO_PARAMS_GOATCOUNTER"] = "https://stats.example.org/"
            try:
                out = build(INDEX, tmp)
            finally:
                del os.environ["HUGO_PARAMS_GOATCOUNTER"]
            with open(os.path.join(out, "index.html"), encoding="utf-8") as f:
                html = f.read()
            self.assertIn('<script data-goatcounter="https://stats.example.org/count" async src="./count.js"></script>', html)
            csp = re.search(r'Content-Security-Policy" content="([^"]*)"', html).group(1)
            self.assertIn("script-src 'self';", csp)
            self.assertIn("img-src 'self' https://stats.example.org;", csp)
            self.assertIn("connect-src https://stats.example.org;", csp)
            self.assertIn("licenses/goatcounter.txt", html)
            with open(os.path.join(out, "privacy", "index.html"), encoding="utf-8") as f:
                privacy = f.read()
            self.assertIn("https://stats.example.org", privacy)
            self.assertNotIn("runs no analytics", privacy)
        with open(os.path.join(HERE, "site", "static", "count.js"), encoding="utf-8") as f:
            self.assertTrue(f.read().startswith("// GoatCounter: https://www.goatcounter.com\n"))

    def test_readme_headings_skip_no_level(self):  # CAT-11e
        readme = self.readme_html()
        self.assertIn('<h2 id="readme-demo">Demo</h2>', readme)
        self.assertIn('<h3 id="readme-usage">Usage</h3>', readme)
        self.assertIn('<h4 id="readme-skipped-level">Skipped level</h4>', readme)

    def test_generators_without_a_listed_version_have_no_card(self):
        home, tags = self.page(), self.page("tags")
        self.assertNotIn('data-name="old"', home)
        self.assertIn('placeholder="Search 2 generators or kinds"', home)
        self.assertIn("Yanked: entry removed", self.page("generators", "old"))  # CAT-5: the page stays
        self.assertIn('id="old"', self.page("popularity"))
        self.assertIn("1 generator tagged helm", tags)

    def test_kind_index(self):  # CAT-29, CAT-29b
        self.assertEqual(os.listdir(os.path.join(self.out, "kinds")), ["index.html"])  # one renderer each: no kind page
        index = self.page("kinds")
        self.assertIn('<h3 id="gateway.networking.k8s.io">gateway.networking.k8s.io', index)
        self.assertLess(index.index('id="core"'), index.index('id="gateway.networking.k8s.io"'))
        self.assertIn('<li><code>ConfigMap</code>: rendered by <a href="../generators/demo/">demo</a>; '
                      'schema shipped by <a href="../generators/plain/">plain</a></li>', index)
        self.assertIn('<li><code>HTTPRoute</code>: rendered by <a href="../generators/demo/">demo</a>; '
                      'schema shipped by <a href="../generators/plain/">plain</a></li>', index)
        self.assertNotIn("Bad Kind", index)
        self.assertNotIn("&lt;b&gt;", index)
        self.assertIn('href="./kinds/"', self.page())  # linked from every page
        with open(os.path.join(self.out, "sitemap.xml"), encoding="utf-8") as f:
            sitemap = f.read()
        self.assertIn("<loc>https://kadet-hub.org/kinds/</loc>", sitemap)
        self.assertNotIn("<loc>https://kadet-hub.org/kinds/core/", sitemap)

    def test_kind_pages_for_kinds_two_generators_render(self):  # CAT-29b, CAT-26, CAT-11
        azure = {"group": "insights.azure.upbound.io", "version": "v1beta1", "kind": "ApplicationInsightsWorkbookTemplate"}
        far = {"group": "a.very.long.group.name.example.com.and.more.example.org", "version": "v1", "kind": "AVeryVeryVeryLongKindNameThatGoesOn"}
        route = {"group": "gateway.networking.k8s.io", "version": "v1", "kind": "HTTPRoute"}
        beta = dict(route, version="v1beta1")
        index = {"serial": 1, "generators": {
            "a": {"1.0.0": dict(record("a", tags=()), kinds=[route, beta, azure, far])},
            "b": {"1.0.0": dict(record("b", tags=()), kinds=[route, azure, far])},
            "c": {"1.0.0": record("c", tags=())},  # no record: ships a schema
            "d": {"1.0.0": dict(record("d", tags=(), yanked="broken"), kinds=[route])},  # CAT-26
            "e": {"1.0.0": dict(record("e", tags=()), kinds=[route]), "1.1.0": dict(record("f", tags=()), kinds=[])}}}
        with tempfile.TemporaryDirectory() as tmp:
            sboms = os.path.join(tmp, "sboms")
            for name, version in (("c", "1.0.0"), ("e", "1.1.0")):  # e has a record, so its SBOM is not read
                sbom(os.path.join(sboms, name, f"{version}.spdx.json"), ["./schemas/gateway.networking.k8s.io/httproute_v1.json"])
            out = build(index, tmp, sboms=sboms)
            result = subprocess.run([sys.executable, "-I", SEO_CHECK, out], capture_output=True, text=True)
            pages = sorted(os.path.relpath(os.path.join(d, n), out) for d, _, names in os.walk(os.path.join(out, "kinds")) for n in names)
            read = lambda *parts: open(os.path.join(out, "kinds", *parts, "index.html"), encoding="utf-8").read()
            page, kinds = read("gateway.networking.k8s.io", "httproute"), read()
            titles = [re.search(r"<title>([^<]*)</title>", read(*p)).group(1) for p in
                      (("insights.azure.upbound.io", "applicationinsightsworkbooktemplate"), (far["group"], "averyveryverylongkindnamethatgoeson"))]
            desc = re.search(r'<meta name="description" content="([^"]*)"', read(far["group"], "averyveryverylongkindnamethatgoeson")).group(1)
            with open(os.path.join(out, "sitemap.xml"), encoding="utf-8") as f:
                sitemap = f.read()
        self.assertEqual((result.returncode, result.stdout), (0, ""))  # CAT-11d on every page
        self.assertEqual(pages, [f"kinds/{far['group']}/averyveryverylongkindnamethatgoeson/index.html",
                                 "kinds/gateway.networking.k8s.io/httproute/index.html", "kinds/index.html",
                                 "kinds/insights.azure.upbound.io/applicationinsightsworkbooktemplate/index.html"])
        self.assertIn("<h1>Kapitan generators that render <code>HTTPRoute</code> in gateway.networking.k8s.io</h1>", page)
        self.assertIn("<dd><code>gateway.networking.k8s.io/v1</code>: a, b</dd>", page)
        self.assertIn("<dd><code>gateway.networking.k8s.io/v1beta1</code>: a</dd>", page)
        self.assertIn('<dt>Schema shipped by</dt><dd><a href="../../../generators/c/">c</a></dd>', page)
        self.assertEqual(re.findall(r'data-name="([^"]+)"', page.split('<ul class="cards')[1]), ["a", "b"])
        levels = [int(h) for h in re.findall(r"<h([1-6])\b", page)]
        self.assertEqual((levels[0], max(b - a for a, b in zip(levels, levels[1:]))), (1, 1))
        self.assertIn('<li><a href="../kinds/gateway.networking.k8s.io/httproute/"><code>HTTPRoute</code></a>: rendered by '
                      '<a href="../generators/a/">a</a>, <a href="../generators/b/">b</a>; schema shipped by <a href="../generators/c/">c</a></li>', kinds)
        self.assertEqual(titles, ["ApplicationInsightsWorkbookTemplate (insights.azure.upbound.io)",
                                  "AVeryVeryVeryLongKindNameThatGoesOn · kadet-hub"])  # the group goes last
        self.assertTrue(desc.endswith("…") and len(_unescape(desc)) <= 160, desc)
        for url in ("kinds/", "kinds/gateway.networking.k8s.io/httproute/"):
            self.assertIn(f"<loc>https://kadet-hub.org/{url}</loc>", sitemap)

    def test_kinds_without_a_group_split_by_version(self):  # CAT-29, CAT-29b, CAT-29c
        def gen(d, kinds, *software):
            return {"1.0.0": dict(record(d, tags=()), kinds=[dict(zip(("group", "version", "kind"), k)) for k in kinds],
                                  compatibility=[{"software": s, "version": "1", "source": "tbd"} for s in software])}
        index = {"serial": 1, "generators": {
            "k8s-a": gen("a", [("", "v1", "ConfigMap"), ("apps", "v1", "Deployment"), ("gateway.networking.k8s.io", "v1", "HTTPRoute")],
                         "Kubernetes", "Gateway API"),
            "k8s-b": gen("b", [("", "v1", "ConfigMap")], "Kubernetes"),
            "talos-a": gen("c", [("", "v1alpha1", "ConfigMap"), ("", "v1alpha1", "HostnameConfig"), ("", "v1", "Secret")], "Kubernetes", "Talos"),
            "talos-b": gen("d", [("", "v1alpha1", "ConfigMap")], "Talos"),
            "kyv": gen("e", [("kyverno.io", "v1", "ClusterPolicy")], "Kyverno"),
            "multi": gen("f", [("kyverno.io", "v1", "Policy"), ("cert-manager.io", "v1", "Certificate")], "Kyverno", "cert-manager")}}
        with tempfile.TemporaryDirectory() as tmp:
            out = build(index, tmp)
            result = subprocess.run([sys.executable, "-I", SEO_CHECK, out], capture_output=True, text=True)
            read = lambda *parts: open(os.path.join(out, "kinds", *parts, "index.html"), encoding="utf-8").read()
            kinds, core, talos = read(), read("core", "configmap"), read("v1alpha1", "configmap")
            with open(os.path.join(out, "sitemap.xml"), encoding="utf-8") as f:
                sitemap = f.read()
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        cards = lambda page: re.findall(r'data-name="([^"]+)"', page.split('<ul class="cards')[1])
        self.assertEqual((cards(core), cards(talos)), (["k8s-a", "k8s-b"], ["talos-a", "talos-b"]))
        self.assertIn("<dd><code>v1</code>: k8s-a, k8s-b</dd>", core)
        self.assertIn("<dd><code>v1alpha1</code>: talos-a, talos-b</dd>", talos)
        self.assertIn("<dt>API group</dt><dd>none: the apiVersion has no group</dd>", talos)
        headings = re.findall(r'<h([23]) id="([^"]+)">(.*?)</h[23]>', kinds)
        self.assertEqual(headings, [
            ("2", "builtin", "Kubernetes built-in APIs"), ("3", "apps", "apps"), ("3", "core", "core (v1)"),
            ("2", "custom", "Custom resources and other APIs"), ("3", "cert-manager.io", "cert-manager.io"),
            ("3", "gateway.networking.k8s.io", "gateway.networking.k8s.io · Gateway API"), ("3", "kyverno.io", "kyverno.io · Kyverno"),
            ("3", "v1alpha1", "v1alpha1 · Talos")])
        for url in ("kinds/core/configmap/", "kinds/v1alpha1/configmap/"):
            self.assertIn(f'href="../{url}"', kinds)
            self.assertIn(f"<loc>https://kadet-hub.org/{url}</loc>", sitemap)

    def test_search_matches_kind_names(self):  # CAT-29a
        home = self.page()
        self.assertRegex(home, r'data-text="demo [^"]* configmap httproute" data-tags="helm" data-name="demo"')
        self.assertRegex(home, r'data-text="plain [^"]* configmap httproute" data-tags="" data-name="plain"')

    def test_feed_stays_valid_xml_with_control_characters(self):  # CAT-18, QA-5a
        with tempfile.TemporaryDirectory() as tmp:
            out = build({"serial": 1, "generators": {"esc": {"1.0.0": record("a", description="Renders \x1b[31mred\u202e text")}}}, tmp)
            with open(os.path.join(out, "index.xml"), encoding="utf-8") as f:
                feed = f.read()
        __import__("xml.etree.ElementTree").etree.ElementTree.fromstring(feed)
        self.assertIn("<summary>Renders [31mred text</summary>", feed)

    def test_empty_index_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = build({"serial": 1, "generators": {}}, tmp)
            with open(os.path.join(out, "index.html"), encoding="utf-8") as f:
                self.assertIn("No generators listed yet", f.read())


DIAGRAMS = os.path.join(HERE, "site", "assets", "diagrams")


def svg_findings(text):
    """CAT-35a: what the CSP blocks in an inline SVG, or what loads another document."""
    found = []
    for el in ET.fromstring(text).iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag in ("style", "script"):
            found.append(f"<{tag}>")
        for attr, value in el.attrib.items():
            attr = attr.rsplit("}", 1)[-1]
            if attr == "style" or attr.startswith("on") or (attr == "href" and not value.startswith("#")):
                found.append(f"{tag} {attr}={value}")
    return found


class Diagrams(unittest.TestCase):
    def test_diagram_svgs(self):  # CAT-35a
        names = sorted(f.removesuffix(".dot") for f in os.listdir(DIAGRAMS) if f.endswith(".dot"))
        self.assertEqual(names, ["consuming", "listing", "overview", "release", "upstream", "withdraw"])
        self.assertEqual(names, sorted(f.removesuffix(".svg") for f in os.listdir(DIAGRAMS) if f.endswith(".svg")))
        for name in names:
            with open(os.path.join(DIAGRAMS, f"{name}.svg"), encoding="utf-8") as f:
                svg = f.read()
            with open(os.path.join(DIAGRAMS, f"{name}.dot"), encoding="utf-8") as f:
                dot = f.read()
            self.assertEqual(svg_findings(svg), [], name)
            version = re.search(r"Generated by graphviz version (\S+)", svg).group(1)
            self.assertIn(f"Rendered with Graphviz {version};", dot, name)
            self.assertLessEqual(float(re.search(r'<svg width="([\d.]+)pt"', svg).group(1)), 340, name)  # readable at 360 px
            fails = re.findall(r'<g id="[^"]+" class="(?:node|edge) fail">.*?</g>', svg, re.S)
            for group in fails:
                self.assertIn('stroke-dasharray="', group, name)  # never colour alone
            if fails:
                self.assertIn(">fails</text>", svg, name)
        for bad in ("<style>text { fill: red }</style>", '<g style="fill: red"/>', "<script>alert(1)</script>", '<g onload="alert(1)"/>',
                    '<a xlink:href="https://example.org/x"/>', '<image href="//example.org/x.png"/>'):
            svg = f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">{bad}</svg>'
            self.assertNotEqual(svg_findings(svg), [], bad)
        self.assertEqual(svg_findings('<svg xmlns="http://www.w3.org/2000/svg"><use href="#i-x"/></svg>'), [])

def built_for(software, version):
    return {"software": software, "version": version, "source": f"https://example.org/{version}"}


# CAT-34: listed versions built for one or two products, an older upstream version, markup in a software name,
# a yanked and an unrecorded version, a generator without records and one without a listed version.
EVIL = '<script>alert(9)</script> "Q" & co'
CM, TM = built_for("cert-manager", "1.21.2"), built_for("trust-manager", "0.25.0")
MATCH_INDEX = {"serial": 3, "generators": {
    "certmanager": {"1.0.1": dict(record("a"), compatibility=[CM, TM]), "1.0.0": dict(record("b"), compatibility=[CM, TM, CM]),
                    "0.9.0": dict(record("c"), compatibility=[built_for("cert-manager", "1.19.4"), built_for(EVIL, "1")]),
                    "0.8.0": dict(record("d", yanked="broken"), compatibility=[built_for("cert-manager", "1.18.0")]), "0.7.0": record("e")},
    "kube": {"2.0.0": dict(record("f"), compatibility=[built_for("Kubernetes", "1.37.1"), CM])},
    "bare": {"1.0.0": record("g")},
    "gone": {"1.0.0": dict(record("h", yanked="entry removed"), compatibility=[built_for("Gone", "1.0.0")])},
}}


class Match(unittest.TestCase):  # CAT-34
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = build(MATCH_INDEX, cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, *parts):
        with open(os.path.join(self.out, *parts, "index.html"), encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def table(html):
        """(link, name, built for as text) of every row of the versions table."""
        start = html.index('<table class="built">')
        rows = re.findall(r'<tr><th scope="row"><a href="([^"]+)">([^<]+)</a></th><td>(.*?)</td></tr>', html[start:html.index("</table>", start)])
        return [(href, name, _unescape(re.sub(r"<[^>]+>", "", cell.replace("<br>", ", ")))) for href, name, cell in rows]

    @staticmethod
    def selector(html):
        """{software: suggested versions} of the selector, in the order of its options."""
        form = html[html.index('<form class="match-form" hidden>'):html.index("</form>")]
        lists = dict(re.findall(r'<datalist id="(match-[0-9]+)">(.*?)</datalist>', form))
        return {_unescape(s): re.findall(r'<option value="([^"]*)">', lists[i])
                for i, s in re.findall(r'<option data-list="(match-[0-9]+)">([^<]*)</option>', form)}

    def test_versions_table_without_javascript(self):  # CAT-34
        html = self.page("generators", "certmanager")
        self.assertIn('<thead><tr><th scope="col">Version</th><th scope="col">Built for (schema-checked)</th></tr></thead>', html)
        self.assertEqual(self.table(html), [
            ("#v1.0.1", "1.0.1", "cert-manager 1.21.2, trust-manager 0.25.0"),
            ("#v1.0.0", "1.0.0", "cert-manager 1.21.2, trust-manager 0.25.0"),
            ("#v0.9.0", "0.9.0", f"cert-manager 1.19.4, {EVIL} 1"),
            ("#v0.7.0", "0.7.0", "not recorded")])  # the yanked 0.8.0 is left out
        self.assertIn('id="v0.8.0"', html)  # and stays in the list below
        self.assertLess(html.index('<form class="match-form" hidden>'), html.index('<table class="built">'))  # hidden without JavaScript
        self.assertLess(html.index('<table class="built">'), html.index('id="v1.0.1"'))
        bare = self.page("generators", "bare")
        self.assertEqual(self.table(bare), [("#v1.0.0", "1.0.0", "not recorded")])
        self.assertNotIn("match-form", bare)  # nothing to select
        self.assertNotIn('class="built"', self.page("generators", "gone"))

    def test_selector_one_product_at_a_time(self):  # CAT-34a
        html = self.page("generators", "certmanager")
        self.assertIn('<label for="match-software">I run</label>', html)
        self.assertEqual(self.selector(html), {EVIL: ["1"], "cert-manager": ["1.21.2", "1.19.4"], "trust-manager": ["0.25.0"]})
        self.assertEqual(list(self.selector(html)), [EVIL, "cert-manager", "trust-manager"])
        self.assertEqual(html.count('<span data-software="cert-manager" data-version="1.21.2">cert-manager 1.21.2</span>'), 2)

    def test_software_names_are_escaped(self):  # CAT-34a, CAT-3
        escaped = "&lt;script&gt;alert(9)&lt;/script&gt; &#34;Q&#34; &amp; co"
        for html in (self.page("generators", "certmanager"), self.page("compatibility")):
            self.assertNotIn("<script>alert(9)", html)
            self.assertIn(f'<span data-software="{escaped}" data-version="1">{escaped} 1</span>', html)
            self.assertIn(f'<option data-list="match-0">{escaped}</option>', html)
        with open(os.path.join(HERE, "site", "static", "site.js"), encoding="utf-8") as f:
            self.assertNotRegex(f.read(), r"innerHTML|outerHTML|insertAdjacentHTML|document\.write")

    def test_compatibility_page_selector(self):  # CAT-34c, CAT-26
        html = self.page("compatibility")
        self.assertLess(html.index('<table class="compat">'), html.index('<h2 id="built-for">'))
        self.assertLess(html.index('<h2 id="built-for">'), html.index('<table class="built">'))
        both = "cert-manager 1.21.2, trust-manager 0.25.0"
        self.assertEqual(self.table(html), [
            ("../generators/bare/#v1.0.0", "bare 1.0.0", "not recorded"),
            ("../generators/certmanager/#v1.0.1", "certmanager 1.0.1", both),
            ("../generators/certmanager/#v1.0.0", "certmanager 1.0.0", both),
            ("../generators/certmanager/#v0.9.0", "certmanager 0.9.0", f"cert-manager 1.19.4, {EVIL} 1"),
            ("../generators/certmanager/#v0.7.0", "certmanager 0.7.0", "not recorded"),
            ("../generators/kube/#v2.0.0", "kube 2.0.0", "Kubernetes 1.37.1, cert-manager 1.21.2")])
        self.assertEqual(self.selector(html), {EVIL: ["1"], "Kubernetes": ["1.37.1"], "cert-manager": ["1.21.2", "1.19.4"],
                                               "trust-manager": ["0.25.0"]})

    def test_seo(self):  # CAT-11d over the new markup
        result = subprocess.run([sys.executable, "-I", SEO_CHECK, self.out], capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_consumer_docs_lookup(self):  # CAT-34d
        with open(os.path.join(HERE, "..", "docs", "consumers.md"), encoding="utf-8") as f:
            doc = f.read()
        start = doc.index("\n## Picking a version by what it is built for\n")
        section = doc[start:doc.index("\n## ", start + 1)]
        command = re.search(r"```sh\ncurl -fsSL https://kadet-hub\.org/catalog\.json \| (jq .*?)\n```", section, re.S).group(1)
        result = subprocess.run(shlex.split(command) + [os.path.join(self.out, "catalog.json")], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, f"1.0.1 sha256:{'a' * 64}\n1.0.0 sha256:{'b' * 64}\n")  # not the yanked 0.8.0
        recipe = json.loads(re.search(r"```json\n(.*?)\n```", section, re.S).group(1))
        (name, datasource), = recipe["customDatasources"].items()
        self.assertEqual(datasource["defaultRegistryUrlTemplate"], "https://kadet-hub.org/catalog.json")
        self.assertEqual([m["datasourceTemplate"] for m in recipe["customManagers"]], [f"custom.{name}"])
        self.assertIn({"matchDatasources": ["docker"], "matchPackageNames": ["ghcr.io/kadet-hub/certmanager"], "enabled": False},
                      recipe["packageRules"])
        self.assertIn("not signed", section)
        self.assertIn("(specs/consumers.md)", section)  # CON-2


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

    def test_schema_kinds_from_sbom_file_names(self):  # CAT-29
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "s.spdx.json")
            sbom(path, SBOM_FILES)
            self.assertEqual(schema_kinds(path), [("core", "configmap", "v1"), ("gateway.networking.k8s.io", "httproute", "v1"),
                                                  ("gateway.networking.k8s.io", "httproute", "v1beta1")])
            for text in ("not json", "[]", '{"files": [1, {"fileName": 2}]}'):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.assertEqual(schema_kinds(path), [], text)
            self.assertEqual(schema_kinds(os.path.join(tmp, "missing.json")), [])

    def test_kinds_from_the_record_or_the_sbom(self):  # CAT-29, CAT-26
        index = {"generators": dict(INDEX["generators"], alpha={"1.0.0": record("e")}, zulu={"1.0.0": record("f")})}
        with tempfile.TemporaryDirectory() as tmp:
            sbom(os.path.join(tmp, "demo", "1.10.0.spdx.json"), ["./schemas/apps/deployment_v1.json"])  # the record wins
            sbom(os.path.join(tmp, "demo", "1.2.0.spdx.json"), ["./schemas/apps/statefulset_v1.json"])  # not the latest
            sbom(os.path.join(tmp, "old", "0.1.0.spdx.json"), ["./schemas/apps/daemonset_v1.json"])  # every version yanked
            sbom(os.path.join(tmp, "alpha", "1.0.0.spdx.json"), ["./schemas/core/configmap_v1.json"])
            sbom(os.path.join(tmp, "zulu", "1.0.0.spdx.json"), ["./schemas/core/configmap_v1.json"])
            result = view(index, OWNER, lambda _: None, sboms=tmp)
        gens = {g["name"]: g for g in result["generators"]}
        self.assertEqual([gens[n]["kinds"] for n in ("demo", "alpha", "old")], [["ConfigMap", "HTTPRoute"], ["configmap"], []])
        self.assertEqual(result["kinds"], {
            "core": {"configmap": {"name": "ConfigMap", "page": False, "rendered": ["demo"], "schema": ["alpha", "zulu"],
                                   "versions": {"v1": ["demo"]}}},
            "gateway.networking.k8s.io": {"httproute": {"name": "HTTPRoute", "page": False, "rendered": ["demo"], "schema": [],
                                                        "versions": {"gateway.networking.k8s.io/v1": ["demo"]}}}})
        self.assertEqual(view({"generators": {"x": {"1.0.0": record("a")}}}, OWNER, lambda _: None)["kinds"], {})  # no record, no SBOM

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


class ReleaseDigest(unittest.TestCase):  # CAT-36b
    INDEX = {"serial": 9, "generators": {
        "demo": {"1.0.0": dict(record("a"), published="2026-10-09T05:00:00Z"),  # the import week: no post
                 "1.1.0": dict(record("b"), published="2026-10-13T08:00:00Z"),
                 "1.2.0": dict(record("c"), published="2026-10-18T23:59:59Z"),
                 "1.3.0": dict(record("d", yanked="broken"), published="2026-10-14T08:00:00Z")},
        "plain": {"0.1.0": dict(record("e"), published="2026-10-26T00:00:00Z"),  # first version: new
                  "0.2.0": dict(record("f"), published="2099-01-05T00:00:00Z")}}}

    def test_weeks(self):
        weeks = releases(self.INDEX)
        self.assertEqual([(w["monday"], w["date"]) for w in weeks],
                         [("2026-10-12", "2026-10-19"), ("2026-10-26", "2026-11-02"), ("2099-01-05", "2099-01-12")])
        demo = weeks[0]["generators"]
        self.assertEqual([(g["name"], g["versions"], g["new"]) for g in demo], [("demo", ["1.1.0", "1.2.0"], False)])
        self.assertTrue(demo[0]["changelog"].endswith("/CHANGELOG.md"))
        self.assertEqual([(g["name"], g["new"]) for g in weeks[1]["generators"]], [("plain", True)])

    def test_posts(self):
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch.dict(os.environ, {"HUGO_BUILDFUTURE": "true"}):
            out = build(self.INDEX, tmp)
            with open(os.path.join(out, "blog", "releases-2026-10-12", "index.md"), encoding="utf-8") as f:
                md = f.read()
            with open(os.path.join(out, "blog", "releases-2026-10-26", "index.html"), encoding="utf-8") as f:
                html = f.read()
        self.assertTrue(md.startswith("# Kapitan generator releases, 12 to 18 October 2026\n"), md)
        self.assertIn("\n| [demo](/generators/demo/) | 1.1.0, 1.2.0 | [CHANGELOG](", md)
        self.assertNotIn("1.3.0", md)
        self.assertIn("<title>Kapitan generator releases, 26 October to 1 November 2026", html)
        self.assertIn('<time datetime="2026-11-02">', html)
        self.assertIn("plain</a> (new)", html)
        with tempfile.TemporaryDirectory() as tmp:
            out = build(self.INDEX, tmp)
            self.assertFalse(os.path.exists(os.path.join(out, "blog", "releases-2099-01-05")))  # future-dated: left out
            self.assertFalse(os.path.exists(os.path.join(out, "blog", "releases-2026-10-05")))
        self.assertNotIn("## demo", md)  # no artifact layer: the line only
        self.assertNotIn("Full changelog", md)

    # The CHANGELOG.md of demo's latest listed version, 1.2.0: sections of other versions, markup and control characters.
    CHANGELOG = ("# Changelog\n\n## [1.3.0] - 2026-10-14\n\n- yanked entry\n\n## 1.2.0-rc.1\n\n- rc entry\n\n## 11.2.0\n\n- other entry\n\n"
                 "## [1.2.0] - 2026-10-18\n\n### Fixed\n\n- fix <script>alert(8)</script>\x1b\u202e one, see [docs](docs/x.md),"
                 " [site](https://example.org/y) and [above](#fixed)\n- ## nested\n\nUnderlined\n---\n\n{{< nope >}}\n\n"
                 "## v1.1.0\n\n```yaml\n## not a heading\n```\n" + "".join(f"- change {i}\n" for i in range(20))
                 + "\n## [1.0.0] - 2026-10-09\n\n- import entry\n")

    def test_sections(self):
        from view import changelog_sections as sections
        found = sections(self.CHANGELOG, ["1.3.0", "1.2.0", "1.1.0", "1.0.0"])
        self.assertTrue(found["1.2.0"].startswith("#### Fixed\n\n- fix <script>alert(8)</script> one,"), found["1.2.0"])
        self.assertNotIn("rc entry", found["1.2.0"])
        self.assertNotIn("other entry", found["1.2.0"])
        self.assertIn("\n## not a heading\n", found["1.1.0"])  # inside a fence: kept, no heading
        self.assertEqual(found["1.0.0"], "- import entry")
        with tempfile.TemporaryDirectory() as tmp:  # no CHANGELOG.md in the layer
            artifact(os.path.join(tmp, "a.tar"), {"./README.md": "# Plain\n"})
            self.assertEqual(sections(readme(os.path.join(tmp, "a.tar"), "CHANGELOG.md"), ["1.0.0"]), {})
        g = releases(self.INDEX, {"demo": sections("## 1.0.0\n\n- other version", ["1.0.0"])})[0]["generators"][0]
        self.assertEqual((g["entries"], g["cut"]), ([], False))  # no section for the week's versions: the line only

    def test_excerpt_is_capped(self):
        from view import changelog_sections as sections
        found = sections(self.CHANGELOG, ["1.2.0", "1.1.0"])
        g = releases(self.INDEX, {"demo": found})[0]["generators"][0]
        self.assertEqual([e["version"] for e in g["entries"]], ["1.2.0", "1.1.0"])  # newest first
        self.assertTrue(g["cut"])
        self.assertEqual(sum(e["text"].count("\n") + 1 for e in g["entries"]), 15)
        g = releases(self.INDEX, {"demo": {"1.1.0": "- one\n```\ncode"}})[0]["generators"][0]
        self.assertEqual((g["entries"], g["cut"]), ([{"version": "1.1.0", "text": "- one\n```\ncode\n```"}], False))

    def test_changelog_in_posts(self):
        with tempfile.TemporaryDirectory() as tmp, unittest.mock.patch.dict(os.environ, {"HUGO_BUILDFUTURE": "true"}):
            os.makedirs(os.path.join(tmp, "artifacts"))
            artifact(os.path.join(tmp, "artifacts", "demo.tar"), {"./README.md": "# Demo\n", "./CHANGELOG.md": self.CHANGELOG})
            with open(os.path.join(tmp, "artifacts", "plain.tar"), "w", encoding="utf-8") as f:
                f.write("not a tar")  # unreadable layer
            out = build(self.INDEX, tmp, artifacts=os.path.join(tmp, "artifacts"))
            post = os.path.join(out, "blog", "releases-2026-10-12")
            with open(os.path.join(post, "index.md"), encoding="utf-8") as f:
                md = f.read()
            with open(os.path.join(post, "index.html"), encoding="utf-8") as f:
                html = f.read()
            with open(os.path.join(out, "blog", "releases-2026-10-26", "index.md"), encoding="utf-8") as f:
                plain = f.read()
            seo = subprocess.run([sys.executable, "-I", SEO_CHECK, out], capture_output=True, text=True)
        self.assertEqual(seo.returncode, 0, seo.stdout)  # CAT-11b: headings do not skip a level
        self.assertIn("| [demo](/generators/demo/) | 1.1.0, 1.2.0 | [CHANGELOG](", md)  # the line stays
        self.assertIn("\n## demo\n\n### demo 1.2.0\n\n#### Fixed\n\n- fix <script>alert(8)</script> one,", md)
        self.assertIn("\n### demo 1.1.0\n\n```yaml\n## not a heading\n```\n- change 0\n", md)
        self.assertIn(f"\n[Full changelog](https://github.com/example/demo/blob/{'c' * 40}/CHANGELOG.md)\n", md)
        for text in ("yanked entry", "rc entry", "other entry", "import entry", "change 19", "\x1b", "\u202e"):
            self.assertNotIn(text, md)
            self.assertNotIn(text, html)
        self.assertNotIn("<script>alert", html)
        self.assertIn('<a href="https://example.org/y" rel="nofollow ugc noopener">site</a>', html)
        self.assertIn(f'<a href="https://github.com/example/demo/blob/{"c" * 40}/docs/x.md" rel="nofollow ugc noopener">docs</a>', html)
        self.assertIn(f'href="https://github.com/example/demo/blob/{"c" * 40}/CHANGELOG.md#fixed" rel="nofollow ugc noopener">above</a>', html)
        self.assertIn("{{&lt; nope &gt;}}", html)  # no shortcode call
        levels = [int(n) for n in re.findall(r"<h([1-6])", html[html.index('id="changes-demo"') - 8:html.index('class="post-foot"')])]
        self.assertEqual(levels[:2], [2, 3])
        self.assertTrue(all(n >= 4 for n in levels[2:] if n != 3), levels)
        self.assertIn('id="changes-demo-1.2.0-fixed"', html)
        self.assertIn(">Full changelog</a>", html)
        self.assertNotIn("## plain", plain)  # unreadable layer: the line only
        self.assertIn("| [plain](/generators/plain/) (new) | 0.1.0 | [CHANGELOG](", plain)


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
