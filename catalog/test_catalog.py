import glob
import hashlib
import itertools
import json
import os
import posixpath
import re
import shlex
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
import unittest.mock
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from html import unescape as _unescape
from typing import ClassVar

HERE = os.path.dirname(os.path.abspath(__file__))
SEO_CHECK = os.path.join(HERE, "seo_check.py")
sys.path.insert(0, HERE)
from view import (
    README_MAX,
    grade,
    readme,
    registry_page,
    releases,
    schema_kinds,
    schema_sources,
    security,
    view,
)

OWNER = "kadet-hub"


def contrast(a, b):
    """WCAG contrast ratio of two #rrggbb colours (CAT-54, PG-25)."""
    def luminance(hex_colour):
        rgb = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        r, g, b = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def png_rows(path):
    """CAT-58: width, height, bytes per pixel and the unfiltered rows of an 8-bit RGB or RGBA PNG without interlacing."""
    with open(path, "rb") as f:
        data = f.read()
    pos, idat = 8, b""
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        if kind == b"IHDR":
            width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", data[pos + 8:pos + 21])
            if (depth, colour in (2, 6), interlace) != (8, True, 0):
                raise ValueError(f"{path}: depth {depth}, colour type {colour}, interlace {interlace}")
        elif kind == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        pos += 12 + length
    bpp = 3 if colour == 2 else 4
    raw, stride, prev, rows = zlib.decompress(idat), width * bpp, bytearray(width * bpp), []
    for y in range(height):  # PNG filter types 1 to 4: Sub, Up, Average, Paeth
        kind, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride) if kind else ():
            a = line[i - bpp] if i >= bpp else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + prev[i]) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + prev[i]) // 2) & 255
            else:
                b, c = prev[i], prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                line[i] = (line[i] + (a if abs(p - a) <= min(abs(p - b), abs(p - c)) else b if abs(p - b) <= abs(p - c) else c)) & 255
        rows.append(bytes(line))
        prev = line
    return width, height, bpp, rows


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
# CAT-41: open recipe requests of kadet-hub/recipes, in the same form.
WANTED_RECIPES = [{"number": 3, "title": "[request] Immich <b>x</b>", "up": 1, "created": "2026-11-01T09:00:00Z", "updated": "2026-11-02T10:00:00Z"},
                  {"number": 5, "title": "[request] Paperless-ngx", "up": 4, "created": "2026-11-03T09:00:00Z", "updated": "2026-11-03T09:00:00Z"}]



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


def sources_layers(tmp, layers):
    """CAT-29c: <tmp>/artifacts/<name>.tar whose schemas/sources.yaml maps each key to its software, in the QA-7 form."""
    path = os.path.join(tmp, "artifacts")
    os.makedirs(path)
    for name, entries in layers.items():
        artifact(os.path.join(path, f"{name}.tar"), {"./schemas/sources.yaml": "# QA-7\n" + "".join(
            f"{key}:\n  software: {software}\n  version: 1.0.0\n  copyright:\n    - x\n" for key, software in entries.items())})
    return path


# CAT-37c: a kadet-hub/recipes recipe as fetched to inventory/classes/recipes/<name>/, raw HTML in a section.
CHART_RECIPE_SHA = "1" * 40
CHART_RECIPE_FILES = {
    "README.md": "# cert-manager\n\nThe controller and the webhook, rendered by the kadet-hub `kubernetes`\ngenerator. Derived from the chart:\n\n"
                 f"Source: `oci://quay.io/jetstack/charts/cert-manager:v1.21.2@sha256:{'c' * 64}`\n\nLevel: `deploys`\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.cert-manager\n  - recipes.cert-manager.crds   # the chart's crds.enabled\n```\n\n"
                 "## Required parameters\n\nNo parameter has to be set.\n\n## Settings\n\n| Chart value | Inventory |\n|---|---|\n| `replicaCount` | `components.cert-manager.replicas` |\n\n"
                 "## Left out\n\nThe hook <script>alert(8)</script> `Job/cert-manager-startupapicheck`.\n\n"
                 "## Renamed RBAC objects\n\n| Chart | Recipe |\n|---|---|\n| `cert-manager:leaderelection` | `cert-manager-leaderelection` |\n\n"
                 "## Proof\n\n`check cert-manager --level deploys` on kind.\n\n## Replacing a Helm release\n\nNot tested.\n",
    # A leading comment with a comma before any colon, as homepage's kubernetes.yml has: Hugo reads such a string as CSV.
    "init.yml": "# The controller, the webhook\nclasses:\n  - .controller\n  - .webhook\nparameters:\n  kapitan:\n    dependencies:\n      - type: oci\n"
                f"        source: ghcr.io/{OWNER}/kubernetes:1.7.0@sha256:{'d' * 64}\n        output_path: lib/kubernetes\n",
    "controller.yml": "parameters:\n  components:\n    cert-manager:\n      application: cert-manager\n",
    "webhook.yml": "parameters:\n  components:\n    cert-manager-webhook:\n      application: cert-manager\n",
    "crds.yml": "# The chart's CRDs, behind crds.enabled\nparameters:\n  kapitan:\n    compile: []\n",
}
# CAT-37e: a kadet-hub/recipes recipe migrated from a Docker Compose file.
COMPOSE_SOURCE = f"https://github.com/miniflux/v2/blob/{'2' * 40}/contrib/docker-compose/basic.yml"
COMPOSE_RECIPE_FILES = {
    "README.md": "# miniflux\n\nMiniflux and its PostgreSQL database, from the Docker Compose file.\n\n"
                 f"Source: `{COMPOSE_SOURCE}@sha256:{'f' * 64}`\n\nLevel: `deploys`\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.miniflux\nparameters:\n  applications:\n    miniflux:\n      admin:\n        password: <ref>\n```\n\n"
                 "## Required parameters\n\nThe password must be set as a ref. Without it the compile stops with\n"
                 "`Interpolation key 'applications.miniflux.admin.password' not found`.\n\n"
                 "## Settings\n\n| Compose | Inventory |\n|---|---|\n| `ADMIN_USERNAME` | `applications.miniflux.admin.username` |\n\n"
                 "## Mapping\n\n| Compose | Recipe |\n|---|---|\n| service `db` | StatefulSet `miniflux-db` |\n\n"
                 "## Proof\n\n`check miniflux --level deploys` on kind.\n",
    "init.yml": "classes:\n  - .miniflux\n  - .db\nparameters:\n  kapitan:\n    dependencies:\n      - type: oci\n"
                f"        source: ghcr.io/{OWNER}/kubernetes:1.7.0@sha256:{'d' * 64}\n        output_path: lib/kubernetes\n",
    "miniflux.yml": "parameters:\n  components:\n    miniflux:\n      application: miniflux\n",
    "db.yml": "parameters:\n  components:\n    miniflux-db:\n      application: miniflux\n",
}

# CAT-38a: valkey, moved from kadet-hub/examples under the same name.
VALKEY_RECIPE_FILES = {
    "README.md": "# valkey\n\nValkey, rendered by the kadet-hub `kubernetes` generator from the valkey-io chart.\n\n"
                 f"Source: `oci://ghcr.io/valkey-io/valkey-helm/valkey:0.12.0@sha256:{'a' * 64}`\n\nLevel: `deploys`\n\n"
                 "## Replaces\n\nThis recipe replaces the `valkey` recipe of kadet-hub/examples. <script>alert(9)</script>\n\n"
                 "| kadet-hub/examples | This recipe |\n|---|---|\n| StatefulSet `valkey` | Deployment `valkey` |\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.valkey\n```\n\n"
                 "## Required parameters\n\n`applications.valkey.password` must be set.\n\n"
                 "## Settings\n\n| Chart value | Inventory |\n|---|---|\n| `valkeyConfig` | `applications.valkey.config` |\n\n"
                 "## Proof\n\n`check valkey --level deploys` on kind.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .valkey\n"),
    "valkey.yml": "parameters:\n  components:\n    valkey:\n      application: valkey\n",
}

# CAT-37f: mysql, designed on its project's image and moved from kadet-hub/examples under the same name.
DESIGN_SOURCE = f"container-registry.oracle.com/mysql/community-server:9.7.4@sha256:{'b' * 64}"
MYSQL_RECIPE_FILES = {
    "README.md": "# mysql\n\nMySQL Community Server as a single instance, designed in kadet-hub on Oracle's image.\n\n"
                 f"Source: `{DESIGN_SOURCE}`\n\nLevel: `deploys`\n\n"
                 "## Replaces\n\nThis recipe replaces the `mysql` recipe of kadet-hub/examples.\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.mysql\n```\n\n"
                 "## Required parameters\n\n`applications.mysql.password` must be set.\n\n"
                 "## Settings\n\n| Setting | Inventory |\n|---|---|\n| MySQL version | `applications.mysql.version` |\n\n"
                 "## Proof\n\n`check mysql --level deploys` on kind.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .mysql\n"),
    "mysql.yml": "parameters:\n  components:\n    mysql:\n      application: mysql\n",
}
MONGODB_RECIPE_FILES = {
    "README.md": "# mongodb\n\nMongoDB Community Server as a single instance, designed in kadet-hub on MongoDB's image.\n\n"
                 f"Source: `docker.io/mongodb/mongodb-community-server:9.0.4-ubi9-slim@sha256:{'e' * 64}`\n\nLevel: `deploys`\n\n"
                 "## Replaces\n\nThis recipe replaces the `mongodb` recipe of kadet-hub/examples.\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.mongodb\n```\n\n"
                 "## Required parameters\n\n`applications.mongodb.password` must be set.\n\n"
                 "## Proof\n\n`check mongodb --level deploys` on kind.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .mongodb\n"),
    "mongodb.yml": "parameters:\n  components:\n    mongodb:\n      application: mongodb\n",
}
# CAT-37f: powerdns, designed on its project's image, a new page beside the examples recipe external-dns-powerdns.
POWERDNS_SOURCE = f"docker.io/powerdns/pdns-auth-51:5.1.5@sha256:{'d' * 64}"
POWERDNS_RECIPE_FILES = {
    "README.md": "# powerdns\n\nPowerDNS Authoritative Server with one zone in SQLite, designed in kadet-hub on PowerDNS's image.\n\n"
                 f"Source: `{POWERDNS_SOURCE}`\n\nLevel: `deploys`\n\n"
                 "## Replaces\n\nThis recipe replaces the PowerDNS part of the `external-dns-powerdns` recipe of kadet-hub/examples.\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.powerdns\n```\n\n"
                 "## Required parameters\n\n`applications.powerdns.api_key` must be set.\n\n"
                 "## Proof\n\n`check powerdns --level deploys` on kind.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .powerdns\n"),
    "powerdns.yml": "parameters:\n  components:\n    powerdns:\n      application: powerdns\n",
}

# CAT-37c: external-dns-powerdns, rebuilt from a chart of an HTTP repository, moved from kadet-hub/examples under the same name.
HTTP_CHART_SOURCE = f"https://kubernetes-sigs.github.io/external-dns/external-dns:1.23.0@sha256:{'6' * 64}"
EXTERNAL_DNS_RECIPE_FILES = {
    "README.md": "# external-dns-powerdns\n\nexternal-dns writing a record for every annotated Service into a zone on PowerDNS. PowerDNS is the included recipe `powerdns`.\n\n"
                 f"Source: `{HTTP_CHART_SOURCE}`\n\nLevel: `deploys`\n\n"
                 "## Replaces\n\nThis recipe replaces the `external-dns-powerdns` recipe of kadet-hub/examples.\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.external-dns-powerdns\n```\n\n"
                 "## Required parameters\n\n`applications.powerdns.api_key` must be set.\n\n"
                 "## Proof\n\n`check external-dns-powerdns --level deploys` on kind.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .external-dns-powerdns\n  - recipes.powerdns\n"),
    "external-dns-powerdns.yml": "parameters:\n  components:\n    external-dns-powerdns:\n      application: external-dns-powerdns\n",
}

# CAT-37f: kafka, designed on Strimzi's image and moved from kadet-hub/examples under the same name, with the prerequisite strimzi.
KAFKA_SOURCE = f"quay.io/strimzi/kafka:1.3.0-kafka-4.3.1@sha256:{'9' * 64}"
KAFKA_RECIPE_FILES = {
    "README.md": "# kafka\n\nApache Kafka as a KRaft cluster, designed in kadet-hub on Strimzi's operator.\n\n"
                 f"Source: `{KAFKA_SOURCE}`\n\nLevel: `deploys`\n\nRequires: `strimzi`\n\n"
                 "## Replaces\n\nThis recipe replaces the `kafka` recipe of kadet-hub/examples.\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.kafka\n```\n\n"
                 "## Required parameters\n\nNo parameter has to be set.\n\n"
                 "## Proof\n\n`check kafka --level deploys` on kind, with `strimzi` installed first.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .kafka\n"),
    "kafka.yml": "parameters:\n  components:\n    kafka:\n      application: kafka\n",
}
# CAT-37c: strimzi, the operator kafka requires, rebuilt from Strimzi's chart.
STRIMZI_RECIPE_FILES = {
    "README.md": "# strimzi\n\nThe Strimzi Cluster Operator, rendered by the kadet-hub `kubernetes` generator. Derived from Strimzi's chart:\n\n"
                 f"Source: `oci://quay.io/strimzi-helm/strimzi-kafka-operator:1.3.0@sha256:{'8' * 64}`\n\nLevel: `deploys`\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.strimzi\n```\n\n"
                 "## Required parameters\n\nNo parameter has to be set.\n\n"
                 "## Proof\n\n`check strimzi --level deploys` on kind.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .cluster-operator\n"),
    "cluster-operator.yml": "parameters:\n  components:\n    strimzi-cluster-operator:\n      application: strimzi\n",
}
# CAT-37c: postgresql, rebuilt from CloudNativePG's cluster chart and moved from kadet-hub/examples under the same name, with the prerequisite cnpg.
POSTGRESQL_RECIPE_FILES = {
    "README.md": "# postgresql\n\nOne CloudNativePG Cluster, rendered by the kadet-hub `cloudnative-pg` generator from CloudNativePG's chart `cluster`.\n\n"
                 f"Source: `oci://ghcr.io/cloudnative-pg/charts/cluster:0.9.0@sha256:{'4' * 64}`\n\nLevel: `deploys`\n\nRequires: `cnpg`\n\n"
                 "## Replaces\n\nThis recipe replaces the `postgresql` recipe of kadet-hub/examples.\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.postgresql\n```\n\n"
                 "## Required parameters\n\nNo parameter has to be set.\n\n"
                 "## Proof\n\n`check postgresql --level deploys` on kind, with `cnpg` installed first.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .cluster\n"),
    "cluster.yml": "parameters:\n  components:\n    postgresql:\n      application: postgresql\n",
}
# CAT-37c: cnpg, the operator postgresql requires, rebuilt from the project's chart.
CNPG_RECIPE_FILES = {
    "README.md": "# cnpg\n\nThe CloudNativePG operator, rendered by the kadet-hub `kubernetes` generator from the project's chart.\n\n"
                 f"Source: `oci://ghcr.io/cloudnative-pg/charts/cloudnative-pg:0.29.1@sha256:{'5' * 64}`\n\nLevel: `deploys`\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.cnpg\n```\n\n"
                 "## Required parameters\n\nNo parameter has to be set.\n\n"
                 "## Proof\n\n`check cnpg --level deploys` on kind.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .operator\n"),
    "operator.yml": "parameters:\n  components:\n    cnpg:\n      application: cnpg\n",
}

# CAT-37f: rabbitmq, designed on the official image and moved from kadet-hub/examples under the same name, with the prerequisite rabbitmq-cluster-operator.
RABBITMQ_SOURCE = f"docker.io/library/rabbitmq:4.3.6-management@sha256:{'5' * 64}"
RABBITMQ_RECIPE_FILES = {
    "README.md": "# rabbitmq\n\nRabbitMQ as a cluster of three nodes, designed in kadet-hub on the RabbitMQ Cluster Operator.\n\n"
                 f"Source: `{RABBITMQ_SOURCE}`\n\nLevel: `deploys`\n\nRequires: `rabbitmq-cluster-operator`\n\n"
                 "## Replaces\n\nThis recipe replaces the `rabbitmq` recipe of kadet-hub/examples.\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.rabbitmq\n```\n\n"
                 "## Required parameters\n\nNo parameter has to be set.\n\n"
                 "## Proof\n\n`check rabbitmq --level deploys` on kind, with `cert-manager` and then `rabbitmq-cluster-operator` installed first.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .rabbitmq\n"),
    "rabbitmq.yml": "parameters:\n  components:\n    rabbitmq:\n      application: rabbitmq\n",
}
# CAT-37g: rabbitmq-cluster-operator, rebuilt from the project's release manifest, which requires cert-manager.
RABBITMQ_MANIFEST = "https://github.com/rabbitmq/cluster-operator/releases/download/v2.23.1/cluster-operator.yml"
RABBITMQ_OPERATOR_RECIPE_FILES = {
    "README.md": "# rabbitmq-cluster-operator\n\nThe RabbitMQ Cluster Operator, rendered by the kadet-hub `kubernetes` generator from the project's release manifest.\n\n"
                 f"Source: `{RABBITMQ_MANIFEST}@sha256:{'7' * 64}`\n\nLevel: `deploys`\n\nRequires: `cert-manager`\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.rabbitmq-cluster-operator\n```\n\n"
                 "## Required parameters\n\nNo parameter has to be set.\n\n"
                 "## Proof\n\n`check rabbitmq-cluster-operator --level deploys` on kind, with `cert-manager` installed first.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .operator\n"),
    "operator.yml": "parameters:\n  components:\n    rabbitmq-cluster-operator:\n      application: rabbitmq-cluster-operator\n",
}

# CAT-37c: nextcloud, rebuilt from Nextcloud's chart, with the included recipes postgresql and valkey.
NEXTCLOUD_RECIPE_FILES = {
    "README.md": "# nextcloud\n\nNextcloud, rendered by the kadet-hub `kubernetes` generator from Nextcloud's Helm chart.\n\n"
                 f"Source: `oci://ghcr.io/nextcloud/helm/nextcloud:9.4.1@sha256:{'6' * 64}`\n\nLevel: `deploys`\n\nRequires: `gateway-api`\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.nextcloud\n```\n\n"
                 "## Required parameters\n\n`applications.nextcloud.host` must be set.\n\n"
                 "## Proof\n\n`check nextcloud --level deploys` on kind, with `cnpg` installed first.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - recipes.postgresql\n  - recipes.valkey\n  - .nextcloud\n"),
    "nextcloud.yml": "parameters:\n  components:\n    nextcloud:\n      application: nextcloud\n",
}

# CAT-37f: keycloak, designed on Keycloak's image and moved from kadet-hub/examples under the same name, with the prerequisites keycloak-operator and cert-manager and the included recipe postgresql.
KEYCLOAK_SOURCE = f"quay.io/keycloak/keycloak:26.8.1@sha256:{'3' * 64}"
KEYCLOAK_RECIPE_FILES = {
    "README.md": "# keycloak\n\nKeycloak as one `Keycloak` resource of the Keycloak Operator, designed in kadet-hub on Keycloak's image.\n\n"
                 f"Source: `{KEYCLOAK_SOURCE}`\n\nLevel: `deploys`\n\nRequires: `keycloak-operator`, `cert-manager`\n\n"
                 "## Replaces\n\nThis recipe replaces the `keycloak` recipe of kadet-hub/examples.\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.keycloak\n```\n\n"
                 "## Required parameters\n\n`applications.keycloak.host` must be set.\n\n"
                 "## Proof\n\n`check keycloak --level deploys` on kind, with `keycloak-operator`, `cert-manager` and, through `postgresql`, `cnpg` installed first.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .keycloak\n  - recipes.postgresql\n"),
    "keycloak.yml": "parameters:\n  components:\n    keycloak:\n      application: keycloak\n",
}
# CAT-37c: keycloak-operator, the operator keycloak requires, rebuilt from the project's chart.
KEYCLOAK_OPERATOR_RECIPE_FILES = {
    "README.md": "# keycloak-operator\n\nThe Keycloak Operator, rendered by the kadet-hub `kubernetes` generator from the project's chart.\n\n"
                 f"Source: `oci://quay.io/keycloak/keycloak-operator-helm:26.8.1@sha256:{'0' * 64}`\n\nLevel: `deploys`\n\n"
                 "## Include\n\n```yaml\nclasses:\n  - recipes.keycloak-operator\n```\n\n"
                 "## Required parameters\n\nNo parameter has to be set.\n\n"
                 "## Proof\n\n`check keycloak-operator --level deploys` on kind.\n",
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace("  - .controller\n  - .webhook\n", "  - .keycloak-operator\n"),
    "keycloak-operator.yml": "parameters:\n  components:\n    keycloak-operator:\n      application: keycloak-operator\n",
}

# CAT-37c, CAT-37e: the other recipes with a content page, as the chart or compose fixture under their own name.
NEW_RECIPES = tuple(
    (name, {k.replace(base, name): v.replace(base, name) for k, v in files.items()})
    for base, files, names in (
        ("cert-manager", CHART_RECIPE_FILES, ("authentik", "blackbox-exporter", "gitea", "immich", "jellyfin", "n8n", "netbox",
                                              "ollama", "open-webui", "semaphore", "mariadb", "wordpress", "forgejo", "memcached",
                                              "ghost", "home-assistant", "homepage", "litellm", "matrix-synapse", "mattermost",
                                              "qdrant", "rocketchat", "stirling-pdf", "zulip", "langfuse", "librechat", "mlflow", "stalwart")),
        ("miniflux", COMPOSE_RECIPE_FILES, ("paperless-ngx", "pihole", "searxng", "uptime-kuma", "vaultwarden", "umami",
                                            "actual", "ejabberd", "memos", "navidrome", "jitsi-meet")))
    for name in names)


def recipe_classes(root):
    """Writes the classes of every recipe page under root (an assets/classes or inventory/classes directory)."""
    for recipe, files in (("cert-manager", CHART_RECIPE_FILES), ("miniflux", COMPOSE_RECIPE_FILES), ("valkey", VALKEY_RECIPE_FILES),
                          ("mysql", MYSQL_RECIPE_FILES), ("mongodb", MONGODB_RECIPE_FILES), ("powerdns", POWERDNS_RECIPE_FILES),
                          ("external-dns-powerdns", EXTERNAL_DNS_RECIPE_FILES), ("kafka", KAFKA_RECIPE_FILES), ("strimzi", STRIMZI_RECIPE_FILES),
                          ("postgresql", POSTGRESQL_RECIPE_FILES), ("cnpg", CNPG_RECIPE_FILES),
                          ("keycloak", KEYCLOAK_RECIPE_FILES), ("keycloak-operator", KEYCLOAK_OPERATOR_RECIPE_FILES),
                          ("rabbitmq", RABBITMQ_RECIPE_FILES), ("rabbitmq-cluster-operator", RABBITMQ_OPERATOR_RECIPE_FILES),
                          ("nextcloud", NEXTCLOUD_RECIPE_FILES), *NEW_RECIPES):
        os.makedirs(os.path.join(root, "recipes", recipe), exist_ok=True)
        for name, text in files.items():
            with open(os.path.join(root, "recipes", recipe, name), "w", encoding="utf-8") as f:
                f.write(text)
    with open(os.path.join(root, "recipes.sha"), "w", encoding="utf-8") as f:
        f.write(CHART_RECIPE_SHA + "\n")


# CAT-38: recipe records as release/index.py writes them (REC-13), with the renders check of REC-12.
RECIPE_SCAN = dict(SCAN, checks=SCAN["checks"] + [{"id": "lint", "tool": "check 0.11.0"}, {"id": "renders", "tool": "check 0.11.0, kind v0.33.0"}])
RECIPE_SHA = "2" * 40


def recipe_record(name, d, version="1.0.0", yanked=None, generators=(("kubernetes", "1.7.0", "d"),), includes=(), capabilities=(), scan=RECIPE_SCAN):
    return {"digest": "sha256:" + d * 64, "yanked": yanked, "advisories": [], "published": "2026-10-26T15:53:43Z",
            "description": f"The {name} recipe {version}.", "license": "Apache-2.0", "owners": [331675722], "tree": "0" * 40, "level": "deploys",
            "chart": {"repo": "quay.io/jetstack/charts/cert-manager", "version": "v1.22.0", "digest": "sha256:" + "c" * 64},
            "generators": [{"name": n, "version": v, "digest": "sha256:" + x * 64} for n, v, x in generators],
            "includes": [{"name": n, "version": v, "digest": "sha256:" + x * 64} for n, v, x in includes],
            "output_capabilities": list(capabilities), "kinds": [{"group": "cert-manager.io", "version": "v1", "kind": "Certificate"}],
            "scan": scan, "output_diff": {"base": None, "error": "no earlier listed version"},
            "source": {"repo": "https://github.com/kadet-hub/recipes.git", "path": name, "tag": f"{name}-v{version}", "sha": RECIPE_SHA}}


LISTED_INDEX = {"serial": 64, "generators": {
    "kubernetes": {"1.7.0": record("d"), "1.7.1": record("e"), "1.9.0": record("9", yanked="renders a broken Service")}},
    "recipes": {
        "cert-manager": {"1.0.0": recipe_record("cert-manager", "a", yanked="wrong CRDs"),
                         "1.1.0": dict(recipe_record("cert-manager", "b", "1.1.0", generators=(("kubernetes", "1.7.1", "e"),),
                                                     capabilities=("admission-webhook",)), backends=["omegaconf"])},
        "valkey": {"1.0.0": recipe_record("valkey", "3", generators=(("kubernetes", "1.9.0", "9"),))},  # pins a yanked generator
        "external-dns-powerdns": {"1.0.0": recipe_record("external-dns-powerdns", "4", includes=(("powerdns", "1.0.0", "5"),), scan=SCAN)},
        "powerdns": {"1.0.0": {k: v for k, v in recipe_record("powerdns", "5").items() if k != "chart"}},  # designed: no chart
        "mysql": {"1.0.0": recipe_record("mysql", "6", yanked="entry removed")},  # every version yanked
        "no-page": {"1.0.0": recipe_record("no-page", "7")},  # no content page
    }}
# CAT-38: the cert-manager layer of 1.1.0, with another chart and generator pin than main, a relative link and a shortcode.
ARTIFACT_CHART = f"oci://quay.io/jetstack/charts/cert-manager:v1.22.0@sha256:{'c' * 64}"
CERT_MANAGER_LAYER = dict(CHART_RECIPE_FILES, **{
    "README.md": CHART_RECIPE_FILES["README.md"]
        .replace("oci://quay.io/jetstack/charts/cert-manager:v1.21.2", "oci://quay.io/jetstack/charts/cert-manager:v1.22.0")
        .replace("Derived from the chart:", "Derived from the chart {{< nonexistent >}}:")
        .replace("| `replicaCount` |", "| `webhook.timeoutSeconds` | `components.cert-manager-webhook.timeout` |\n| `replicaCount` |")
        .replace("on kind.\n\n## Replacing", "on kind with [the values](tests/values.yaml). {{% nonexistent %}}\n\n## Replacing"),
    "init.yml": CHART_RECIPE_FILES["init.yml"].replace(f"kubernetes:1.7.0@sha256:{'d' * 64}", f"kubernetes:1.7.1@sha256:{'e' * 64}"),
    "vendor/cert-manager.crds.yaml": "# not shown\n"})
LAYERS = {"cert-manager": CERT_MANAGER_LAYER, "valkey": VALKEY_RECIPE_FILES, "external-dns-powerdns": EXTERNAL_DNS_RECIPE_FILES,
          "powerdns": POWERDNS_RECIPE_FILES}
IDENTITY = f"https://github.com/{OWNER}/registry/.github/workflows/release.yml@refs/heads/main"


def recipe_layers(root, layers=LAYERS):
    """CAT-38: <root>/recipes/<name>.tar, each a recipe layer as release/build.py writes it (REC-11)."""
    os.makedirs(os.path.join(root, "recipes"), exist_ok=True)
    for name, files in layers.items():
        artifact(os.path.join(root, "recipes", f"{name}.tar"), files)
    return root


def build(index, tmp, artifacts=None, sboms=None, rekor=None, discussions=None, pages=None, diffs=None, wanted=None, gate=None, recipes=None, capture=False, root=HERE,
          security=None, wanted_recipes=None, playground=None):
    path = os.path.join(tmp, "index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f)
    out = os.path.join(tmp, "out")
    env = dict(os.environ, OWNER=OWNER, CATALOG_OFFLINE="1", CATALOG_ARTIFACTS=artifacts or os.path.join(tmp, "none"),
               CATALOG_SBOMS=sboms or os.path.join(tmp, "none"), CATALOG_REKOR=rekor or os.path.join(tmp, "none.json"),
               CATALOG_DISCUSSIONS=discussions or os.path.join(tmp, "none.json"),
               CATALOG_PAGES=pages or os.path.join(tmp, "none"), CATALOG_DIFFS=diffs or os.path.join(tmp, "none"),
               CATALOG_WANTED=wanted or os.path.join(tmp, "none.json"), CATALOG_GATE=gate or os.path.join(tmp, "none.json"),
               CATALOG_SECURITY=security or os.path.join(tmp, "none.json"), CATALOG_WANTED_RECIPES=wanted_recipes or os.path.join(tmp, "none.json"))
    if recipes is None:
        recipes = os.path.join(tmp, "recipes")
        recipe_classes(os.path.join(recipes, "inventory", "classes"))
    env["CATALOG_RECIPES"] = recipes
    env.pop("CATALOG_PLAYGROUND", None)
    if playground:
        env["CATALOG_PLAYGROUND"] = playground
    subprocess.run([os.path.join(root, "build"), path, out], env=env, check=True, capture_output=capture, text=capture)
    return out


# CAT-36e: the posts that moved to /guides/; each keeps its old URL as an alias (CAT-36f).
MOVED_POSTS = {"actions-runner-controller-dind", "apiserver-dry-run", "bitnami", "cert-manager-helm-chart-patches", "config-tools", "first-platform",
               "gvisor-ci", "helm-chart-vs-kapitan-inventory", "helm-chart-vs-operator", "kube-prometheus-stack-dashboards",
               "kustomize-delete-resource-helm-chart", "kustomize-json-patch-helm-chart", "kustomize-patch-env-helm-chart",
               "nextcloud-helm-chart-bitnami", "renovate-automerge-required-reviews", "same-app", "verify-oci"}
CONTENT = os.path.join(HERE, "site", "content")
CONNECTIVES = {"a", "an", "the", "on", "in", "for", "with", "to", "of"}  # CAT-11m: left out when a title is matched with a query


def front_matter(path):
    with open(path, encoding="utf-8") as f:
        return f.read().split("\n---\n", 1)[0]


def titles(field="title"):
    """CAT-11j: the hand-written title (or another front matter field) of every page under content/, by its path without .md."""
    found = {}
    for path in sorted(glob.glob(os.path.join(CONTENT, "**", "*.md"), recursive=True)):
        m = re.search(rf'^{field}: "?(.*?)"?$', front_matter(path), re.MULTILINE)
        if m:
            found[os.path.relpath(path, CONTENT)[:-3]] = m.group(1)
    return found


def title_words(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def joined(text):
    """CAT-11m: the words of a query or title without connectives, run together."""
    return "".join(w for w in title_words(text) if w not in CONNECTIVES)


def leads(title, query):
    """CAT-11m: the number of the title's words that make up the query, 0 when it does not lead with it."""
    want = joined(query)
    got = ""
    for i, w in enumerate(title_words(title), 1):
        got += "" if w in CONNECTIVES else w
        if len(got) >= len(want):
            return i if got.startswith(want) else 0
    return 0


def compares(title):
    """CAT-11a: the number of words of a comparison's "<A> vs <B>" up to the first colon or comma, 0 for any other title."""
    head = re.split(r"[:,]", title, maxsplit=1)[0]
    return len(title_words(head)) if " vs " in head else 0


def title_queries():
    """CAT-11f: every title the table names, with the queries of the rows that name it; "same guide" or "same post" is the row above."""
    with open(os.path.join(HERE, "..", "docs", "specs", "catalog.md"), encoding="utf-8") as f:
        table = f.read().split("\n- CAT-11f:", 1)[1].split("\n- CAT-", 1)[0]
    found, above = {}, []
    for query, pages in re.findall(r"^ *\| (.+) \| (.+) \|$", table, re.MULTILINE):
        if query == "Query":
            continue
        also = [a for group in re.findall(r"\(also ([^)]*)\)", query) for a in re.findall(r'"([^"]+)"', group)]
        query = re.sub(r"\((also|checked|Google)[^)]*\)", "", query)
        named = re.findall(r'(?:guide|blog post) "([^"]+)"', pages) or (above if re.search(r"\bsame (guide|post)\b", pages) else [])
        for title in named:
            found.setdefault(title, []).extend([q.strip() for q in query.split(",") if q.strip()] + also)
        above = named or above
    return found


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
        wanted_recipes = os.path.join(cls.tmp.name, "wanted-recipes.json")
        with open(wanted_recipes, "w", encoding="utf-8") as f:
            json.dump(WANTED_RECIPES, f)
        cls.out = build(SITE_INDEX, cls.tmp.name, arts, os.path.dirname(sboms), rekor, discussions, pages, os.path.dirname(diffs), wanted, gate,
                        wanted_recipes=wanted_recipes)

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

    def test_pages_without_image_report_say_not_scanned(self):  # CAT-39, CAT-39c
        self.assertIn("<dt>Image security</dt><dd>Not scanned: no image scan was available when this page was built.</dd>", self.page("generators", "demo"))
        self.assertFalse(os.path.exists(os.path.join(self.out, "security")))

    def test_owner_without_login_shows_the_user_id(self):
        self.assertIn("<dt>Maintainer</dt><dd>331675722</dd>", self.page())

    def test_values_are_escaped(self):
        for html in (self.page(), self.page("generators", "demo")):
            self.assertNotIn("<script>alert", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_no_resource_from_another_origin(self):
        for html in self.pages():
            for ref in re.findall(r'<(?:script|link|img)\b[^>]*\b(?:src|href)="([^"]*)"', html):
                if not re.search(r'rel="(canonical|me)"', html[html.rfind("<", 0, html.index(ref)):html.index(ref)]):  # load nothing (CAT-53)
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

    def test_mobile_header_and_filters(self):  # CAT-9a
        html = self.page()
        self.assertRegex(html, r'(?s)<nav id="site-nav">.*</nav>\s*<button type="button" id="theme"[^>]*hidden>.*?</button>\s*'
                               r'<button type="button" id="menu" class="icon-button" aria-label="Menu" aria-expanded="false" aria-controls="site-nav" hidden>')
        self.assertRegex(html, r'<button type="button" id="tag-toggle" class="chip" aria-expanded="false" aria-controls="tags" hidden>Filter by tag')
        self.assertIn('<symbol id="i-menu"', html)
        with open(os.path.join(self.out, "style.css"), encoding="utf-8") as f:
            css = f.read()
        self.assertIn("#menu, #tag-toggle { display: none; }", css)
        narrow = re.search(r"@media \(max-width: 48rem\) \{(.*?)\n\}", css, re.DOTALL).group(1)
        for rule in ('header.site[data-menu="closed"] nav { display: none; }', '.filters[data-tags="closed"] .tag-filter { display: none; }',
                     ".filters { position: static; }"):
            self.assertIn(rule, narrow)

    def css(self):
        with open(os.path.join(self.out, "style.css"), encoding="utf-8") as f:
            return f.read()

    def test_words_wrap_between_words(self):  # CAT-9b
        css = self.css()
        self.assertRegex(css, r"\n\.facts dt \{[^}]*flex: none;")
        self.assertNotRegex(css, r"\.scan-head \{[^}]*display: flex")
        narrow = re.search(r"@media \(max-width: 60rem\) \{(.*?)\n\}", css, re.DOTALL).group(1)
        self.assertIn(".compat th:first-child { width: auto; }", narrow)

    def test_text_reaches_aa(self):  # CAT-54
        css = self.css()
        colours = {n: (light, dark) for n, light, dark in re.findall(r"--([\w-]+): light-dark\((#[0-9a-f]{6}), (#[0-9a-f]{6})\);", css)}
        pairs = [(fg, bg) for fg in ("text", "text-muted", "accent", "accent-strong", "warn", "ok") for bg in ("bg", "bg-subtle", "surface")]
        pairs += [("accent-strong", "accent-bg"), ("text-muted", "accent-bg"), ("on-accent", "accent"), ("warn", "warn-bg"), ("ok", "ok-bg")]
        for fg, bg in pairs:
            for theme in (0, 1):
                self.assertGreaterEqual(contrast(colours[fg][theme], colours[bg][theme]), 4.5, (fg, bg, ("light", "dark")[theme]))
        # Opacity between 0 and 1 fades text below what its tokens reach; only a disabled control may.
        faded = {sel.strip() for sel, value in re.findall(r"([^{}]+)\{[^}]*opacity: ([.\d]+)", css) if 0 < float(value) < 1}
        self.assertEqual(faded, {".chip:disabled"})

    def test_targets_reach_24px(self):  # CAT-55
        css = self.css()
        for selector in (".fact-link", ".permalink"):
            rule = re.search(rf"^{re.escape(selector)} \{{([^}}]*)\}}", css, re.MULTILINE).group(1)
            self.assertIn("min-width: 24px;", rule, selector)
            self.assertIn("min-height: 24px;", rule, selector)

    def test_issue_forms_are_linked(self):
        links = [__import__("html").unescape(h) for h in re.findall(r'href="([^"]*issues/new[^"]*)"', self.page("generators", "demo"))]
        self.assertIn(f"https://github.com/{OWNER}/registry/issues/new?generator=demo&template=generator-report.yml&title=%5Breport%5D+demo%3A+&version=1.10.0", links)
        self.assertIn(f"https://github.com/{OWNER}/registry/issues/new?template=generator-request.yml", self.page())
        for form in ("generator-report", "generator-request"):
            self.assertTrue(os.path.isfile(os.path.join(HERE, "..", ".github", "ISSUE_TEMPLATE", f"{form}.yml")))

    def test_quickstart_linked(self):  # CAT-40, CAT-40a, CAT-40b
        nav = re.search(r'<nav id="site-nav">(.*?)</nav>', self.page(), re.DOTALL).group(1)
        self.assertRegex(nav, r'^\s*<a href="\./quickstart/">Quickstart</a>\s*<a href="[^"]*/docs/consumers\.md">Use</a>')
        recipes = glob.glob(os.path.join(self.out, "recipes", "*", "index.html"))
        self.assertGreater(len(recipes), 30)
        for path in recipes:
            with open(path, encoding="utf-8") as f:
                self.assertIn('<h2>Fetching it</h2>\n<p>The <a href="../../quickstart/">quickstart</a>', f.read(), path)
        page = self.page("quickstart")
        # Not listed in this index: no steps, the recipe page instead.
        self.assertIn('<p class="warning">The uptime-kuma recipe has no version this page can pin right now.', page)
        self.assertNotIn("<pre", page)

        def links(heading):
            section = page.split(f">{heading}</h2>", 1)[1].split("<h2", 1)[0]
            return [posixpath.normpath(posixpath.join("/quickstart/", h)) for h in re.findall(r'href="([^"#]+)"', section)]
        kustomize = sorted(f"/guides/{os.path.basename(p)[:-3]}" for p in glob.glob(os.path.join(HERE, "site", "content", "guides", "kustomize-*.md")))
        self.assertEqual(len(kustomize), 3)
        for heading, posts in (("Coming from Helm?", ["/guides/helm-chart-vs-kapitan-inventory", "/guides/same-app", "/guides/bitnami-chart-alternatives"]),
                               ("Coming from Kustomize?", ["/guides/same-app", *kustomize])):
            for post in posts:
                self.assertIn(post, links(heading))
                self.assertTrue(os.path.isfile(os.path.join(self.out, post.strip("/"), "index.html")), post)

    def test_stacks_linked(self):  # CAT-47
        nav = re.search(r'<nav id="site-nav">(.*?)</nav>', self.page(), re.DOTALL).group(1)
        self.assertRegex(nav, r'<a href="\./recipes/">Recipes</a>\s*<a href="\./stacks/">Stacks</a>')
        with open(os.path.join(self.out, "llms.txt"), encoding="utf-8") as f:
            using = f.read().split("\n## Using generators\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("\n- [Stacks](https://kadet-hub.org/stacks/): ", using)

    def test_conversion_events(self):  # CAT-42
        recipe = self.page("recipes", "miniflux")  # from main: the git fetch inventory
        self.assertIn('data-copy="fetch" aria-label="Copy fetch inventory" data-goatcounter-click="copy-fetch-inventory/recipes/miniflux" '
                      'data-goatcounter-title="Copy fetch inventory" hidden>', recipe)
        self.assertRegex(recipe, r'<a href="https://github\.com/kadet-hub/recipes/tree/[0-9a-f]{40}/miniflux" '
                                 r'data-goatcounter-click="source-repo/recipes/miniflux">kadet-hub/recipes</a>')
        generator = self.page("generators", "demo")
        verify = re.findall(r'data-copy="(verify-\d+)" aria-label="Copy verify command for [^"]+" data-goatcounter-click="copy-verify/generators/demo" '
                            r'data-goatcounter-title="Copy verify command for [^"]+"', generator)
        self.assertEqual(verify, re.findall(r'<pre id="(verify-\d+)">', generator))
        self.assertIn('<a href="https://github.com/example/demo" data-goatcounter-click="source-repo/generators/demo">', generator)
        self.assertNotIn("data-goatcounter-click", re.sub(r'data-copy="(fetch|verify-\d+)"[^>]*>|<a href="[^"]*" data-goatcounter-click="source-repo/[^"]*">', "",
                                                            recipe + generator))  # nothing else
        self.assertIn("is counted as an event", self.page("privacy"))
        with open(os.path.join(HERE, "site", "static", "count.js"), encoding="utf-8") as f:
            self.assertIn('document.querySelectorAll("*[data-goatcounter-click]")', f.read())  # bound on load

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
        ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)]
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
        code = re.search(r'<pre class="diff"><code>(.*?)</code></pre>', latest, re.DOTALL).group(1)
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
        with (tempfile.TemporaryDirectory() as tmp,  # a record without a verified text
              open(os.path.join(build({"serial": 1, "generators": {"g": {"1.0.0": dict(record("e"), output_diff=OUTPUT_DIFF)}}}, tmp),
                                "generators", "g", "index.html"), encoding="utf-8") as f):
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
        self.assertIn("\n- [Kafka on Kubernetes in KRaft mode under Strimzi](https://kadet-hub.org/recipes/kafka/index.md): Bitnami kafka Helm chart alternative: Kapitan", text)  # CAT-37b
        self.assertEqual(text.count("](https://kadet-hub.org/recipes/"), 55)
        self.assertIn("\n- [cert-manager on Kubernetes, matched to its chart object by object](https://kadet-hub.org/recipes/cert-manager/index.md): cert-manager Helm chart alternative:", text)  # CAT-37c
        self.assertIn("\n- [demo](https://kadet-hub.org/generators/demo/index.md): <script>alert(1)</script>\n", text)  # text, as typed
        self.assertIn("\n- [plain](https://kadet-hub.org/generators/plain/index.md): Renders a [ConfigMap](x) ## Not a heading 31m*bold*\n", text)
        self.assertNotIn("generators/old/", text)  # CAT-26: no listed version
        self.assertIn("\n- [Writing a Kapitan generator](https://kadet-hub.org/guides/writing-a-kapitan-generator/index.md): How to write a reusable", text)
        self.assertEqual(text.count("](https://kadet-hub.org/guides/"), 29)
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
            text = _unescape(re.search(rf'<pre id="{block}"><code>(.*?)</code></pre>', html, re.DOTALL).group(1))
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
            self.assertRegex(html, r'(?s)<nav id="site-nav">.*<a href="[./]*compatibility/">Compatibility</a>.*</nav>')
            self.assertRegex(html, r'(?s)<nav id="site-nav">.*<a href="[./]*recipes/">Recipes</a>.*</nav>')  # CAT-37
            self.assertRegex(html, r'(?s)<nav id="site-nav">.*<a href="[./]*playground/">Playground</a>.*</nav>')  # PG-4

    def test_playground_without_its_files(self):  # PG-13
        page = self.page("playground")
        self.assertIn("The playground is not part of this build of the site.", page)
        self.assertNotIn("playground.js", page)
        self.assertNotIn('id="pg-start"', page)

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
                     "bitnami-chart-alternatives", "helm-alternatives-for-kubernetes", "talos-machine-config", "helm-vs-terraform", "argocd-vs-flux",
                     "patch-helm-chart"):
            self.assertIn(f"guides/{slug}/", guides)
            self.page("guides", slug)
        self.assertIn('<h2 id="generator-contract">Generator contract</h2>', self.page("guides", "writing-a-kapitan-generator"))  # CAT-24

    def test_recipes(self):  # CAT-37, CAT-37b
        index = self.page("recipes")
        self.assertEqual(sorted(re.findall(r'<li><a href="[./]*recipes/([^/]+)/">', index)), sorted(["cert-manager", "miniflux", "valkey", "mysql", "mongodb", "powerdns", "external-dns-powerdns", "kafka", "strimzi", "postgresql", "cnpg", "keycloak", "keycloak-operator", "rabbitmq", "rabbitmq-cluster-operator", "nextcloud", *(name for name, _ in NEW_RECIPES)]))
        self.assertIn("<title>Kubernetes recipes that replace Helm and Bitnami charts</title>", index)  # CAT-11a
        self.assertIn(" The files are read from kadet-hub/recipes when the site is built.", index)
        chart = index
        self.assertRegex(chart, r'(?s)<h2>Rebuilt from a Helm chart, a release manifest or a Docker Compose file, or designed on an image</h2>.*recipes/cert-manager/">.*Proof level: <code>deploys</code>')
        self.assertRegex(chart, r'recipes/miniflux/">.*?Proof level: <code>deploys</code></p></li>')  # CAT-37e
        self.assertRegex(chart, r'recipes/valkey/">.*?Proof level: <code>deploys</code>')  # CAT-38a: same URL, now a chart recipe
        self.assertRegex(chart, r'recipes/mysql/">.*?Proof level: <code>deploys</code></p></li>')  # CAT-37f
        self.assertRegex(chart, r'recipes/mongodb/">.*?Proof level: <code>deploys</code></p></li>')  # CAT-37f
        self.assertRegex(chart, r'recipes/powerdns/">.*?Proof level: <code>deploys</code></p></li>')  # CAT-37f
        self.assertRegex(chart, r'recipes/external-dns-powerdns/">.*?Proof level: <code>deploys</code></p></li>')  # CAT-38a: same URL, now a chart recipe
        self.assertRegex(chart, r'recipes/kafka/">.*?Proof level: <code>deploys</code></p></li>')  # CAT-37f, CAT-38a
        self.assertRegex(chart, r'recipes/strimzi/">.*?Proof level: <code>deploys</code></p></li>')  # CAT-37c
        self.assertRegex(chart, r'recipes/postgresql/">.*?Proof level: <code>deploys</code>')  # CAT-38a: same URL, now a chart recipe
        self.assertRegex(chart, r'recipes/cnpg/">.*?Proof level: <code>deploys</code></p></li>')  # CAT-37c
        self.assertRegex(chart, r'recipes/keycloak/">.*?Proof level: <code>deploys</code>')  # CAT-37f, CAT-38a: same URL, now a chart recipe
        self.assertRegex(chart, r'recipes/keycloak-operator/">.*?Proof level: <code>deploys</code></p></li>')  # CAT-37c
        self.assertRegex(chart, r'recipes/rabbitmq/">.*?Proof level: <code>deploys</code></p></li>')  # CAT-37f, CAT-38a
        self.assertRegex(chart, r'recipes/rabbitmq-cluster-operator/">.*?Proof level: <code>deploys</code></p></li>')  # CAT-37g
        self.assertIn('href="../guides/bitnami-chart-alternatives/">Bitnami chart alternatives</a> lists', index)  # CAT-11f: one page per query
        page = self.page("recipes", "postgresql")
        self.assertIn("<title>PostgreSQL on Kubernetes: CloudNativePG clusters from Kapitan</title>", page)  # no room for the suffix
        self.assertIn('<meta name="description" content="Bitnami postgresql Helm chart alternative: Kapitan', page)
        self.assertNotIn("without Bitnami", page)
        self.assertIn("<h2>Replaces</h2>\n<p>This recipe replaces the <code>postgresql</code> recipe of kadet-hub/examples.", page)
        self.assertIn("<title>CloudNativePG on Kubernetes: the operator from Kapitan classes</title>", self.page("recipes", "cnpg"))  # no room for the suffix
        self.assertIn("<title>MongoDB on Kubernetes with Community Server, as a Kapitan class</title>", self.page("recipes", "mongodb"))  # no room for the suffix
        self.assertIn("<title>PowerDNS on Kubernetes, the Authoritative Server in Kapitan</title>", self.page("recipes", "powerdns"))  # no room for the suffix
        self.assertIn("<title>external-dns and PowerDNS on Kubernetes as one Kapitan recipe</title>", self.page("recipes", "external-dns-powerdns"))  # no room for the suffix
        self.assertIn("<title>Kafka on Kubernetes in KRaft mode under Strimzi · kadet-hub</title>", self.page("recipes", "kafka"))
        self.assertIn("<title>Strimzi on Kubernetes, its Kafka operator chart in Kapitan</title>", self.page("recipes", "strimzi"))  # no room for the suffix
        self.assertIn("<title>RabbitMQ on Kubernetes through the Cluster Operator and Kapitan</title>", self.page("recipes", "rabbitmq"))  # no room for the suffix
        self.assertIn("<title>RabbitMQ Cluster Operator on Kubernetes from its release manifest</title>", self.page("recipes", "rabbitmq-cluster-operator"))  # no room for the suffix
        page = self.page("recipes", "keycloak")
        self.assertIn("<title>Keycloak on Kubernetes run by the Keycloak Operator · kadet-hub</title>", page)
        self.assertIn('<meta name="description" content="Bitnami keycloak Helm chart alternative: Kapitan', page)
        self.assertNotIn("without Bitnami", page)
        self.assertIn("<title>Keycloak Operator on Kubernetes, its chart rebuilt for Kapitan</title>", self.page("recipes", "keycloak-operator"))  # no room for the suffix
        page = self.page("recipes", "nextcloud")
        self.assertIn("<title>Nextcloud on Kubernetes, its own Helm chart rebuilt in Kapitan</title>", page)  # no room for the suffix
        self.assertIn('<meta name="description" content="Nextcloud Helm chart alternative: Kapitan', page)
        self.assertFalse(os.path.exists(os.path.join(self.out, "recipes", "index.md")))
        guide = self.page("guides", "bitnami-chart-alternatives")
        for name in ["cert-manager", "valkey", "mysql", "mongodb", "external-dns-powerdns", "kafka", "postgresql", "keycloak", "rabbitmq"]:
            self.assertIn(f'href="../../recipes/{name}/"', guide)
        with open(os.path.join(self.out, "sitemap.xml"), encoding="utf-8") as f:
            self.assertIn("https://kadet-hub.org/recipes/kafka/<", f.read())

    def test_recipe_sources_listed(self):  # CAT-37h
        index = self.page("recipes")

        def entry(name):
            return re.search(rf'<li><a href="[./]*recipes/{name}/">.*?</li>', index, re.DOTALL)[0]

        self.assertIn("<p>Source chart: <code>oci://quay.io/jetstack/charts/cert-manager:v1.21.2</code></p>", entry("cert-manager"))
        self.assertIn("<p>Source chart: <code>https://kubernetes-sigs.github.io/external-dns/external-dns:1.23.0</code></p>",
                      entry("external-dns-powerdns"))
        self.assertIn("<p>Source: Docker Compose file <code>miniflux/v2</code> (<code>contrib/docker-compose/basic.yml</code>)</p>", entry("miniflux"))
        self.assertIn("<p>Source: container image <code>container-registry.oracle.com/mysql/community-server:9.7.4</code></p>", entry("mysql"))
        self.assertIn("<p>Source: release manifest <code>rabbitmq/cluster-operator@v2.23.1</code> (<code>cluster-operator.yml</code>)</p>",
                      entry("rabbitmq-cluster-operator"))
        for name in ("miniflux", "mysql", "rabbitmq-cluster-operator"):  # CAT-37e, CAT-37f, CAT-37g
            self.assertNotIn("chart", entry(name).split("<p>Source")[1])
        self.assertEqual(len(re.findall(r"<p>Source", index)), len(re.findall(r'<li><a href="[./]*recipes/', index)))
        self.assertNotIn("sha256:", index)
        self.assertNotIn("2" * 40, index)

    def test_recipe_finder(self):  # CAT-37i
        index = self.page("recipes")
        find = re.search(r'<div class="recipe-find" role="search" hidden>.*?</div>', index, re.DOTALL)[0]
        self.assertIn('<label for="recipe-search">Find a recipe by Helm chart, image or app</label>', find)
        self.assertRegex(find, r'<input id="recipe-search" type="search" [^>]*autocomplete="off"')
        self.assertIn('<p id="recipe-result" class="result" aria-live="polite"></p>', find)
        self.assertLess(index.index('class="recipe-find"'), index.index('<ul class="guide-list">'))
        empty = re.search(r'<p id="recipe-empty" class="empty" hidden>.*?</p>', index, re.DOTALL)[0]
        self.assertIn('<button type="button" id="recipe-reset" class="link">Show all</button>', empty)
        for href in ("../guides/bitnami-chart-alternatives/", "../wanted/#recipes",
                     f"https://github.com/{OWNER}/recipes/issues/new?template=recipe-request.yml"):  # CAT-41
            self.assertIn(f'href="{href}"', empty)
        self.assertIn('<link rel="canonical" href="https://kadet-hub.org/recipes/">', index)  # CAT-11: ?q= shares it
        with open(os.path.join(self.out, "site.js"), encoding="utf-8") as f:
            self.assertIn('document.getElementById("recipe-search")', f.read())

    def test_http_chart_recipe(self):  # CAT-37c
        page = self.page("recipes", "external-dns-powerdns")
        self.assertIn(f"<li>Source chart: <code>{HTTP_CHART_SOURCE}</code></li>", page)
        self.assertIn("<li><a href=\"../../glossary/#proof-level\">Proof level</a>: <code>deploys</code>, compared with the chart by the kadet-hub/recipes CI</li>", page)
        fetch = _unescape(re.search(r'<pre id="fetch"><code>(.*?)</code></pre>', page, re.DOTALL).group(1))
        self.assertEqual(re.findall(r"        subdir: (\S+)\n", fetch), ["external-dns-powerdns", "powerdns"])  # the recipe it includes, REC-16
        self.assertEqual(re.findall(r"output_path: inventory/classes/recipes/(\S+)", fetch), ["external-dns-powerdns", "powerdns"])
        self.assertEqual(fetch.count(f"ref: {CHART_RECIPE_SHA}\n"), 2)
        self.assertIn(f"- Source chart: {HTTP_CHART_SOURCE}\n", self.markdown("recipes", "external-dns-powerdns"))

    def test_recipe_prerequisite(self):  # CAT-37c
        page = self.page("recipes", "kafka")
        self.assertIn('<li>Prerequisites, installed once per cluster before the recipe: <a href="../../recipes/strimzi/"><code>strimzi</code></a></li>', page)
        self.assertRegex(page, r"(?s)Proof level</a>: .*Prerequisites, .*<li>Generators: ")
        fetch = _unescape(re.search(r'<pre id="fetch"><code>(.*?)</code></pre>', page, re.DOTALL).group(1))
        self.assertEqual(re.findall(r"        subdir: (\S+)\n", fetch), ["kafka"])  # strimzi has its own target and page
        self.assertIn("\n- Prerequisites, installed once per cluster before the recipe: strimzi\n- Generators: ", self.markdown("recipes", "kafka"))
        self.assertIn('<li>Prerequisites, installed once per cluster before the recipe: <a href="../../recipes/cnpg/"><code>cnpg</code></a></li>',
                      self.page("recipes", "postgresql"))
        self.assertNotIn("Prerequisites", self.page("recipes", "strimzi"))
        self.assertNotIn("Prerequisites", self.page("recipes", "cnpg"))
        both = ("Prerequisites, installed once per cluster before the recipe: ", "rabbitmq-cluster-operator", "cert-manager")  # the operator's own prerequisite follows it
        self.assertIn(f'<li>{both[0]}<a href="../../recipes/{both[1]}/"><code>{both[1]}</code></a>, <a href="../../recipes/{both[2]}/"><code>{both[2]}</code></a></li>',
                      self.page("recipes", "rabbitmq"))
        self.assertIn(f"\n- {both[0]}{both[1]}, {both[2]}\n- Generators: ", self.markdown("recipes", "rabbitmq"))
        self.assertIn(f'<li>{both[0]}<a href="../../recipes/{both[2]}/"><code>{both[2]}</code></a></li>', self.page("recipes", "rabbitmq-cluster-operator"))
        self.assertNotIn("Prerequisites", self.markdown("recipes", "mysql"))
        keycloak = self.page("recipes", "keycloak")  # cnpg is required by the included postgresql
        links = ", ".join(f'<a href="../../recipes/{n}/"><code>{n}</code></a>' for n in ("keycloak-operator", "cert-manager", "cnpg"))
        self.assertIn(f"<li>{both[0]}{links}</li>", keycloak)
        fetch = _unescape(re.search(r'<pre id="fetch"><code>(.*?)</code></pre>', keycloak, re.DOTALL).group(1))
        self.assertEqual(re.findall(r"        subdir: (\S+)\n", fetch), ["keycloak", "postgresql"])
        self.assertIn(f"\n- {both[0]}keycloak-operator, cert-manager, cnpg\n- Generators: ", self.markdown("recipes", "keycloak"))
        self.assertNotIn("Prerequisites", self.page("recipes", "keycloak-operator"))

    def test_release_manifest_recipe(self):  # CAT-37g
        page = self.page("recipes", "rabbitmq-cluster-operator")
        self.assertIn(f'<li>Source: release manifest <a href="{RABBITMQ_MANIFEST}"><code>rabbitmq/cluster-operator@v2.23.1</code></a> '
                      f'(<code>cluster-operator.yml</code>), <code>sha256:{"7" * 64}</code></li>', page)
        self.assertIn("<li><a href=\"../../glossary/#proof-level\">Proof level</a>: <code>deploys</code>, compared with the manifest by the kadet-hub/recipes CI</li>", page)
        self.assertNotIn("Source chart", page)
        self.assertNotIn("compared with the chart", page)
        self.assertIn(f"\n- Source: release manifest rabbitmq/cluster-operator@v2.23.1 (cluster-operator.yml), sha256:{'7' * 64}: {RABBITMQ_MANIFEST}\n"
                      "- Proof level: deploys, compared with the manifest by the kadet-hub/recipes CI\n", self.markdown("recipes", "rabbitmq-cluster-operator"))

    def test_chart_recipe(self):  # CAT-37c
        page = self.page("recipes", "cert-manager")
        self.assertIn("<title>cert-manager on Kubernetes, matched to its chart object by object</title>", page)  # no room for the suffix
        self.assertIn('<p class="lead">The controller and the webhook, rendered by the kadet-hub <code>kubernetes</code> generator. Derived from the chart.</p>', page)
        self.assertIn(f"<li>Source chart: <code>oci://quay.io/jetstack/charts/cert-manager:v1.21.2@sha256:{'c' * 64}</code></li>", page)
        self.assertIn("<li><a href=\"../../glossary/#proof-level\">Proof level</a>: <code>deploys</code>, compared with the chart by the kadet-hub/recipes CI</li>", page)
        self.assertIn(f'<li>Generators: <a href="../../generators/kubernetes/#v1.7.0">kubernetes 1.7.0</a> <code>sha256:{"d" * 64}</code></li>', page)
        self.assertIn("<li><code>recipes.cert-manager.controller</code> (<code>controller.yml</code>): <code>cert-manager</code></li>", page)
        self.assertIn("<li><code>recipes.cert-manager.webhook</code> (<code>webhook.yml</code>): <code>cert-manager-webhook</code></li>", page)
        self.assertIn("<li><code>recipes.cert-manager.crds</code> (<code>crds.yml</code>), an option</li>", page)
        self.assertIn('<pre id="include"><code>classes:\n  - recipes.cert-manager\n  - recipes.cert-manager.crds   # the chart&#39;s crds.enabled</code></pre>', page)
        fetch = _unescape(re.search(r'<pre id="fetch"><code>(.*?)</code></pre>', page, re.DOTALL).group(1))
        self.assertIn(f"      - type: git\n        source: https://github.com/{OWNER}/recipes.git\n        ref: {CHART_RECIPE_SHA}\n"
                      "        subdir: cert-manager\n        output_path: inventory/classes/recipes/cert-manager", fetch)
        self.assertIn('<pre id="commands"><code>kapitan compile --inventory-path fetch --fetch --output-path .\nkapitan compile --fetch</code></pre>', page)
        self.assertIn(f'<a href="https://github.com/{OWNER}/recipes#using-a-recipe">Using a recipe</a>', page)
        self.assertEqual([h for h in re.findall(r"<h2>([^<]+)</h2>", page) if h != "Used in stacks"],  # CAT-48 follows the real posts' dates; Stacks tests it
                         ["What it deploys", "Required parameters", "Include", "Fetching it", "Settings", "Left out", "Renamed RBAC objects", "Proof"])
        self.assertIn("<h2>Required parameters</h2>\n<p>No parameter has to be set.</p>", page)
        self.assertIn("<td><code>replicaCount</code></td>", page)  # rendered from the README
        self.assertIn("<td><code>cert-manager:leaderelection</code></td>", page)
        self.assertNotIn("alert(8)</script>", page)  # raw HTML is dropped
        self.assertNotIn("Not tested.", page)
        self.assertIn(f'<a href="https://github.com/{OWNER}/recipes/tree/{CHART_RECIPE_SHA}/cert-manager" data-goatcounter-click="source-repo/recipes/cert-manager">kadet-hub/recipes</a>', page)
        self.assertNotIn("Bitnami", page.split("<main")[1])
        md = self.markdown("recipes", "cert-manager")
        self.assertTrue(md.startswith("# cert-manager on Kubernetes, matched to its chart object by object\n\n> The controller and the webhook, rendered by the kadet-hub `kubernetes` generator."))
        self.assertIn(f"\n- Generators: kubernetes 1.7.0 (sha256:{'d' * 64})\n", md)
        self.assertIn("\n- Option recipes.cert-manager.crds (crds.yml)\n", md)
        self.assertIn(f"ref: {CHART_RECIPE_SHA}\n", md)
        self.assertIn("\n## Required parameters\n\nNo parameter has to be set.\n\n## Include\n", md)
        self.assertIn("\n## Settings\n\n| Chart value | Inventory |\n", md)
        self.assertIn("\n## Proof\n\n`check cert-manager --level deploys` on kind.\n", md)
        self.assertNotIn("## Replaces", md)
        page = self.page("recipes", "valkey")  # Replaces after the source and the level
        self.assertIn("<title>Valkey (Redis) on Kubernetes, the BSD-licensed fork in Kapitan</title>", page)  # no room for the suffix
        self.assertIn("<h2>Replaces</h2>\n<p>This recipe replaces the <code>valkey</code> recipe of kadet-hub/examples.", page)
        self.assertIn("<td>StatefulSet <code>valkey</code></td>", page)
        self.assertNotIn("alert(9)</script>", page)
        self.assertRegex(page, r"(?s)Proof level</a>: .*</ul>\n<h2>Replaces</h2>.*<h2>What it deploys</h2>")
        md = self.markdown("recipes", "valkey")
        self.assertRegex(md, r"\n- Page: \S+\n\n## Replaces\n\nThis recipe replaces the `valkey` recipe of kadet-hub/examples\..*\n\n"
                             r"\| kadet-hub/examples \| This recipe \|\n\|---\|---\|\n\| StatefulSet `valkey` \| Deployment `valkey` \|\n\n## Required parameters\n")

    def test_compose_recipe(self):  # CAT-37e
        page = self.page("recipes", "miniflux")
        self.assertIn("<title>Miniflux on Kubernetes, migrated from Docker Compose by Kapitan</title>", page)  # no room for the suffix
        self.assertIn(f'<li>Source: Docker Compose file <a href="{COMPOSE_SOURCE}"><code>miniflux/v2@{"2" * 40}</code></a> '
                      f"(<code>contrib/docker-compose/basic.yml</code>), <code>sha256:{'f' * 64}</code></li>", page)
        self.assertIn("<li><a href=\"../../glossary/#proof-level\">Proof level</a>: <code>deploys</code>, deployed on kind and smoke tested by the kadet-hub/recipes CI</li>", page)
        self.assertNotIn("Source chart", page)
        self.assertNotIn("compared with", page)
        self.assertIn("<li><code>recipes.miniflux.db</code> (<code>db.yml</code>): <code>miniflux-db</code></li>", page)
        self.assertEqual([h for h in re.findall(r"<h2>([^<]+)</h2>", page) if h != "Used in stacks"],  # CAT-48 follows the real posts' dates; Stacks tests it
                         ["What it deploys", "Required parameters", "Include", "Fetching it", "Settings", "Mapping", "Proof"])
        self.assertIn("<h2>Required parameters</h2>\n<p>The password must be set as a ref. Without it the compile stops with\n"
                      "<code>Interpolation key 'applications.miniflux.admin.password' not found</code>.</p>", page)
        self.assertIn("        password: &lt;ref&gt;</code></pre>", page)
        self.assertIn("<td>service <code>db</code></td>", page)
        self.assertIn("        subdir: miniflux\n", _unescape(re.search(r'<pre id="fetch"><code>(.*?)</code></pre>', page, re.DOTALL).group(1)))
        md = self.markdown("recipes", "miniflux")
        self.assertIn(f"\n- Source: Docker Compose file miniflux/v2@{'2' * 40} (contrib/docker-compose/basic.yml), sha256:{'f' * 64}: {COMPOSE_SOURCE}\n"
                      "- Proof level: deploys, deployed on kind and smoke tested by the kadet-hub/recipes CI\n- Generators: kubernetes 1.7.0", md)
        self.assertIn("\n## Mapping\n\n| Compose | Recipe |\n", md)
        self.assertIn("\n## Required parameters\n\nThe password must be set as a ref.", md)
        self.assertNotIn("compared with", md)

    def test_designed_recipe(self):  # CAT-37f
        page = self.page("recipes", "mysql")
        self.assertIn("<title>MySQL on Kubernetes from Oracle&#39;s Community Server image</title>", page)  # no room for the suffix
        self.assertIn(f"<li>Source: container image <code>{DESIGN_SOURCE}</code>, recipe designed in kadet-hub</li>", page)
        self.assertIn("<li><a href=\"../../glossary/#proof-level\">Proof level</a>: <code>deploys</code>, deployed on kind and smoke tested by the kadet-hub/recipes CI</li>", page)
        self.assertNotIn("Source chart", page)
        self.assertNotIn("compared with", page)
        self.assertIn("<li><code>recipes.mysql.mysql</code> (<code>mysql.yml</code>): <code>mysql</code></li>", page)
        self.assertEqual(re.findall(r"<h2>([^<]+)</h2>", page),
                         ["Replaces", "What it deploys", "Required parameters", "Include", "Fetching it", "Settings", "Proof"])
        self.assertIn("        subdir: mysql\n", _unescape(re.search(r'<pre id="fetch"><code>(.*?)</code></pre>', page, re.DOTALL).group(1)))
        md = self.markdown("recipes", "mysql")
        self.assertIn(f"\n- Source: container image {DESIGN_SOURCE}, recipe designed in kadet-hub\n"
                      "- Proof level: deploys, deployed on kind and smoke tested by the kadet-hub/recipes CI\n- Generators: kubernetes 1.7.0", md)
        self.assertNotIn("compared with", md)
        self.assertIn(f"<li>Source: container image <code>docker.io/mongodb/mongodb-community-server:9.0.4-ubi9-slim@sha256:{'e' * 64}</code>,"
                      " recipe designed in kadet-hub</li>", self.page("recipes", "mongodb"))
        powerdns = self.page("recipes", "powerdns")
        self.assertIn(f"<li>Source: container image <code>{POWERDNS_SOURCE}</code>, recipe designed in kadet-hub</li>", powerdns)
        self.assertIn("PowerDNS part of the <code>external-dns-powerdns</code> recipe of kadet-hub/examples", powerdns)
        self.assertNotIn("compared with", powerdns)
        kafka = self.page("recipes", "kafka")
        self.assertIn(f"<li>Source: container image <code>{KAFKA_SOURCE}</code>, recipe designed in kadet-hub</li>", kafka)
        self.assertIn("<h2>Replaces</h2>\n<p>This recipe replaces the <code>kafka</code> recipe of kadet-hub/examples.", kafka)
        self.assertNotIn("compared with", kafka)
        self.assertNotIn("without Bitnami", kafka)
        rabbitmq = self.page("recipes", "rabbitmq")
        self.assertIn(f"<li>Source: container image <code>{RABBITMQ_SOURCE}</code>, recipe designed in kadet-hub</li>", rabbitmq)
        self.assertIn("<h2>Replaces</h2>\n<p>This recipe replaces the <code>rabbitmq</code> recipe of kadet-hub/examples.", rabbitmq)
        self.assertNotIn("without Bitnami", rabbitmq)
        keycloak = self.page("recipes", "keycloak")
        self.assertIn(f"<li>Source: container image <code>{KEYCLOAK_SOURCE}</code>, recipe designed in kadet-hub</li>", keycloak)
        self.assertIn("<h2>Replaces</h2>\n<p>This recipe replaces the <code>keycloak</code> recipe of kadet-hub/examples.", keycloak)
        self.assertNotIn("without Bitnami", keycloak)

    def test_recipe_file_missing_fails_the_build(self):  # CAT-37a, CAT-37c, CAT-37e
        for missing, error in (("webhook.yml", "classes/recipes/cert-manager/webhook.yml missing"),
                               ("crds.yml", "classes/recipes/cert-manager/crds.yml missing"),
                               ("Level", "README.md has no Level:"), ("Source", "README.md has no Source:"),
                               ("Required", 'README.md has no section "Required parameters"')):
            with self.subTest(missing), tempfile.TemporaryDirectory() as tmp:
                recipes = os.path.join(tmp, "recipes")
                recipe_classes(os.path.join(recipes, "inventory", "classes"))
                path = os.path.join(recipes, "inventory", "classes", "recipes", "cert-manager", missing)
                if missing in ("Level", "Source", "Required"):
                    path = os.path.join(os.path.dirname(path), "README.md")
                    with open(path, "w", encoding="utf-8") as f:  # Source: a compose file not pinned to a commit
                        f.write(CHART_RECIPE_FILES["README.md"].replace("Level: `deploys`", "Level: deploys") if missing == "Level" else
                                CHART_RECIPE_FILES["README.md"].replace("## Required parameters", "## Required") if missing == "Required" else
                                CHART_RECIPE_FILES["README.md"].replace("oci://quay.io/jetstack/charts/cert-manager:v1.21.2",
                                                                        "https://github.com/miniflux/v2/blob/main/basic.yml"))
                else:
                    os.remove(path)
                with self.assertRaises(subprocess.CalledProcessError) as failed:
                    build({"serial": 1, "generators": {}}, tmp, recipes=recipes, capture=True)
                self.assertIn(error, failed.exception.stderr)

    def test_build_fetches_recipes_at_main(self):  # CAT-37a: the online build with curl, git and gh faked
        shims = {"curl": 'while (($#)); do case $1 in -o) out=$2; shift;; https://*) url=$1;; esac; shift; done\n'
                         'echo "$url" >>"$CURL_LOG"\n'
                         'case $url in\n'
                         '  https://raw.githubusercontent.com/*/recipes/*/*) cp "$RECIPES/inventory/classes/recipes/${url#https://raw.githubusercontent.com/*/recipes/*/}" "$out";;\n'
                         '  *) exit 22;;\n'
                         'esac\n',
                 "git": 'printf "%s\\trefs/heads/main\\n" "$RECIPES_SHA"\n',
                 "gh": "exit 1\n"}
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, "bin"))
            for name, script in shims.items():
                with open(os.path.join(tmp, "bin", name), "w", encoding="utf-8") as f:
                    f.write("#!/usr/bin/env bash\n" + script)
                os.chmod(os.path.join(tmp, "bin", name), 0o755)
            recipes, log = os.path.join(tmp, "recipes"), os.path.join(tmp, "curl.log")
            recipe_classes(os.path.join(recipes, "inventory", "classes"))
            with open(os.path.join(tmp, "index.json"), "w", encoding="utf-8") as f:
                json.dump({"serial": 1, "generators": {}}, f)
            env = dict(os.environ, OWNER=OWNER, PATH=os.path.join(tmp, "bin") + os.pathsep + os.environ["PATH"], CURL_LOG=log, RECIPES=recipes, RECIPES_SHA=CHART_RECIPE_SHA)
            env.pop("CATALOG_OFFLINE", None)
            subprocess.run([os.path.join(HERE, "build"), os.path.join(tmp, "index.json"), os.path.join(tmp, "out")], env=env, check=True, capture_output=True)
            with open(log, encoding="utf-8") as f:
                urls = f.read()
            self.assertIn(f"/{OWNER}/recipes/{CHART_RECIPE_SHA}/keycloak/README.md\n", urls)
            self.assertNotIn("/examples/", urls)

    def test_blog(self):  # CAT-36
        slug = "kapitan-generators-as-supply-chain-artifacts"
        blog = self.page("blog")
        self.assertIn(f'<a href="../blog/{slug}/">Kapitan generators as supply-chain artifacts</a> <time datetime="2026-10-17">', blog)
        self.assertIn('<link rel="alternate" type="application/atom+xml" title="kadet-hub blog" href="../blog/index.xml">', blog)
        self.assertIn("<title>Kapitan on Kubernetes: a first platform from four generators</title>", self.page("guides", "first-platform"))  # CAT-11a
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
        ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', post, re.DOTALL)]
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

    def test_blog_tools(self):  # CAT-51, CAT-52
        tools = {}
        for path in sorted(glob.glob(os.path.join(CONTENT, "blog", "*.md"))):
            name = os.path.basename(path)[:-3]
            m = re.search(r"^tools: \[(.*)\]$", front_matter(path), re.MULTILINE)
            self.assertIsNotNone(m, f"{name}.md has no tools")
            tools[name] = m.group(1).split(", ")
            self.assertIn(len(tools[name]), (1, 2, 3), name)
            for tool in tools[name]:
                self.assertRegex(tool, r"^[A-Za-z0-9]+$", name)
                self.assertNotEqual(tool.lower(), "kapitan", name)
        atom = "{http://www.w3.org/2005/Atom}"
        published = 0
        for entry in ET.parse(os.path.join(self.out, "blog", "index.xml")).getroot().iter(f"{atom}entry"):
            name = entry.findtext(f"{atom}id").rstrip("/").rsplit("/", 1)[1]
            self.assertEqual([c.get("term") for c in entry.findall(f"{atom}category")], tools.get(name, []), name)  # a release post has none
            published += name in tools
        self.assertGreater(published, 0)

    def og_card(self, html, out):
        """CAT-58: checks the card a post page names and returns its URL."""
        meta = dict(re.findall(r'<meta (?:property|name)="((?:og|twitter):image[^"]*)" content="([^"]*)">', html))
        ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)]
        post = next(b for b in ld if b["@type"] == "BlogPosting")
        url = meta["og:image"]
        self.assertRegex(url, r"^https://kadet-hub\.org/og/[\w-]+\.png$")
        self.assertEqual([meta["og:image:width"], meta["og:image:height"], meta["twitter:image"], post["image"]], ["1200", "630", url, url])
        self.assertIn(post["headline"], _unescape(meta["og:image:alt"]))
        path = os.path.join(out, url.removeprefix("https://kadet-hub.org/"))
        self.assertLess(os.path.getsize(path), 300_000, url)
        width, height, bpp, rows = png_rows(path)
        self.assertEqual((width, height, rows[0][:3]), (1200, 630, bytes.fromhex("0d1117")), url)
        blank = rows[0][:bpp]
        for y, row in enumerate(rows):  # the outer 80 px, and below the third title line, above the tags
            edge = row if y < 80 or y >= 550 or 430 <= y < 510 else row[:80 * bpp] + row[1120 * bpp:]
            self.assertTrue(edge == blank * (len(edge) // bpp), f"{url}: text in row {y}")
        return url

    def test_post_cards(self):  # CAT-58
        urls = []
        for path in sorted(glob.glob(os.path.join(self.out, "blog", "*", "index.html"))):
            with open(path, encoding="utf-8") as f:
                html = f.read()
            if '<meta property="og:type" content="article">' in html:  # not the alias of a moved post
                urls.append(self.og_card(html, self.out))
        self.assertGreater(len(urls), 1)
        self.assertEqual(len(set(urls)), len(urls))  # each post its own
        for html in (*self.pages(), self.page("blog"), self.page("guides", "writing-a-kapitan-generator")):
            self.assertIn('<meta property="og:image" content="https://kadet-hub.org/og.png">', html)
            self.assertNotIn("twitter:image", html)
        with open(os.path.join(HERE, "site", "layouts", "_partials", "og-card.html"), encoding="utf-8") as f:
            for colour in re.findall(r'"color" "(#[0-9a-f]{6})"', f.read()):
                self.assertGreaterEqual(contrast(colour, "#0d1117"), 4.5, colour)
        long = ("title: A very long post title that keeps going well past the three lines the social card has room for, so it ends in an ellipsis\n"
                "date: 2000-01-02\ndescription: A post whose title and tools are longer than the card has room for, for the test of CAT-58.\n"
                "tools: [CloudNativePGOperatorForPostgreSQLClusters, ExternalSecretsOperatorWithVaultBackend, KubePrometheusStack]")
        with tempfile.TemporaryDirectory() as tmp:
            out, built = stack_build(tmp, {**dict.fromkeys(stack_posts()), "long": long})
            self.assertEqual(built.returncode, 0, built.stderr)
            with open(os.path.join(out, "blog", "long", "index.html"), encoding="utf-8") as f:
                self.og_card(f.read(), out)

    def test_guides_and_recipes_dated(self):  # CAT-11g
        with open(os.path.join(self.out, "sitemap.xml"), encoding="utf-8") as f:
            sitemap = f.read()
        for section in ("guides", "recipes"):
            names = sorted(f[:-3] for f in os.listdir(os.path.join(HERE, "site", "content", section)))
            for name in names:
                with open(os.path.join(HERE, "site", "content", section, name + ".md"), encoding="utf-8") as f:
                    day = re.search(r"^lastmod: (\d{4}-\d{2}-\d{2})$", f.read(), re.MULTILINE)
                self.assertTrue(day, name)
                ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', self.page(section, name), re.DOTALL)]
                self.assertIn(("TechArticle", day.group(1)), [(b["@type"], b.get("dateModified")) for b in ld], name)
                self.assertRegex(sitemap, rf"/{section}/{name}/</loc>\s*<lastmod>{day.group(1)}")
        titles = re.findall(r'<li><a href="[^"]*">([^<]*)</a>', self.page("guides"))
        self.assertEqual(titles, sorted(titles, key=str.lower))  # lastmod does not reorder the list

    def test_titles(self):  # CAT-11j to CAT-11m
        pages, descriptions, queries, found = titles(), titles("description"), title_queries(), []
        by_title = {title: name for name, title in pages.items()}
        contrast = re.compile(r"\bwithout\b.*\bwith\b|\bnot with\b|,\s*not\b|\binstead of\b|\brather than\b|[\u2013\u2014]", re.IGNORECASE)
        found += [f"CAT-11j: {name}: {title}" for name, title in pages.items() if contrast.search(title)]
        lists = [name for name, title in pages.items() if re.search(r":\s[^:]*,[^:]*\b(and|or)\b", title)]
        if len(lists) > 3:
            found.append(f"CAT-11l: {len(lists)} titles end in a colon and a list: {', '.join(lists)}")
        lead = {}
        for title, qs in queries.items():
            if title not in by_title:
                found.append(f"CAT-11m: CAT-11f names {title!r}, which no page has")
            elif by_title[title].startswith("blog/"):  # a post names a query in its title or description
                if not any(joined(q) in joined(title) or joined(q) in joined(descriptions.get(by_title[title], "")) for q in qs):
                    found.append(f"CAT-11m: {by_title[title]}: neither title nor description contains one of {qs}")
                lead[title] = max(leads(title, q) for q in qs)
            elif not any(leads(title, q) for q in qs) and not compares(title):
                found.append(f"CAT-11m: {by_title[title]}: {title!r} leads with none of {qs}")
            else:
                lead[title] = max(leads(title, q) for q in qs)
        phrases = {}
        for name, title in pages.items():
            words = title_words(title)
            n = max(lead.get(title, 0), compares(title))
            if not n and name.startswith("recipes/") and "kubernetes" in words:  # CAT-37: the software on Kubernetes
                n = words.index("kubernetes") + 1
            words = ["_"] * bool(n) + words[n:]
            for phrase in set(zip(words, words[1:], words[2:])):
                phrases.setdefault(phrase, []).append(name)
        found += [f"CAT-11k: {' '.join(p)!r} in {len(names)} titles: {', '.join(names)}" for p, names in sorted(phrases.items()) if len(names) > 2]
        self.assertFalse(found, "\n" + "\n".join(found))

    def test_moved_posts(self):  # CAT-36e to CAT-36g
        moved = {}
        for path in sorted(glob.glob(os.path.join(CONTENT, "guides", "*.md"))):
            front, name = front_matter(path), os.path.basename(path)[:-3]
            self.assertNotRegex(front, r"(?m)^date:", name)  # CAT-36e: lastmod only
            self.assertRegex(front, r"(?m)^layout: prose$", name)
            aliases = re.search(r"^aliases: \[(.*)\]$", front, re.MULTILINE)
            for alias in aliases.group(1).split(", ") if aliases else ():
                old = re.fullmatch(r"/blog/([a-z0-9-]+)/", alias).group(1)
                moved[old] = name
        self.assertLessEqual(MOVED_POSTS, set(moved))
        with open(os.path.join(self.out, "sitemap.xml"), encoding="utf-8") as f:
            sitemap = f.read()
        with open(os.path.join(self.out, "blog", "index.xml"), encoding="utf-8") as f:
            feed = f.read()
        with open(os.path.join(self.out, "llms.txt"), encoding="utf-8") as f:
            llms = f.read()
        for old, name in moved.items():
            url = f"https://kadet-hub.org/guides/{name}/"
            self.assertFalse(os.path.exists(os.path.join(CONTENT, "blog", old + ".md")), old)
            page = self.page("blog", old)
            self.assertIn(f'<meta http-equiv="refresh" content="0; url={url}">', page)  # CAT-36f: instant, so permanent for Google
            self.assertIn(f'<link rel="canonical" href="{url}">', page)
            self.assertIn(f"<loc>{url}</loc>", sitemap)
            self.assertNotIn(f"/blog/{old}/", sitemap)
            self.assertNotIn(f"/blog/{old}/", feed)
            self.assertNotIn(f"/blog/{old}/", llms)
            variant = self.markdown("guides", name)
            self.assertTrue(variant.startswith("# "), name)  # CAT-28: the guide's Markdown variant
            heading = variant.split("\n", 1)[0]  # CAT-36f: the old variant links the guide and its variant, without its text
            self.assertEqual(self.markdown("blog", old), f"{heading}\n\nThis page moved to <{url}>. Its Markdown variant is at <{url}index.md>.\n")
        sources = glob.glob(os.path.join(CONTENT, "**", "*.md"), recursive=True) + glob.glob(os.path.join(HERE, "site", "layouts", "**", "*.*"), recursive=True)
        for path in sources:  # CAT-36g: no internal link to an alias
            with open(path, encoding="utf-8") as f:
                body = f.read()
            if path.startswith(CONTENT):
                body = body.split("\n---\n", 1)[1]
            for old in moved:
                self.assertNotRegex(body, rf"blog/{old}/", os.path.relpath(path, HERE))

    def test_generator_mentions_linked(self):  # CAT-11h
        names = [f[:-5] for f in os.listdir(os.path.join(HERE, "..", "generators"))]
        content = os.path.join(HERE, "site", "content")
        for section in ("guides", "recipes", "blog"):
            for f in os.listdir(os.path.join(content, section)):
                with open(os.path.join(content, section, f), encoding="utf-8") as fh:
                    body = fh.read().split("---", 2)[2]
                for name in names:
                    mentioned = re.search(rf"(?<![\w/-])`?{re.escape(name)}`? generators?\b", body, re.IGNORECASE)
                    if mentioned:
                        self.assertTrue(f"](/generators/{name}/" in body, f"{section}/{f}: {name} generator not linked")

    def test_indexnow_key(self):  # CAT-11i
        with open(os.path.join(self.out, "9402a7122cd662ad840c013f9c6f7906.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "9402a7122cd662ad840c013f9c6f7906")

    def test_share_links(self):  # CAT-36c, CAT-36d
        post = self.page("blog", "kapitan-generators-as-supply-chain-artifacts")
        url = "https://kadet-hub.org/blog/kapitan-generators-as-supply-chain-artifacts/"
        title = "Kapitan generators as supply-chain artifacts"
        description = _unescape(re.search(r'<meta name="description" content="([^"]+)">', post)[1])
        q = urllib.parse.quote_plus  # Go's url.QueryEscape, behind Hugo's urlquery
        prefill = f'---\ntitle: "{title}"\npublished: false\ncanonical_url: {url}\n---\n\n{description}\n\nRead the full post: {url}\n'
        links = re.findall(r'<a class="icon-button" href="([^"]+)" target="_blank" rel="nofollow noopener noreferrer" aria-label="([^"]+)">', post)
        self.assertEqual([(_unescape(h), label) for h, label in links], [
            (f"https://www.linkedin.com/sharing/share-offsite/?url={q(url)}", "Share on LinkedIn"),
            (f"https://bsky.app/intent/compose?text={q(title + ' ' + url)}", "Share on Bluesky"),
            (f"https://x.com/intent/tweet?text={q(title)}&url={q(url)}", "Share on X"),
            (f"https://news.ycombinator.com/submitlink?u={q(url)}&t={q(title)}", "Share on Hacker News"),
            (f"https://www.reddit.com/submit?url={q(url)}&title={q(title)}", "Share on Reddit"),
            (f"https://dev.to/new?prefill={q(prefill)}", "Cross-post to dev.to"),
        ])
        self.assertIn(f'<div class="share" data-title="{title}" data-url="{url}">', post)
        self.assertRegex(post, r'<button type="button" class="share-native icon-button" aria-label="[^"]+" hidden>')
        form = re.search(r'<form class="share-mastodon" hidden>.*?</form>', post, re.DOTALL)[0]
        self.assertIn('<label for="mastodon-server">', form)
        pattern = _unescape(re.search(r'<input id="mastodon-server" name="server" [^>]*pattern="([^"]+)"', form)[1])
        for host, ok in [("mastodon.social", True), (" hachyderm.io ", True), ("https://mastodon.social", False),
                         ("mastodon.social/share", False), ("@me@mastodon.social", False), ("localhost", False)]:
            self.assertEqual(bool(re.fullmatch(pattern, host)), ok, host)
        with open(os.path.join(self.out, "site.js"), encoding="utf-8") as f:
            script = f.read()
        self.assertIn("navigator.share", script)
        self.assertIn('localStorage.setItem("mastodon"', script)
        self.assertIn("/share?text=${encodeURIComponent(", script)
        self.assertIn("under the key <code>mastodon</code>", self.page("privacy"))  # LEG-1
        for page in (self.page(), self.page("blog"), self.page("guides", "writing-a-kapitan-generator"),
                     self.page("recipes", "kafka"), self.page("generators", "demo")):
            self.assertNotIn('class="share"', page)
            self.assertNotIn("share-offsite", page)

    def test_fediverse_verification(self):  # CAT-53
        me = '<link rel="me" href="https://hachyderm.io/@kadethub">'
        creator = '<meta name="fediverse:creator" content="@kadethub@hachyderm.io">'
        heads = {}
        for path in glob.glob(os.path.join(self.out, "**", "*.html"), recursive=True):
            with open(path, encoding="utf-8") as f:
                head = f.read().split("</head>")[0]
            if 'http-equiv="refresh"' not in head:  # a Hugo alias page is a redirect (CAT-36f)
                heads[os.path.relpath(path, self.out)] = head
        self.assertGreater(len(heads), 20)
        for path, head in heads.items():
            self.assertIn(me, head, path)
        self.assertIn(creator, heads[os.path.join("blog", "kapitan-generators-as-supply-chain-artifacts", "index.html")])
        for path in ("index.html", os.path.join("generators", "demo", "index.html"), os.path.join("blog", "index.html")):
            self.assertNotIn(creator, heads[path], path)

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
        self.assertIn(">REG-1 to REG-6, REG-8, REG-10</a>", table)
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
        with tempfile.TemporaryDirectory() as tmp, open(os.path.join(build(gitlab, tmp), "generators", "g", "index.html"), encoding="utf-8") as f:
            page = f.read()
        link = re.search(r'<a class="button" href="([^"]+)">Request a feature</a>', page).group(1)
        self.assertTrue(link.startswith("https://gitlab.com/group/proj/-/issues/new?"))
        self.assertIn("issue[title]", urllib.parse.unquote(_unescape(link)))
        own = dict(INDEX, generators={"g": {"1.0.0": dict(record("e"), source=dict(record("e")["source"], repo=f"https://github.com/{OWNER}/generators.git"))}})
        with tempfile.TemporaryDirectory() as tmp, open(os.path.join(build(own, tmp), "generators", "g", "index.html"), encoding="utf-8") as f:
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
                json.dump({"generators": [{"name": "demo", "latest": {"digest": digest}, "readme": "# Kept", "changelog": {"1.10.0": "- kept", "1.2.0": 1},
                                           "sources": {"gateway.networking.k8s.io": "Gateway API", "x.io": 1}},
                                          {"name": "big", "latest": {"digest": "sha256:x"}, "readme": "x" * (README_MAX + 1)}]}, f)
            previous = load_previous(prev)
        self.assertEqual(previous, {("demo", digest): {"readme": "# Kept", "changelog": {"1.10.0": "- kept"},
                                                       "sources": {"gateway.networking.k8s.io": "Gateway API", "x.io": None}}})  # oversized README dropped
        result = view(INDEX, OWNER, lambda _: None, previous=previous)
        g = result["generators"][0]
        self.assertEqual((g["readme"], g["changelog"]), ("# Kept", {"1.10.0": "- kept"}))  # CAT-36b
        self.assertEqual(result["software"], {"gateway.networking.k8s.io": "Gateway API"})  # CAT-29c
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
        code = _unescape(re.search(r'<pre id="badge-markdown"><code>(.*?)</code></pre>', section, re.DOTALL).group(1))
        self.assertEqual(code, "[![kadet-hub](https://img.shields.io/endpoint?url=https://kadet-hub.org/generators/demo/badge.json)]"
                               "(https://kadet-hub.org/generators/demo/)")
        self.assertIn('data-copy="badge-markdown"', section)
        self.assertNotIn("badge-snippet", self.page("generators", "old"))  # no listed version, no snippet
        for page in (html, self.page("generators", "old")):
            self.assertNotRegex(page, r"<img\b[^>]*shields")
            csp = re.search(r'Content-Security-Policy" content="([^"]*)"', page).group(1)
            self.assertEqual(csp, "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' https://stats.kadet-hub.org; "
                                  "connect-src 'self' https://stats.kadet-hub.org; base-uri 'none'; form-action 'none'")  # CAT-3a
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
        # CAT-41: the recipe requests of kadet-hub/recipes in their own section, after the generators.
        self.assertLess(page.index('<h2 id="registry">Generators</h2>'), page.index('<h2 id="recipes">Recipes</h2>'))
        recipes = re.findall(rf'<li><a href="https://github.com/{OWNER}/recipes/issues/(\d+)">([^<]*)</a>', page)
        self.assertEqual(recipes, [("5", "Paperless-ngx"), ("3", "Immich &lt;b&gt;x&lt;/b&gt;")])
        self.assertLess(page.index('<h2 id="recipes">'), page.index(f"{OWNER}/recipes/issues/5"))
        self.assertRegex(page, rf'<a href="https://github.com/{OWNER}/recipes/issues/new\?template=recipe-request.yml"[^>]*>recipe request form</a>')
        self.assertIn('<a class="button" href="https://github.com/kadet-hub/registry/issues/new?template=generator-request.yml">Request a generator</a>'
                      '<a class="button" href="./wanted/">Wanted generators</a>', self.page())

    def test_wanted_page_without_requests(self):  # CAT-31
        texts = []
        for wanted, wanted_recipes in (([], []), (None, None), ([], None)):
            with tempfile.TemporaryDirectory() as tmp:
                paths = []
                for name, data in (("wanted.json", wanted), ("wanted-recipes.json", wanted_recipes)):
                    paths.append(None if data is None else os.path.join(tmp, name))
                    if data is not None:
                        with open(paths[-1], "w", encoding="utf-8") as f:
                            json.dump(data, f)
                with open(os.path.join(build(INDEX, tmp, wanted=paths[0], wanted_recipes=paths[1]), "wanted", "index.html"), encoding="utf-8") as f:
                    texts.append(f.read())
        empty, unread, mixed = texts
        self.assertIn("No generator request is open.", empty)
        self.assertIn(f'href="https://github.com/{OWNER}/registry/issues/new?template=generator-request.yml"', empty)
        self.assertIn("No recipe request is open.", empty)  # CAT-41
        self.assertIn(f'href="https://github.com/{OWNER}/recipes/issues/new?template=recipe-request.yml">Request a recipe</a>', empty)
        self.assertIn("The open generator requests could not be read when this page was built.", unread)
        self.assertIn("The open recipe requests could not be read when this page was built.", unread)
        self.assertIn(f'href="https://github.com/{OWNER}/recipes/issues?q=is%3Aissue+is%3Aopen+label%3Arecipe-request"', unread)
        self.assertIn("No generator request is open.", mixed)  # one list unread leaves the other
        self.assertIn("The open recipe requests could not be read", mixed)
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
        result = subprocess.run([sys.executable, "-I", SEO_CHECK, self.out], capture_output=True, text=True, check=False)
        self.assertEqual((result.returncode, result.stdout), (0, ""))  # CAT-11d: every page
        self.assertIn('<link rel="canonical" href="https://kadet-hub.org/">', self.page())
        ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', self.page("generators", "demo"), re.DOTALL).group(1)
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
            result = subprocess.run([sys.executable, "-I", SEO_CHECK, out], capture_output=True, text=True, check=False)
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
        for slug, start in (("ingress-nginx-to-gateway-api", "ingress-nginx Gateway API migration"), ("generator-helm-or-jinja2", "Kapitan inputs"),
                            ("bitnami-chart-alternatives", "Bitnami alternatives"),
                            ("helm-alternatives-for-kubernetes", "Helm alternatives for Kubernetes"),
                            ("talos-machine-config", "Talos machine config"),
                            ("helm-vs-terraform", "Helm vs Terraform for Kubernetes"),
                            ("argocd-vs-flux", "Argo CD vs Flux"),
                            ("patch-helm-chart", "Patch a Helm chart")):
            self.assertIn(f"<h1>{start}", self.page("guides", slug))
        ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL).group(1))
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
            for before, after in itertools.pairwise(levels):
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
                self.assertIn("connect-src 'self'; base-uri", html)  # CAT-3a, no counter origin
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
            self.assertIn("connect-src 'self' https://stats.example.org;", csp)
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
            result = subprocess.run([sys.executable, "-I", SEO_CHECK, out], capture_output=True, text=True, check=False)
            pages = sorted(os.path.relpath(os.path.join(d, n), out) for d, _, names in os.walk(os.path.join(out, "kinds")) for n in names)
            def read(*parts):
                with open(os.path.join(out, "kinds", *parts, "index.html"), encoding="utf-8") as f:
                    return f.read()
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
        self.assertEqual((levels[0], max(b - a for a, b in itertools.pairwise(levels))), (1, 1))
        self.assertIn('<li><a href="../kinds/gateway.networking.k8s.io/httproute/"><code>HTTPRoute</code></a>: rendered by '
                      '<a href="../generators/a/">a</a>, <a href="../generators/b/">b</a>; schema shipped by <a href="../generators/c/">c</a></li>', kinds)
        self.assertEqual(titles, ["ApplicationInsightsWorkbookTemplate (insights.azure.upbound.io)",
                                  "AVeryVeryVeryLongKindNameThatGoesOn · kadet-hub"])  # the group goes last
        self.assertTrue(desc.endswith("…") and len(_unescape(desc)) <= 160, desc)
        for url in ("kinds/", "kinds/gateway.networking.k8s.io/httproute/"):
            self.assertIn(f"<loc>https://kadet-hub.org/{url}</loc>", sitemap)

    def test_kinds_without_a_group_split_by_version(self):  # CAT-29, CAT-29b, CAT-29c, CAT-34e
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
        layers = {"k8s-a": {"core": "Kubernetes", "apps": "Kubernetes", "gateway.networking.k8s.io": "Gateway API"}, "k8s-b": {"core": "Kubernetes"},
                  "talos-a": {"core": "Kubernetes", "core/v1alpha1": "Talos"}, "talos-b": {"core/v1alpha1": "Talos"}, "kyv": {"kyverno.io": "Kyverno"},
                  "multi": {"kyverno.io": "Kyverno", "cert-manager.io": "cert-manager"}}
        with tempfile.TemporaryDirectory() as tmp:
            out = build(index, tmp, artifacts=sources_layers(tmp, layers))
            result = subprocess.run([sys.executable, "-I", SEO_CHECK, out], capture_output=True, text=True, check=False)
            def read(*parts):
                with open(os.path.join(out, "kinds", *parts, "index.html"), encoding="utf-8") as f:
                    return f.read()
            kinds, core, talos = read(), read("core", "configmap"), read("v1alpha1", "configmap")
            with open(os.path.join(out, "sitemap.xml"), encoding="utf-8") as f:
                sitemap = f.read()
            with open(os.path.join(HERE, "..", "docs", "consumers.md"), encoding="utf-8") as f:  # CAT-34e
                command = re.search(r"```sh\ncurl -fsSL https://kadet-hub\.org/catalog\.json \| (jq -r --arg kind .*?)\n```", f.read(), re.DOTALL).group(1)
            lookup = subprocess.run(shlex.split(command) + [os.path.join(out, "catalog.json")], capture_output=True, text=True, check=True)
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertEqual(lookup.stdout, "core k8s-a k8s-b\nv1alpha1 talos-a talos-b\n")
        cards = lambda page: re.findall(r'data-name="([^"]+)"', page.split('<ul class="cards')[1])
        self.assertEqual((cards(core), cards(talos)), (["k8s-a", "k8s-b"], ["talos-a", "talos-b"]))
        self.assertIn("<dd><code>v1</code>: k8s-a, k8s-b</dd>", core)
        self.assertIn("<dd><code>v1alpha1</code>: talos-a, talos-b</dd>", talos)
        self.assertIn("<dt>API group</dt><dd>none: the apiVersion has no group</dd>", talos)
        headings = re.findall(r'<h([23]) id="([^"]+)">(.*?)</h[23]>', kinds)
        self.assertEqual(headings, [
            ("2", "builtin", "Kubernetes built-in APIs"), ("3", "apps", "apps"), ("3", "core", "core (v1)"),
            ("2", "custom", "Custom resources and other APIs"), ("3", "cert-manager.io", "cert-manager.io · cert-manager"),
            ("3", "gateway.networking.k8s.io", "gateway.networking.k8s.io · Gateway API"), ("3", "kyverno.io", "kyverno.io · Kyverno"),
            ("3", "v1alpha1", "v1alpha1 · Talos")])
        for url in ("kinds/core/configmap/", "kinds/v1alpha1/configmap/"):
            self.assertIn(f'href="../{url}"', kinds)
            self.assertIn(f"<loc>https://kadet-hub.org/{url}</loc>", sitemap)

    def test_custom_sections_group_by_domain(self):  # CAT-29d, CAT-29b, CAT-29c
        def gen(d, kinds, *software):
            return {"1.0.0": dict(record(d, tags=()), kinds=[dict(zip(("group", "version", "kind"), k)) for k in kinds],
                                  compatibility=[{"software": s, "version": "1", "source": "tbd"} for s in software])}
        pool = ("pool.kubevirt.io", "v1alpha1", "VirtualMachinePool")
        index = {"serial": 1, "generators": {
            "k8s": gen("a", [("apps", "v1", "Deployment"), ("networking.k8s.io", "v1", "Ingress"), ("autoscaling.k8s.io", "v1", "VerticalPodAutoscaler"),
                             ("gateway.networking.k8s.io", "v1", "HTTPRoute"), ("snapshot.storage.k8s.io", "v1", "VolumeSnapshot")]),
            "kv-a": gen("b", [("kubevirt.io", "v1", "VirtualMachine"), pool, ("cdi.kubevirt.io", "v1beta1", "DataVolume"),
                              ("snapshot.storage.k8s.io", "v1", "VolumeSnapshotClass")], "KubeVirt", "CDI", "Kubernetes CSI external-snapshotter"),
            "kv-b": gen("c", [pool]),
            "iron": gen("d", [("compute.ironcore.dev", "v1alpha1", "Machine"), ("storage.ironcore.dev", "v1alpha1", "Volume")], "IronCore"),
            "cm": gen("e", [("cert-manager.io", "v1", "Certificate")], "cert-manager"),
            "tm": gen("f", [("trust.cert-manager.io", "v1alpha1", "Bundle")], "trust-manager"),
            "multus": gen("g", [("k8s.cni.cncf.io", "v1", "NetworkAttachmentDefinition")], "Multus CNI"),
            "calico": gen("h", [("projectcalico.org", "v3", "IPPool")], "Calico"),
            "talos": gen("i", [("", "v1alpha1", "MachineConfig")], "Talos")}}
        # kv-a ships no entry for pool.kubevirt.io and calico no sources.yaml: their groups name nothing.
        layers = {"k8s": {"apps": "Kubernetes", "gateway.networking.k8s.io": "Gateway API"},
                  "kv-a": {"kubevirt.io": "KubeVirt", "cdi.kubevirt.io": "CDI", "snapshot.storage.k8s.io": "Kubernetes CSI external-snapshotter"},
                  "iron": {"compute.ironcore.dev": "IronCore", "storage.ironcore.dev": "IronCore"}, "cm": {"cert-manager.io": "cert-manager"},
                  "tm": {"trust.cert-manager.io": "trust-manager"}, "multus": {"k8s.cni.cncf.io": "Multus CNI"}, "talos": {"core/v1alpha1": "Talos"}}
        with tempfile.TemporaryDirectory() as tmp:
            out = build(index, tmp, artifacts=sources_layers(tmp, layers))
            result = subprocess.run([sys.executable, "-I", SEO_CHECK, out], capture_output=True, text=True, check=False)
            with open(os.path.join(out, "kinds", "index.html"), encoding="utf-8") as f:
                kinds = f.read()
            with open(os.path.join(out, "catalog.json"), encoding="utf-8") as f:
                software = json.load(f)["software"]
            pool_page = os.path.isfile(os.path.join(out, "kinds", "pool.kubevirt.io", "virtualmachinepool", "index.html"))
        self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertEqual(software, {"cdi.kubevirt.io": "CDI", "cert-manager.io": "cert-manager", "compute.ironcore.dev": "IronCore",
                                    "gateway.networking.k8s.io": "Gateway API", "k8s.cni.cncf.io": "Multus CNI", "kubevirt.io": "KubeVirt",
                                    "snapshot.storage.k8s.io": "Kubernetes CSI external-snapshotter", "storage.ironcore.dev": "IronCore",
                                    "trust.cert-manager.io": "trust-manager", "v1alpha1": "Talos"})
        headings = re.findall(r'<h([234]) id="([^"]+)">(.*?)</h[234]>', kinds)
        self.assertEqual(headings, [
            ("2", "builtin", "Kubernetes built-in APIs"), ("3", "apps", "apps"), ("3", "networking.k8s.io", "networking.k8s.io"),
            ("2", "custom", "Custom resources and other APIs"),
            ("3", "domain-cert-manager.io", "cert-manager.io · cert-manager, trust-manager"),
            ("4", "cert-manager.io", "cert-manager.io"), ("4", "trust.cert-manager.io", "trust.cert-manager.io"),
            ("3", "k8s.cni.cncf.io", "k8s.cni.cncf.io · Multus CNI"),
            ("3", "domain-ironcore.dev", "ironcore.dev · IronCore"),
            ("4", "compute.ironcore.dev", "compute.ironcore.dev"), ("4", "storage.ironcore.dev", "storage.ironcore.dev"),
            ("3", "domain-k8s.io", "k8s.io · Gateway API, Kubernetes CSI external-snapshotter"), ("4", "autoscaling.k8s.io", "autoscaling.k8s.io"),
            ("4", "gateway.networking.k8s.io", "gateway.networking.k8s.io"), ("4", "snapshot.storage.k8s.io", "snapshot.storage.k8s.io"),
            ("3", "domain-kubevirt.io", "kubevirt.io · CDI, KubeVirt"), ("4", "cdi.kubevirt.io", "cdi.kubevirt.io"), ("4", "kubevirt.io", "kubevirt.io"),
            ("4", "pool.kubevirt.io", "pool.kubevirt.io"), ("3", "projectcalico.org", "projectcalico.org"), ("3", "v1alpha1", "v1alpha1 · Talos")])
        ids = [h[1] for h in headings]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(pool_page)
        self.assertIn('href="../kinds/pool.kubevirt.io/virtualmachinepool/"', kinds)

    def test_search_matches_kind_names(self):  # CAT-29a
        home = self.page()
        self.assertRegex(home, r'data-text="demo [^"]* configmap httproute[^"]*" data-tags="helm" data-name="demo"')
        self.assertRegex(home, r'data-text="plain [^"]* configmap httproute" data-tags="" data-name="plain"')

    def test_search_matches_built_for(self):  # CAT-29e
        home = self.page()
        self.assertRegex(home, r'data-text="demo [^"]* configmap httproute external secrets operator" data-tags="helm" data-name="demo"')
        self.assertRegex(home, r'data-text="plain [^"]* httproute" data-tags="" data-name="plain"')  # no compatibility record

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


class Playground(unittest.TestCase):  # PG-4, PG-7, PG-9, PG-13
    """With PLAYGROUND_BUILD, a directory build.py wrote (static/ and playground.json), the
    page also runs in Chrome (browser.mjs, PG-3, PG-7 to PG-11); without it, a stand-in."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.real = os.environ.get("PLAYGROUND_BUILD")
        pg = cls.real or os.path.join(cls.tmp.name, "playground")
        if not cls.real:
            os.makedirs(os.path.join(pg, "static", "pyodide"))
            with open(os.path.join(pg, "playground.json"), "w", encoding="utf-8") as f:
                json.dump({"pyodide": "314.0.7", "kapitan": "0.36.3", "download": 9_876_543, "size": 20_000_000,
                           "examples": [{"name": "basics", "title": "Inventory basics"}]}, f)
        cls.out = build(SITE_INDEX, cls.tmp.name, playground=pg)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, *parts):
        with open(os.path.join(self.out, *parts, "index.html"), encoding="utf-8") as f:
            return f.read()

    def test_start_button_names_the_download(self):  # PG-9
        page = self.page("playground")
        self.assertRegex(page, r'<button type="button" id="pg-start" class="button primary" data-size="\d+\.\d MB">Start the playground</button>')
        if not self.real:
            self.assertIn("Starting downloads about 9.9 MB from this site: Pyodide 314.0.7 and Kapitan 0.36.3", page)

    def test_only_its_own_script_before_start(self):  # PG-9: the worker and Pyodide load after the click
        page = self.page("playground")
        scripts = re.findall(r'<script[^>]*src="([^"]+)"', page)
        self.assertIn("../playground/playground.js", scripts)
        self.assertEqual([s for s in scripts if "playground" in s or "pyodide" in s], ["../playground/playground.js"])
        self.assertIn('<script type="module" src="../playground/playground.js"></script>', page)

    def test_csp_is_the_home_page_csp(self):  # PG-7
        csp = re.compile(r'Content-Security-Policy" content="([^"]*)"')
        self.assertEqual(csp.search(self.page("playground")).group(1), csp.search(self.page()).group(1))

    def test_no_inline_script_or_style(self):  # PG-7, CAT-3
        page = self.page("playground")
        self.assertNotRegex(page, r"<script(?![^>]*\bsrc=)(?![^>]*application/ld\+json)[^>]*>")
        self.assertNotIn(' style="', page)

    def test_backends_and_limits(self):  # PG-4, PG-11, PG-22
        page = self.page("playground")
        self.assertIn('<select id="pg-backend"><option value="omegaconf">omegaconf</option><option value="reclass">reclass</option></select>', page)
        self.assertIn("Not available: the reclass-rs backend, the jsonnet, helm, kustomize, CUE and external inputs", page)
        self.assertIn("The Terraform example writes Terraform JSON; terraform init, plan and apply do not run here.", page)  # PG-22
        self.assertIn("helm template output, rendered when this site was built", page)
        self.assertIn("Not compiled in your browser and not affected by your edits", page)

    def test_highlight_colours_reach_aa(self):  # PG-25: every token colour on pre's background, light and dark
        with open(os.path.join(HERE, "site", "static", "style.css"), encoding="utf-8") as f:
            css = f.read()
        colours = {n: (light, dark) for n, light, dark in re.findall(r"--([\w-]+): light-dark\((#[0-9a-f]{6}), (#[0-9a-f]{6})\);", css)}
        used = set(re.findall(r"\.token\.[^{]*\{[^}]*color: var\(--([\w-]+)\)", css))
        self.assertEqual(re.search(r"^pre \{[^}]*background: var\(--([\w-]+)\)", css, re.MULTILINE).group(1), "bg-subtle")
        self.assertEqual(used, {"text-muted", "accent", "ok", "warn"})
        for name in used:
            for theme in (0, 1):
                self.assertGreaterEqual(contrast(colours[name][theme], colours["bg-subtle"][theme]), 4.5, (name, ("light", "dark")[theme]))

    def test_build_takes_the_latest_listed_version_and_the_gate_hashes(self):  # PG-1, PG-5
        sys.path.insert(0, os.path.join(HERE, "playground"))
        try:
            import build as pgbuild
        finally:
            sys.path.pop(0)
        versions = {"1.2.0": {"digest": "a"}, "1.10.0": {"digest": "b", "yanked": "broken"}, "1.9.0": {"digest": "c"}}
        self.assertEqual(pgbuild.latest(versions), ("1.9.0", {"digest": "c"}))
        self.assertEqual(pgbuild.latest({"1.0.0": {"yanked": "x"}}), (None, None))
        version, hashes = pgbuild.gate_pins()["kapitan"]
        with open(os.path.join(HERE, "..", "sandbox", "requirements.in"), encoding="utf-8") as f:
            self.assertIn(f"=={version}", f.read())
        self.assertTrue(hashes and all(re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes))

    def test_runs_in_chrome(self):  # PG-3, PG-7 to PG-11
        if not self.real:
            self.skipTest("PLAYGROUND_BUILD not set")
        subprocess.run(["node", os.path.join(HERE, "playground", "browser.mjs"), self.out], check=True)


class PlaygroundReport(unittest.TestCase):  # PG-14, AC-43
    TITLE = "Playground differs from the gate image"
    DIFF = "basics (omegaconf): differs from the Pyodide output\nkubernetes (reclass): identical, 4 files\n"

    def report(self, issues, summary):
        """Runs report with a stand-in gh that answers `issue list` with issues; returns its calls and the body."""
        with tempfile.TemporaryDirectory() as tmp:
            log, body = os.path.join(tmp, "calls"), os.path.join(tmp, "body")
            with open(os.path.join(tmp, "gh"), "w", encoding="utf-8") as f:
                f.write("#!/usr/bin/env bash\n"
                        f'printf "%s\\n" "$*" >>{shlex.quote(log)}\n'
                        f"[[ $2 == list ]] && printf %s {shlex.quote(json.dumps(issues))}\n"
                        f'while (($#)); do [[ $1 == --body-file ]] && cp -- "$2" {shlex.quote(body)}; shift; done\n'
                        "exit 0\n")
            os.chmod(os.path.join(tmp, "gh"), 0o755)
            summary_file = os.path.join(tmp, "summary.txt")
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(summary)
            env = dict(os.environ, PATH=f"{tmp}{os.pathsep}{os.environ['PATH']}", REPO=f"{OWNER}/registry", GH_TOKEN="x")
            subprocess.run([os.path.join(HERE, "playground", "report"), summary_file, "https://github.com/run/1"],
                           env=env, check=True, capture_output=True)
            with open(log, encoding="utf-8") as f:
                calls = f.read().splitlines()
            with open(body, encoding="utf-8") as f:
                return calls, f.read()

    def test_creates_the_issue_when_none_with_its_title_is_open(self):
        calls, body = self.report([{"number": 3, "title": f"{self.TITLE} (old)"}], self.DIFF)
        self.assertEqual(calls[-1], f"issue create -R {OWNER}/registry --title {self.TITLE} --body-file " + calls[-1].split()[-1])
        self.assertIn("https://github.com/run/1", body)
        self.assertIn("differs from the gate image's", body)
        self.assertIn("basics (omegaconf): differs from the Pyodide output", body)

    def test_updates_the_open_issue_with_its_title(self):
        calls, _body = self.report([{"number": 3, "title": f"{self.TITLE} (old)"}, {"number": 7, "title": self.TITLE}], self.DIFF)
        self.assertTrue(calls[-1].startswith(f"issue edit 7 -R {OWNER}/registry --body-file "), calls)
        self.assertFalse(any(c.startswith("issue create") for c in calls))

    def test_says_when_the_comparison_did_not_run_or_found_nothing(self):
        _, body = self.report([], "")
        self.assertIn("The comparison did not run", body)
        _, body = self.report([], "basics (omegaconf): identical, 3 files\n")
        self.assertIn("The comparison found no difference; a later step of the run failed", body)


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
            fails = re.findall(r'<g id="[^"]+" class="(?:node|edge) fail">.*?</g>', svg, re.DOTALL)
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
        result = subprocess.run([sys.executable, "-I", SEO_CHECK, self.out], capture_output=True, text=True, check=False)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_consumer_docs_lookup(self):  # CAT-34d
        with open(os.path.join(HERE, "..", "docs", "consumers.md"), encoding="utf-8") as f:
            doc = f.read()
        start = doc.index("\n## Picking a version by what it is built for\n")
        section = doc[start:doc.index("\n## ", start + 1)]
        command = re.search(r"```sh\ncurl -fsSL https://kadet-hub\.org/catalog\.json \| (jq .*?)\n```", section, re.DOTALL).group(1)
        result = subprocess.run(shlex.split(command) + [os.path.join(self.out, "catalog.json")], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout, f"1.0.1 sha256:{'a' * 64}\n1.0.0 sha256:{'b' * 64}\n")  # not the yanked 0.8.0
        recipe = json.loads(re.search(r"```json\n(.*?)\n```", section, re.DOTALL).group(1))
        (name, datasource), = recipe["customDatasources"].items()
        self.assertEqual(datasource["defaultRegistryUrlTemplate"], "https://kadet-hub.org/catalog.json")
        self.assertEqual([m["datasourceTemplate"] for m in recipe["customManagers"]], [f"custom.{name}"])
        self.assertIn({"matchDatasources": ["docker"], "matchPackageNames": ["ghcr.io/kadet-hub/certmanager"], "enabled": False},
                      recipe["packageRules"])
        self.assertIn("not signed", section)
        self.assertIn("(specs/consumers.md)", section)  # CON-2


class ListedRecipe(unittest.TestCase):  # CAT-38 to CAT-38b
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = build(LISTED_INDEX, cls.tmp.name, recipe_layers(os.path.join(cls.tmp.name, "artifacts")))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, *parts, name="index.html"):
        with open(os.path.join(self.out, *parts, name), encoding="utf-8") as f:
            return f.read()

    def snippet(self, page, id):
        return _unescape(re.search(rf'<pre id="{id}"><code>(.*?)</code></pre>', page, re.DOTALL).group(1))

    def test_page_from_the_artifact(self):  # CAT-38: README sections, chart, level and generators of the latest listed version
        page = self.page("recipes", "cert-manager")
        self.assertIn("<title>cert-manager on Kubernetes, matched to its chart object by object</title>", page)  # same URL and content page
        self.assertIn(f"<li>Source chart: <code>{ARTIFACT_CHART}</code></li>", page)
        self.assertNotIn("v1.21.2", page)  # main's chart
        self.assertIn(f'<li>Generators: <a href="../../generators/kubernetes/#v1.7.1">kubernetes 1.7.1</a> <code>sha256:{"e" * 64}</code></li>', page)
        self.assertIn("<td><code>webhook.timeoutSeconds</code></td>", page)
        self.assertNotIn("alert(8)</script>", page)  # raw HTML is dropped
        self.assertIn('<a href="#v1.1.0"><code>1.1.0</code></a>, published <time datetime="2026-10-26T15:53:43Z">2026-10-26</time></li>', page)
        self.assertRegex(page, r"(?s)Proof level</a>: <code>deploys</code>, compared with the chart by the kadet-hub/recipes CI</li>\n"
                               r"<li><code>renders</code> passed in the <a href=\"https://github.com/kadet-hub/registry/actions/runs/42\">release run</a> "
                               r"of <time datetime=\"2026-10-10T08:00:00Z\">2026-10-10</time> with check 0.11.0, kind v0.33.0</li>\n"
                               r"<li>Output capabilities: <code>admission-webhook</code></li>")
        # CAT-7: no shortcode runs, relative links point into the source tree at source.sha.
        self.assertIn("Derived from the chart {{&lt; nonexistent &gt;}}.", page)
        self.assertIn("{{% nonexistent %}}", page)
        self.assertIn(f'<a href="https://github.com/{OWNER}/recipes/blob/{RECIPE_SHA}/cert-manager/tests/values.yaml">the values</a>', page)
        self.assertIn(f'<a href="https://github.com/{OWNER}/recipes/tree/{RECIPE_SHA}/cert-manager" data-goatcounter-click="source-repo/recipes/cert-manager">kadet-hub/recipes</a>', page)
        self.assertNotIn(CHART_RECIPE_SHA, page)
        self.assertNotIn("vendor", os.listdir(os.path.join(self.out, "recipes", "cert-manager")))
        md = self.page("recipes", "cert-manager", name="index.md")
        self.assertIn(f"\n- Latest version: 1.1.0, published 2026-10-26\n- Source chart: {ARTIFACT_CHART}\n"
                      "- Proof level: deploys, compared with the chart by the kadet-hub/recipes CI\n"
                      "- renders passed in the release run of 2026-10-10 with check 0.11.0, kind v0.33.0: https://github.com/kadet-hub/registry/actions/runs/42\n"
                      "- Output capabilities: admission-webhook\n- Inventory backends: omegaconf\n- Generators: kubernetes 1.7.1", md)
        self.assertNotIn("without Bitnami", self.page("recipes", "valkey"))

    def test_backends(self):  # CAT-38, REC-18: the record's inventory backends, none for a record without them
        self.assertIn("<li>Output capabilities: <code>admission-webhook</code></li>\n<li>Inventory backends: <code>omegaconf</code></li>",
                      self.page("recipes", "cert-manager"))
        self.assertNotIn("Inventory backends", self.page("recipes", "valkey"))
        self.assertNotIn("Inventory backends", self.page("recipes", "valkey", name="index.md"))

    def test_fetch_inventory_and_verification(self):  # CAT-38, CON-4, CON-5
        page = self.page("recipes", "cert-manager")
        self.assertEqual(self.snippet(page, "fetch"), "parameters:\n  kapitan:\n    dependencies:\n      - type: oci\n"
                         f"        source: ghcr.io/{OWNER}/recipes/cert-manager:1.1.0@sha256:{'b' * 64}\n"
                         "        output_path: inventory/classes/recipes/cert-manager")
        self.assertEqual(self.snippet(page, "verify"), f"gh attestation verify \\\n  oci://ghcr.io/{OWNER}/recipes/cert-manager@sha256:{'b' * 64} \\\n"
                         f"  --owner {OWNER} \\\n  --cert-identity {IDENTITY}")
        self.assertIn(f'<a href="https://github.com/{OWNER}/registry/blob/main/docs/consumers.md#verifying-by-hand">Verifying by hand</a>', page)
        self.assertEqual(self.snippet(page, "policy"), 'output_capabilities:\n  "compiled/<target>/*": [admission-webhook]')
        self.assertIn("This is <code>fetch/targets/recipes.yml</code> for version 1.1.0:", page)
        self.assertNotIn("type: git", page)
        md = self.page("recipes", "cert-manager", name="index.md")
        self.assertIn(f"\n```yaml\n{self.snippet(page, 'fetch')}\n```\n", md)
        self.assertIn(f"\n```sh\n{self.snippet(page, 'verify')}\n```\n", md)
        self.assertIn('\n```yaml\noutput_capabilities:\n  "compiled/<target>/*": [admission-webhook]\n```\n', md)
        self.assertIn("pins the recipe by version", page)
        self.assertNotIn('id="pull"', page)
        self.assertIn("This verifies the attestation of the recipe:", page)
        # The workflow adds an included recipe (CON-7); a local compile pulls it, and both verify it (REC-16, CON-6).
        page = self.page("recipes", "external-dns-powerdns")
        self.assertEqual(re.findall(r"source: (\S+)\n", self.snippet(page, "fetch") + "\n"),
                         [f"ghcr.io/{OWNER}/recipes/external-dns-powerdns:1.0.0@sha256:{'4' * 64}"])
        self.assertIn("<p>Version 1.0.0 includes powerdns 1.0.0. The consumer workflow adds the included recipes", page)
        pull = ('tmp=$(mktemp -d)\n'
                f'oras pull -o "$tmp" ghcr.io/{OWNER}/recipes/powerdns@sha256:{"5" * 64}\n'
                'mkdir -p inventory/classes/recipes/powerdns\n'
                'tar -xf "$tmp/powerdns.tar" -C inventory/classes/recipes/powerdns --no-same-owner')
        self.assertEqual(self.snippet(page, "pull"), pull)
        self.assertEqual(re.findall(r"oci://(\S+)", self.snippet(page, "verify")),
                         [f"ghcr.io/{OWNER}/recipes/external-dns-powerdns@sha256:{'4' * 64}", f"ghcr.io/{OWNER}/recipes/powerdns@sha256:{'5' * 64}"])
        self.assertIn("This verifies the attestation of the recipe and of the recipes it includes:", page)
        md = self.page("recipes", "external-dns-powerdns", name="index.md")
        self.assertIn(f"\n```yaml\n{self.snippet(page, 'fetch')}\n```\n\nexternal-dns-powerdns 1.0.0 includes powerdns 1.0.0. ", md)
        self.assertIn(f"\n```sh\n{pull}\n```\n", md)
        self.assertIn("<li>No <code>renders</code> result in the release run's record</li>", page)  # a scan record without it
        self.assertIn("<li>Output capabilities: none</li>", page)
        self.assertNotIn('id="policy"', page)

    def test_yanked_versions_and_generators(self):  # CAT-38: the reason and no fetch inventory entry
        page = self.page("recipes", "cert-manager")
        versions = page[page.index("<h2>Versions</h2>"):]
        self.assertLess(versions.index('id="v1.1.0"'), versions.index('id="v1.0.0"'))
        self.assertIn(f'<li id="v1.0.0"><code>1.0.0</code>, <time datetime="2026-10-26T15:53:43Z">2026-10-26</time>: <code>sha256:{"a" * 64}</code>'
                      '<br><span class="warning">Yanked: wrong CRDs</span></li>', versions)
        self.assertEqual(page.count("a" * 64), 1)
        self.assertIn(f"\n## Versions\n\n- 1.1.0, 2026-10-26: sha256:{'b' * 64}\n- 1.0.0, 2026-10-26: sha256:{'a' * 64}; yanked: wrong CRDs\n",
                      self.page("recipes", "cert-manager", name="index.md"))
        page = self.page("recipes", "valkey")
        reason = "pins the generator kubernetes 1.9.0, which is yanked: renders a broken Service"
        self.assertIn(f'<p class="warning">Version 1.0.0 {reason}</p>', page)
        self.assertIn(f'<br><span class="warning">P{reason[1:]}</span></li>', page)
        self.assertNotIn('<pre id="fetch">', page)
        self.assertNotIn('<pre id="verify">', page)
        self.assertNotIn(f"recipes/valkey:1.0.0@sha256:{'3' * 64}", page)
        md = self.page("recipes", "valkey", name="index.md")
        self.assertIn(f"\n## Fetching it\n\nVersion 1.0.0 {reason}\n\nThe consumer workflow rejects", md)
        self.assertNotIn("```yaml\nparameters:", md)

    def test_all_versions_yanked(self):  # CAT-38: no version to read, so the page stays built from main
        page = self.page("recipes", "mysql")
        self.assertIn(f"ref: {CHART_RECIPE_SHA}\n", self.snippet(page, "fetch"))
        self.assertIn("Until this recipe is published as an OCI artifact", page)
        self.assertNotIn("Latest version", page)
        self.assertIn('<br><span class="warning">Yanked: entry removed</span></li>', page)
        self.assertFalse(os.path.exists(os.path.join(self.out, "recipes", "no-page")))  # no content page, no page
        page = self.page("recipes", "miniflux")  # unlisted
        self.assertNotIn("<h2>Versions</h2>", page)
        self.assertIn("        subdir: miniflux\n", self.snippet(page, "fetch"))

    def test_layer_missing_fails_the_build(self):  # CAT-38, CAT-37a
        for case, layers in (("missing", {k: v for k, v in LAYERS.items() if k != "valkey"}),
                             ("escapes", dict(LAYERS, valkey=dict(VALKEY_RECIPE_FILES, **{"../../escaped.yml": "x"})))):
            with self.subTest(case), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(subprocess.CalledProcessError) as failed:
                    build(LISTED_INDEX, tmp, recipe_layers(os.path.join(tmp, "artifacts"), layers), capture=True)
                self.assertIn(f"::error::recipes: valkey: {tmp}/artifacts/recipes/valkey.tar not unpacked", failed.exception.stdout)

    def test_build_fetches_the_layer_by_digest(self):  # CAT-38: the online build with curl, git, gh and oras faked
        shims = {"curl": 'while (($#)); do case $1 in -o) out=$2; shift;; https://*) url=$1;; esac; shift; done\n'
                         'echo "$url" >>"$LOG"\n'
                         'case $url in\n'
                         '  https://raw.githubusercontent.com/*/recipes/*/*) cp "$RECIPES/inventory/classes/recipes/${url#https://raw.githubusercontent.com/*/recipes/*/}" "$out";;\n'
                         '  *) exit 22;;\n'
                         'esac\n',
                 "git": 'printf "%s\\trefs/heads/main\\n" "$RECIPES_SHA"\n',
                 "gh": "exit 1\n",
                 "oras": 'ref=${!#}; echo "oras $1 $ref" >>"$LOG"\n'
                         'case $1 in\n'
                         '  manifest) printf \'{"artifactType": "%s", "layers": [{"digest": "sha256:%s"}]}\' "$ORAS_TYPE" "$(printf "f%.0s" {1..64})";;\n'
                         '  blob) while (($#)); do case $1 in --output) out=$2; shift;; esac; shift; done\n'
                         '        name=${ref#ghcr.io/*/recipes/}; cp "$LAYERS/recipes/${name%@*}.tar" "$out";;\n'
                         'esac\n'}
        index = {"serial": 1, "generators": {}, "recipes": {"cert-manager": LISTED_INDEX["recipes"]["cert-manager"]}}
        for artifact_type in ("application/vnd.kadet-hub.recipe.v1", "application/vnd.kadet-hub.generator.v1"):
            with self.subTest(artifact_type), tempfile.TemporaryDirectory() as tmp:
                os.mkdir(os.path.join(tmp, "bin"))
                for name, script in shims.items():
                    with open(os.path.join(tmp, "bin", name), "w", encoding="utf-8") as f:
                        f.write("#!/usr/bin/env bash\n" + script)
                    os.chmod(os.path.join(tmp, "bin", name), 0o755)
                recipes, log = os.path.join(tmp, "recipes"), os.path.join(tmp, "fetch.log")
                recipe_classes(os.path.join(recipes, "inventory", "classes"))
                with open(os.path.join(tmp, "index.json"), "w", encoding="utf-8") as f:
                    json.dump(index, f)
                env = dict(os.environ, OWNER=OWNER, PATH=os.path.join(tmp, "bin") + os.pathsep + os.environ["PATH"], LOG=log, RECIPES=recipes,
                           RECIPES_SHA=CHART_RECIPE_SHA, ORAS_TYPE=artifact_type, LAYERS=recipe_layers(os.path.join(tmp, "layers")))
                env.pop("CATALOG_OFFLINE", None)
                p = subprocess.run([os.path.join(HERE, "build"), os.path.join(tmp, "index.json"), os.path.join(tmp, "out")], env=env, capture_output=True, text=True, check=False)
                with open(log, encoding="utf-8") as f:
                    fetched = f.read()
                self.assertIn(f"oras manifest ghcr.io/{OWNER}/recipes/cert-manager@sha256:{'b' * 64}\n", fetched)  # 1.1.0, not the yanked 1.0.0
                self.assertNotIn("/cert-manager/", fetched)  # nothing from main
                if artifact_type.endswith("generator.v1"):
                    self.assertEqual(p.returncode, 1)
                    self.assertIn(f"::error::recipes: ghcr.io/{OWNER}/recipes/cert-manager@sha256:{'b' * 64} not fetched", p.stdout)
                    continue
                self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
                self.assertIn(f"/{OWNER}/recipes/{CHART_RECIPE_SHA}/valkey/README.md\n", fetched)  # unlisted: from main
                self.assertIn(f"oras blob ghcr.io/{OWNER}/recipes/cert-manager@sha256:{'f' * 64}\n", fetched)
                with open(os.path.join(tmp, "out", "recipes", "cert-manager", "index.html"), encoding="utf-8") as f:
                    self.assertIn(f"<li>Source chart: <code>{ARTIFACT_CHART}</code></li>", f.read())

    def test_index_shows_the_latest_version(self):  # CAT-38a
        index = self.page("recipes")
        self.assertRegex(index, r'recipes/cert-manager/">.*?Proof level: <code>deploys</code>, version <code>1\.1\.0</code></p></li>')
        self.assertRegex(index, r'recipes/valkey/">.*?Proof level: <code>deploys</code>, version <code>1\.0\.0</code></p></li>')
        self.assertRegex(index, r'recipes/miniflux/">.*?Proof level: <code>deploys</code></p></li>')  # unlisted
        self.assertRegex(index, r'recipes/mysql/">.*?Proof level: <code>deploys</code></p></li>')  # every version yanked

    def test_catalog_json(self):  # CAT-38b
        with open(os.path.join(self.out, "catalog.json"), encoding="utf-8") as f:
            data = json.load(f)
        recipes = {r["name"]: r for r in data["recipes"]}
        self.assertEqual(list(recipes), ["cert-manager", "external-dns-powerdns", "mysql", "no-page", "powerdns", "valkey"])
        fields = ("version", "digest", "yanked", "level", "chart", "generators")
        self.assertEqual([{k: v[k] for k in fields} for v in recipes["cert-manager"]["versions"]], [
            {"version": "1.1.0", "digest": "sha256:" + "b" * 64, "yanked": None, "level": "deploys",
             "chart": {"repo": "quay.io/jetstack/charts/cert-manager", "version": "v1.22.0", "digest": "sha256:" + "c" * 64},
             "generators": [{"name": "kubernetes", "version": "1.7.1", "digest": "sha256:" + "e" * 64, "yanked": None}]},
            {"version": "1.0.0", "digest": "sha256:" + "a" * 64, "yanked": "wrong CRDs", "level": "deploys",
             "chart": {"repo": "quay.io/jetstack/charts/cert-manager", "version": "v1.22.0", "digest": "sha256:" + "c" * 64},
             "generators": [{"name": "kubernetes", "version": "1.7.0", "digest": "sha256:" + "d" * 64, "yanked": None}]}])
        self.assertEqual(recipes["cert-manager"]["description"], "The cert-manager recipe 1.1.0.")  # the latest listed version's
        self.assertEqual(recipes["valkey"]["versions"][0]["generators"][0]["yanked"], "renders a broken Service")
        self.assertIsNone(recipes["powerdns"]["versions"][0]["chart"])
        self.assertEqual(recipes["mysql"]["description"], "The mysql recipe 1.0.0.")  # every version yanked: the newest

    def test_not_counted_with_generators(self):  # CAT-38b
        home = self.page()
        self.assertEqual(re.findall(r'data-name="([^"]+)"', home), ["kubernetes"])
        self.assertRegex(home, r'data-tag="helm"[^>]*>.*?helm <span class="count">\(1\)</span>')
        self.assertNotIn("Certificate", self.page("kinds"))
        self.assertEqual(re.findall(r'<tr id="([^"]+)">', self.page("compatibility")), ["kubernetes"])

    def test_seo(self):  # CAT-11d over the new markup
        result = subprocess.run([sys.executable, "-I", SEO_CHECK, self.out], capture_output=True, text=True, check=False)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_consumer_docs_lookup(self):  # CAT-38b, as CAT-34d
        with open(os.path.join(HERE, "..", "docs", "consumers.md"), encoding="utf-8") as f:
            doc = f.read()
        command = re.search(r"```sh\ncurl -fsSL https://kadet-hub\.org/catalog\.json \| (jq [^`]*?\.recipes\[\].*?)\n```", doc, re.DOTALL).group(1)
        for name, expected in (("cert-manager", f"1.1.0 sha256:{'b' * 64}\n"), ("valkey", "")):  # not the yanked 1.0.0; valkey pins a yanked generator
            result = subprocess.run(shlex.split(command.replace("cert-manager", name)) + [os.path.join(self.out, "catalog.json")],
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, expected)
        self.assertIn("A recipe digest needs the same check against\nthe index's `recipes` (CON-5).", doc)


# CAT-40: uptime-kuma listed, as in the release build.
QUICKSTART_INDEX = {"serial": 5, "generators": {"kubernetes": {"1.7.0": record("d")}},
                    "recipes": {"uptime-kuma": {"1.0.0": recipe_record("uptime-kuma", "8")}}}
UPTIME_KUMA_FILES = dict(NEW_RECIPES)["uptime-kuma"]


class Quickstart(unittest.TestCase):  # CAT-40
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = build(QUICKSTART_INDEX, cls.tmp.name, recipe_layers(os.path.join(cls.tmp.name, "artifacts"), {"uptime-kuma": UPTIME_KUMA_FILES}))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, *parts):
        with open(os.path.join(self.out, *parts, "index.html"), encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def snippets(page):
        return [(i, _unescape(t)) for i, t in re.findall(r'<pre id="([^"]+)"><code>(.*?)</code></pre>', page, re.DOTALL)]

    def test_commands(self):  # every command in order; the manual run on kind is redone when this list changes
        page = self.page("quickstart")
        recipe = dict(self.snippets(self.page("recipes", "uptime-kuma")))
        digest = "sha256:" + "8" * 64
        fetch = ("parameters:\n  kapitan:\n    dependencies:\n      - type: oci\n"
                 f"        source: ghcr.io/{OWNER}/recipes/uptime-kuma:1.0.0@{digest}\n        output_path: inventory/classes/recipes/uptime-kuma")
        self.assertEqual(self.snippets(page), [
            ("cluster", "kind create cluster --name quickstart-uptime-kuma"),
            ("install", "uv tool install --python 3.13 --with omegaconf==2.4.0.dev4 --with oras 'kapitan[omegaconf,reclass-rs]==0.36.3'"),
            ("project", ("mkdir -p uptime-kuma/fetch/targets uptime-kuma/inventory/targets\ncd uptime-kuma\n"
                         "cat > .kapitan <<'EOF'\nglobal:\n  inventory-backend: omegaconf\nEOF")),
            ("fetch", f"cat > fetch/targets/recipes.yml <<'EOF'\n{fetch}\nEOF"),
            ("target", f"cat > inventory/targets/uptime-kuma.yml <<'EOF'\n{recipe['include']}\nEOF"),
            ("verify", f"gh attestation verify \\\n  oci://ghcr.io/{OWNER}/recipes/uptime-kuma@{digest} \\\n  --owner {OWNER} \\\n  --cert-identity {IDENTITY}"),
            ("compile", "kapitan compile --inventory-path fetch --fetch --output-path .\nkapitan compile --fetch"),
            ("apply", ("kubectl create namespace uptime-kuma\nkubectl apply -R -f compiled/uptime-kuma\n"
                       "kubectl -n uptime-kuma rollout status statefulset/uptime-kuma --timeout=5m")),
            ("open", "kubectl -n uptime-kuma port-forward service/uptime-kuma 3001:3001"),
            ("cleanup", "kind delete cluster --name quickstart-uptime-kuma")])
        # The recipe page's own snippets (CAT-37c, CAT-38), and the install command of docs/consumers.md with oras.
        self.assertEqual((recipe["fetch"], recipe["verify"], recipe["commands"], recipe.get("pull")),
                         (fetch, dict(self.snippets(page))["verify"], dict(self.snippets(page))["compile"],
                          dict(self.snippets(page)).get("pull")))  # uptime-kuma includes no recipe (CON-7)
        self.assertTrue(recipe["include"].startswith("classes:\n  - recipes.uptime-kuma\n"))
        with open(os.path.join(HERE, "..", "docs", "consumers.md"), encoding="utf-8") as f:
            install = re.search(r"```sh\n(uv tool install [^\n]*)\n```", f.read()).group(1)
        self.assertEqual(install.replace(" 'kapitan", " --with oras 'kapitan"), dict(self.snippets(page))["install"])
        self.assertIn(f'<a href="https://github.com/{OWNER}/registry/blob/main/docs/consumers.md#verifying-a-recipe-by-hand">', page)
        # CAT-42 on the quickstart and on a listed recipe's verify command.
        self.assertIn('data-copy="fetch" aria-label="Copy fetch inventory" data-goatcounter-click="copy-fetch-inventory/quickstart"', page)
        self.assertIn('data-copy="verify" aria-label="Copy verify command" data-goatcounter-click="copy-verify/quickstart"', page)
        self.assertIn('data-goatcounter-click="copy-verify/recipes/uptime-kuma"', self.page("recipes", "uptime-kuma"))

    def test_without_a_usable_version(self):  # CAT-40: the latest version pins a yanked generator
        index = dict(QUICKSTART_INDEX, generators={"kubernetes": {"1.7.0": record("d", yanked="renders a broken Service")}})
        with tempfile.TemporaryDirectory() as tmp:
            out = build(index, tmp, recipe_layers(os.path.join(tmp, "artifacts"), {"uptime-kuma": UPTIME_KUMA_FILES}))
            with open(os.path.join(out, "quickstart", "index.html"), encoding="utf-8") as f:
                page = f.read()
        self.assertIn('<p class="warning">The uptime-kuma recipe has no version this page can pin right now. '
                      'Its <a href="../recipes/uptime-kuma/">recipe page</a> says why.</p>', page)
        self.assertNotIn("<pre", page)
        self.assertIn(">Coming from Helm?</h2>", page)

    def test_seo(self):  # CAT-11d over the new page
        result = subprocess.run([sys.executable, "-I", SEO_CHECK, self.out], capture_output=True, text=True, check=False)
        self.assertEqual((result.returncode, result.stdout), (0, ""))


# CAT-45: fixture stack posts; stack-a is the newer. LISTED_INDEX lists the generator kubernetes, not demo.
STACK_POSTS = {
    "stack-a": 'title: "Stack A: cert-manager and Valkey on Kubernetes"\ndate: 2000-01-02\n'
               'description: "The newer fixture stack: two recipes, a listed generator and one the fixture index does not list."\n'
               "stack:\n  recipes: [cert-manager, valkey]\n  generators: [kubernetes, demo]\n  example: stack-a",
    "stack-b": 'title: "Stack B: Valkey alone on Kubernetes with Kapitan"\ndate: 2000-01-01\n'
               'description: "The older fixture stack: one recipe and no generators, with its folder in kadet-hub/examples."\n'
               "stack:\n  recipes: [valkey]\n  example: stack-b",
}


def stack_posts():
    """CAT-45: the committed blog posts with a stack field, by name."""
    blog = os.path.join(HERE, "site", "content", "blog")
    names = []
    for f in sorted(os.listdir(blog)):
        with open(os.path.join(blog, f), encoding="utf-8") as fh:
            if "\nstack:\n" in fh.read().split("\n---\n", 1)[0]:
                names.append(f[:-3])
    return names


def stack_build(tmp, posts, *args):
    """CAT-45: Hugo over the site with LISTED_INDEX and the generator old; posts maps a post's name to its front matter, or None to remove it."""
    site = os.path.join(tmp, "site")
    shutil.copytree(os.path.join(HERE, "site"), site)
    for name, front in posts.items():
        path = os.path.join(site, "content", "blog", name + ".md")
        if front is None:
            os.remove(path)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"---\n{front}\n---\n\nThe post.\n")
    os.makedirs(os.path.join(site, "data"))
    shutil.copy(os.path.join(HERE, "..", "policy", "tags.yaml"), os.path.join(site, "data", "tags.yaml"))
    recipe_classes(os.path.join(site, "assets", "classes"))
    index = dict(LISTED_INDEX, generators=dict(LISTED_INDEX["generators"], old=INDEX["generators"]["old"]))
    with open(os.path.join(site, "data", "catalog.json"), "w", encoding="utf-8") as f:
        json.dump(view(index, OWNER, lambda _: None), f)
    out = os.path.join(tmp, "out")
    return out, subprocess.run(["hugo", "--logLevel", "error", "--source", site, "--destination", out, *args], capture_output=True, text=True, check=False)


class Stacks(unittest.TestCase):  # CAT-45 to CAT-50
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out, built = stack_build(cls.tmp.name, {**dict.fromkeys(stack_posts()), **STACK_POSTS})  # the fixtures alone
        if built.returncode:
            raise AssertionError(built.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, *parts):
        with open(os.path.join(self.out, *parts, "index.html"), encoding="utf-8") as f:
            return f.read()

    def test_stacks_page(self):  # CAT-45, CAT-46
        page = self.page("stacks")
        self.assertEqual(re.findall(r'<li><a href="\.\./blog/([^/]+)/">', page), ["stack-a", "stack-b"])  # newest first
        self.assertIn('<li><a href="../blog/stack-a/">Stack A: cert-manager and Valkey on Kubernetes</a>'
                      "<p>The newer fixture stack: two recipes, a listed generator and one the fixture index does not list.</p>\n"
                      '<p>Recipes: <a href="../recipes/cert-manager/"><code>cert-manager</code></a>, <a href="../recipes/valkey/"><code>valkey</code></a></p>\n'
                      '<p>Generators: <a href="../generators/kubernetes/"><code>kubernetes</code></a>, <code>demo</code></p>\n'  # demo: no page
                      f'<p>Project: <a href="https://github.com/{OWNER}/examples/tree/main/stack-a">kadet-hub/examples/stack-a</a></p></li>', page)
        self.assertNotIn("Generators:", page.split("blog/stack-b/", 1)[1])
        with tempfile.TemporaryDirectory() as tmp:  # no stack post published
            out, built = stack_build(tmp, dict.fromkeys(stack_posts()))
            self.assertEqual(built.returncode, 0, built.stderr)
            with open(os.path.join(out, "stacks", "index.html"), encoding="utf-8") as f:
                self.assertIn('<p class="empty">No stack post is published yet.</p>', f.read())

    def test_used_in_stacks(self):  # CAT-48
        a = '<li><a href="../../blog/stack-a/">Stack A: cert-manager and Valkey on Kubernetes</a></li>'
        b = '<li><a href="../../blog/stack-b/">Stack B: Valkey alone on Kubernetes with Kapitan</a></li>'
        self.assertRegex(self.page("recipes", "valkey"), rf"<h2>Used in stacks</h2>\n<ul>{re.escape(a + b)}</ul>\s*<h2>Versions</h2>")
        self.assertIn(f"<h2>Used in stacks</h2>\n<ul>{a}</ul>", self.page("recipes", "cert-manager"))
        self.assertNotIn("Used in stacks", self.page("recipes", "mysql"))
        page = self.page("generators", "kubernetes")
        self.assertRegex(page, r'<li><a href="#stacks">Used in stacks</a></li>\s*<li><a href="#versions">Versions</a></li>')  # CAT-19
        self.assertRegex(page, rf'(?s)<div class="generator-body">\s*<section class="stacks" aria-labelledby="stacks">\n'
                               rf'<h2 id="stacks">Used in stacks</h2>\n<ul>{re.escape(a)}</ul>\n</section>\s*</div>')
        self.assertNotIn("Used in stacks", self.page("generators", "old"))

    def test_queued_stack_posts(self):  # CAT-49: every committed stack post, also before its date
        with tempfile.TemporaryDirectory() as tmp:
            out, built = stack_build(tmp, {}, "--buildFuture")
            self.assertEqual(built.returncode, 0, built.stderr)
            with open(os.path.join(out, "stacks", "index.html"), encoding="utf-8") as f:
                page = f.read()
        self.assertGreaterEqual(len(stack_posts()), 5)
        self.assertEqual(sorted(re.findall(r'<li><a href="\.\./blog/([^/]+)/">', page)), stack_posts())
        entries = {f[:-5] for f in os.listdir(os.path.join(HERE, "..", "generators"))}
        for line in re.findall(r"<p>Generators: (.*?)</p>", page):
            for name in re.findall(r"<code>([^<]+)</code>", line):
                self.assertIn(name, entries)
        projects = re.findall(rf'<li><a href="\.\./blog/([^/]+)/">.*?<p>Project: <a href="https://github\.com/{OWNER}/examples/tree/main/([^"]+)">', page, re.DOTALL)
        self.assertEqual(len(projects), len(stack_posts()))
        for name, example in projects:  # CAT-50: the post's own project link
            with open(os.path.join(HERE, "site", "content", "blog", name + ".md"), encoding="utf-8") as f:
                link = f"(https://github.com/kadet-hub/examples/tree/main/{example})"
                self.assertTrue(link in f.read().split("\n---\n", 1)[1], f"{name}.md does not link {link}")

    def test_unknown_recipe_fails_the_build(self):  # CAT-49
        front = STACK_POSTS["stack-b"]
        for case, post, error in (("recipe", front.replace("[valkey]", "[valkey, no-such-recipe]"),
                                   "blog/stack-b.md: stack names the recipe no-such-recipe, which has no page at /recipes/no-such-recipe/"),
                                  ("example", front.replace("\n  example: stack-b", ""), "blog/stack-b.md: stack names no example"),
                                  *((f"example {bad}", front.replace("example: stack-b", f"example: {bad}"),  # CAT-50
                                     f"blog/stack-b.md: stack names the example {bad}, which is not a folder name of lowercase letters, digits and hyphens")
                                    for bad in ("Stack-B", "stack-b/", "stack-b/sub", "stack--b"))):
            with self.subTest(case), tempfile.TemporaryDirectory() as tmp:
                _, built = stack_build(tmp, {"stack-b": post})
                self.assertNotEqual(built.returncode, 0)
                self.assertIn(error, built.stderr)

    def test_seo(self):  # CAT-11d over the new page and sections
        result = subprocess.run([sys.executable, "-I", SEO_CHECK, self.out], capture_output=True, text=True, check=False)
        self.assertEqual((result.returncode, result.stdout), (0, ""))


# CAT-39: the rescan's image report (SEC-19): graded, ungraded, unscanned, outdated and by-tag pages, and recipes at main.
IMAGE = "registry.example/{}:1.0@sha256:" + "f" * 64
MAIN_SHA = "2" * 40
SECURITY = {"scanned": "2026-10-29T04:31:07Z", "trivy": "0.76.1", "db": "2026-10-29T07:17:11Z",
            "pages": {"generators/demo": {"1.10.0": [IMAGE.format("a"), IMAGE.format("b")]},
                      "generators/clean": {"1.0.0": [IMAGE.format("clean")]},
                      "generators/nopin": {"1.0.0": []},
                      "generators/failing": {"1.0.0": [IMAGE.format("a"), IMAGE.format("missing")]},
                      "generators/stale": {"1.0.0": [IMAGE.format("a")]},
                      "generators/tagged": {"1.0.0": ["registry.example/kubelet:v1.37.1", "quay.io/strimzi/kafka:1.3.0-kafka"]},
                      "recipes/cert-manager": {"1.1.0": [IMAGE.format("unknown")], f"main@{MAIN_SHA}": [IMAGE.format("a")]},
                      "recipes/valkey": {f"main@{MAIN_SHA}": [IMAGE.format("b")]},
                      "recipes/miniflux": {f"main@{MAIN_SHA}": ["postgres:18.6@sha256:" + "f" * 64, "ghcr.io/miniflux/miniflux:2.3.4@sha256:" + "f" * 64,
                                                                IMAGE.format("clean")]},
                      "recipes/no-page": {f"main@{MAIN_SHA}": [IMAGE.format("b")]}},
            "images": {IMAGE.format("a"): {"digest": "sha256:" + "f" * 64, "vulnerabilities": [
                           {"id": "CVE-2026-3", "severity": "UNKNOWN", "package": "zlib", "installed": "1.3", "fixed": ""},
                           {"id": "CVE-2026-2", "severity": "LOW", "package": "zlib", "installed": "1.3", "fixed": "1.3.1"},
                           {"id": "CVE-2026-1", "severity": "HIGH", "package": "<script>alert(10)</script>", "installed": "1.0\u202e", "fixed": ""}]},
                       IMAGE.format("b"): {"digest": "sha256:" + "f" * 64, "vulnerabilities": [
                           {"id": "CVE-2026-1", "severity": "HIGH", "package": "openssl", "installed": "3.0.1", "fixed": "3.0.2"},
                           {"id": "GHSA-aaaa-bbbb-cccc", "severity": "MEDIUM", "package": "golang.org/x/net", "installed": "0.1.0", "fixed": "0.2.0"}]},
                       IMAGE.format("clean"): {"digest": "sha256:" + "f" * 64, "vulnerabilities": []},
                       "postgres:18.6@sha256:" + "f" * 64: {"digest": "sha256:" + "f" * 64, "vulnerabilities": []},
                       "ghcr.io/miniflux/miniflux:2.3.4@sha256:" + "f" * 64: {"digest": "sha256:" + "f" * 64, "vulnerabilities": []},
                       IMAGE.format("unknown"): {"digest": "sha256:" + "f" * 64,
                                                 "vulnerabilities": [{"id": "CVE-2026-4", "severity": "UNKNOWN", "package": "x", "installed": "1", "fixed": ""}]},
                       IMAGE.format("missing"): {"error": "MANIFEST_UNKNOWN: manifest\x1b[31m unknown", "missing": True},  # by digest: still a failure
                       "registry.example/kubelet:v1.37.1": {"digest": "sha256:" + "7" * 64,
                                                            "vulnerabilities": [{"id": "CVE-2026-5", "severity": "LOW", "package": "y", "installed": "1", "fixed": ""}]},
                       "quay.io/strimzi/kafka:1.3.0-kafka": {"error": "MANIFEST_UNKNOWN: manifest unknown", "missing": True}}}
SECURITY_INDEX = {"serial": 9, "generators": {"demo": {"1.10.0": record("b")}, "clean": {"1.0.0": record("c")}, "nopin": {"1.0.0": record("d")},
                                              "failing": {"1.0.0": record("e")}, "stale": {"2.0.0": record("f")}, "tagged": {"1.0.0": record("9")},
                                              "old": {"0.1.0": record("1", yanked="entry removed")}},
                  "recipes": {"cert-manager": LISTED_INDEX["recipes"]["cert-manager"]}}


class Security(unittest.TestCase):  # CAT-39 to CAT-39c
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        report = os.path.join(cls.tmp.name, "security.json")
        with open(report, "w", encoding="utf-8") as f:
            json.dump(SECURITY, f)
        artifacts = recipe_layers(os.path.join(cls.tmp.name, "artifacts"), {"cert-manager": CERT_MANAGER_LAYER})
        cls.out = build(SECURITY_INDEX, cls.tmp.name, artifacts, security=report)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def page(self, *parts, name="index.html"):
        with open(os.path.join(self.out, *parts, name), encoding="utf-8") as f:
            return f.read()

    def fact(self, *parts):
        page = self.page(*parts)
        if parts[0] == "recipes":
            return re.search(r"<li>Image security: (.*?)</li>", page).group(1)
        return re.search(r"<dt>Image security</dt><dd>(.*?)</dd>", page).group(1)

    def test_report_on_the_pages(self):  # CAT-39: counts per severity, grade, scan time, link
        self.assertRegex(self.fact("generators", "demo"), r'^Grade <span class="grade grade-d">D</span> 5 findings, one per advisory and package, '
                         r"in the 2 images of version 1\.10\.0: CRITICAL 0, HIGH 2, MEDIUM 1, LOW 1, UNKNOWN 1\. Scanned 2026-10-29 04:31 UTC\. "
                         r'<a href="[./]*security/generators/demo/">Full report</a>$')
        self.assertRegex(self.fact("generators", "clean"), r'^Grade <span class="grade grade-a">A</span> 0 findings, .* in the 1 image of version 1\.0\.0: ')
        self.assertRegex(self.fact("recipes", "cert-manager"), r'^grade <span class="grade grade-u">-</span> 1 finding, .*UNKNOWN 1\. ')  # not main's
        self.assertIn("- Image security: grade -, 1 finding, one per advisory and package, in the 1 image of version 1.1.0: CRITICAL 0, HIGH 0, "
                      "MEDIUM 0, LOW 0, UNKNOWN 1. Scanned 2026-10-29 04:31 UTC. Full report: https://kadet-hub.org/security/recipes/cert-manager/\n",
                      self.page("recipes", "cert-manager", name="index.md"))  # CAT-37b

    def test_upstream_images(self):  # CAT-39: the grade rates the images, each linked to its registry page where it has one
        self.assertTrue(self.fact("recipes", "miniflux").endswith(
            '<br>The grade rates the upstream images the recipe pins, not the recipe: <a href="https://hub.docker.com/_/postgres"><code>postgres</code></a>, '
            '<a href="https://ghcr.io/miniflux/miniflux"><code>ghcr.io/miniflux/miniflux</code></a>, <code>registry.example/clean</code>.'))
        self.assertIn("\n- The grade rates the upstream images the recipe pins, not the recipe: postgres (https://hub.docker.com/_/postgres), "
                      "ghcr.io/miniflux/miniflux (https://ghcr.io/miniflux/miniflux), registry.example/clean\n",
                      self.page("recipes", "miniflux", name="index.md"))  # CAT-37b
        self.assertNotIn("upstream images", self.fact("recipes", "mysql"))  # not scanned: no grade, no note
        self.assertNotIn("upstream images", self.page("generators", "demo"))

    def test_by_tag(self):  # CAT-39a: a reference by tag is scanned at its digest then; a tag no registry serves names no image
        self.assertRegex(self.fact("generators", "tagged"), r'^Grade <span class="grade grade-b">B</span> 1 finding, one per advisory and package, '
                         r"in the 1 image of version 1\.0\.0, 1 by tag, digest at scan time: CRITICAL 0, HIGH 0, MEDIUM 0, LOW 1, UNKNOWN 0\. ")
        page = self.page("security", "generators", "tagged")
        self.assertIn(f"<p>By tag, digest at scan time: <code>sha256:{'7' * 64}</code></p>", page)
        self.assertIn('<p class="warning">No image at this tag on 2026-10-29: MANIFEST_UNKNOWN: manifest unknown</p>', page)

    def test_recipe_at_main(self):  # CAT-39: a recipe page without a listed version reports main of kadet-hub/recipes
        self.assertRegex(self.fact("recipes", "valkey"), r'^grade <span class="grade grade-d">D</span> 2 findings, one per advisory and package, '
                         rf"in the 1 image of main at {MAIN_SHA[:12]}: CRITICAL 0, HIGH 1, MEDIUM 1, LOW 0, UNKNOWN 0\. Scanned 2026-10-29 04:31 UTC\. "
                         r'<a href="[./]*security/recipes/valkey/">Full report</a>'
                         r"<br>The grade rates the upstream images the recipe pins, not the recipe: <code>registry\.example/b</code>\.$")
        self.assertIn(f"commit <code>{MAIN_SHA}</code>", self.page("security", "recipes", "valkey"))
        self.assertEqual(self.fact("recipes", "mysql"), "Not scanned: the image scan of 2026-10-29 did not cover main of kadet-hub/recipes.")
        self.assertFalse(os.path.exists(os.path.join(self.out, "security", "recipes", "no-page")))  # no recipe page to link it

    def test_not_scanned(self):  # CAT-39: the page says why instead of showing a grade
        self.assertEqual(self.fact("generators", "nopin"), "Version 1.0.0 names no image.")
        self.assertRegex(self.fact("generators", "failing"), r"^Not graded: 1 of the 2 images of version 1\.0\.0 could not be scanned on "
                         r'2026-10-29 04:31 UTC\. <a href="[./]*security/generators/failing/">Full report</a>$')
        self.assertEqual(self.fact("generators", "stale"), "Not scanned: the image scan of 2026-10-29 did not cover version 2.0.0.")
        self.assertEqual(self.fact("generators", "old"), "Not scanned: no version is listed.")
        for name in ("nopin", "stale", "old"):
            self.assertFalse(os.path.exists(os.path.join(self.out, "security", "generators", name)))

    def test_full_report(self):  # CAT-39b
        page = self.page("security", "generators", "demo")
        self.assertIn("<h1>Image security report: demo generator</h1>", page)
        self.assertIn('<meta name="description" content="Vulnerabilities that Trivy finds in the container images the generator demo names at 1.10.0, '
                      'with fixed versions, scanned daily by kadet-hub.">', page)
        self.assertIn(f"<h2><code>{IMAGE.format('a')}</code></h2>\n\n\n<p>CRITICAL 0, HIGH 1, MEDIUM 0, LOW 1, UNKNOWN 1</p>", page)
        rows = re.findall(r"<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td></tr>", page)
        self.assertEqual(rows, [("CVE-2026-1", "HIGH", "&lt;script&gt;alert(10)&lt;/script&gt;", "1.0", ""),
                                ("CVE-2026-2", "LOW", "zlib", "1.3", "1.3.1"), ("CVE-2026-3", "UNKNOWN", "zlib", "1.3", ""),
                                ("CVE-2026-1", "HIGH", "openssl", "3.0.1", "3.0.2"), ("GHSA-aaaa-bbbb-cccc", "MEDIUM", "golang.org/x/net", "0.1.0", "0.2.0")])
        self.assertIn("Trivy 0.76.1 scanned the images with the vulnerability database of 2026-10-29.", page)
        self.assertNotIn("By tag", page)
        self.assertIn('<p class="warning">Not scanned: MANIFEST_UNKNOWN: manifest[31m unknown</p>', self.page("security", "generators", "failing"))
        self.assertIn("<p>No vulnerabilities found.</p>", self.page("security", "generators", "clean"))
        self.assertIn("<h1>Image security report: cert-manager recipe</h1>", self.page("security", "recipes", "cert-manager"))

    def test_seo(self):  # CAT-11d over the new pages
        p = subprocess.run([sys.executable, SEO_CHECK, self.out], capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_build_reads_the_newest_report(self):  # CAT-39c: the online build with gh, curl, git and oras faked
        shims = {"gh": 'echo "gh $*" >>"$LOG"\n'
                       'case "$1 $2" in\n'
                       '  "run list") printf "30\\n20\\n10\\n";;\n'
                       '  "run download") [[ $3 == 20 ]] || exit 1\n'
                       '    while (($#)); do case $1 in -D) mkdir -p "$2"; cp "$REPORT" "$2/security.json"; shift;; esac; shift; done;;\n'
                       '  *) exit 1;;\n'
                       'esac\n',
                 "curl": 'while (($#)); do case $1 in -o) out=$2; shift;; https://*) url=$1;; esac; shift; done\n'
                         'case $url in\n'
                         '  https://raw.githubusercontent.com/*/recipes/*/*) cp "$RECIPES/inventory/classes/recipes/${url#https://raw.githubusercontent.com/*/recipes/*/}" "$out";;\n'
                         '  *) exit 22;;\n'
                         'esac\n',
                 "git": 'printf "%s\\trefs/heads/main\\n" "$RECIPES_SHA"\n',
                 "oras": "exit 1\n"}
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, "bin"))
            for name, script in shims.items():
                with open(os.path.join(tmp, "bin", name), "w", encoding="utf-8") as f:
                    f.write("#!/usr/bin/env bash\n" + script)
                os.chmod(os.path.join(tmp, "bin", name), 0o755)
            recipes, log, report = os.path.join(tmp, "recipes"), os.path.join(tmp, "gh.log"), os.path.join(tmp, "report.json")
            recipe_classes(os.path.join(recipes, "inventory", "classes"))
            with open(report, "w", encoding="utf-8") as f:
                json.dump(SECURITY, f)
            with open(os.path.join(tmp, "index.json"), "w", encoding="utf-8") as f:
                json.dump({"serial": 1, "generators": {"demo": {"1.10.0": record("b")}}}, f)
            env = dict(os.environ, OWNER=OWNER, PATH=os.path.join(tmp, "bin") + os.pathsep + os.environ["PATH"], LOG=log, RECIPES=recipes,
                       RECIPES_SHA=CHART_RECIPE_SHA, REPORT=report)
            env.pop("CATALOG_OFFLINE", None)
            subprocess.run([os.path.join(HERE, "build"), os.path.join(tmp, "index.json"), os.path.join(tmp, "out")], env=env, check=True, capture_output=True)
            with open(log, encoding="utf-8") as f:
                calls = [c for c in f.read().splitlines() if c.startswith("gh run ")]
            with open(os.path.join(tmp, "out", "security", "generators", "demo", "index.html"), encoding="utf-8") as f:
                self.assertIn("GHSA-aaaa-bbbb-cccc", f.read())
        self.assertEqual(calls[0], f"gh run list -R {OWNER}/registry --workflow scheduled.yml --branch main --limit 7 --json databaseId --jq .[].databaseId")
        self.assertEqual([c.split()[3] for c in calls[1:]], ["30", "20"])  # 30 has no report; 10 is not read
        self.assertIn("-n security-report", calls[2])


class View(unittest.TestCase):
    def test_security_grade(self):  # CAT-39: Artifact Hub's letters
        zero = dict.fromkeys(("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"), 0)
        for counts, letter in ((zero, "A"), (dict(zero, UNKNOWN=3), "-"), (dict(zero, LOW=1, UNKNOWN=3), "B"), (dict(zero, MEDIUM=1, LOW=9), "C"),
                               (dict(zero, HIGH=1, MEDIUM=1), "D"), (dict(zero, CRITICAL=1, HIGH=9), "F")):
            self.assertEqual(grade(counts), letter, counts)

    def test_security_of_the_shown_version(self):  # CAT-39: another version or a malformed entry is no result
        report = {"scanned": "2026-10-29T04:31:07Z", "images": {"r": ["not", "a", "dict"]},
                  "pages": {"generators/a": {"1.0.0": ["r"]}, "generators/b": {"0.9.0": []}, "generators/c": ["x"],
                            "recipes/d": {"main@" + "1" * 40: []}, "recipes/e": {"main@x": []}}}
        found = security(report, [{"name": n, "latest": {"version": "1.0.0"}} for n in "abc"], [{"name": "d", "latest": {"version": "1.0.0"}}])
        self.assertEqual(found["generators"], {"a": {"version": "1.0.0", "failed": 1, "counts": None, "total": None, "grade": None, "count": 1, "tagged": 1,
                                                     "images": [{"ref": "r", "tag": True, "digest": "", "error": "no result", "missing": False,
                                                                 "counts": None, "findings": []}]}})
        self.assertEqual((found["recipes"], found["main"]), ({}, {}))  # d is listed, e names no commit

    def test_image_registry_pages(self):  # CAT-39: Docker Hub, ghcr.io and Quay; other registries and odd names get no link
        digest = "@sha256:" + "a" * 64
        for ref, expected in (
                ("docker.io/louislam/uptime-kuma:2.5.9" + digest, ("docker.io/louislam/uptime-kuma", "https://hub.docker.com/r/louislam/uptime-kuma")),
                ("miniflux/miniflux:2.3.4" + digest, ("miniflux/miniflux", "https://hub.docker.com/r/miniflux/miniflux")),
                ("postgres:18.6" + digest, ("postgres", "https://hub.docker.com/_/postgres")),
                ("docker.io/library/rabbitmq:4.3.6-management", ("docker.io/library/rabbitmq", "https://hub.docker.com/_/rabbitmq")),
                ("ghcr.io/immich-app/immich-server:v3.3.5" + digest, ("ghcr.io/immich-app/immich-server", "https://ghcr.io/immich-app/immich-server")),
                ("quay.io/strimzi/kafka:1.3.0-kafka", ("quay.io/strimzi/kafka", "https://quay.io/repository/strimzi/kafka")),
                ("registry.k8s.io/kube-apiserver:v1.37.1", ("registry.k8s.io/kube-apiserver", None)),
                ("localhost:5000/app:1", ("localhost:5000/app", None)),
                ('ghcr.io/x/"><script>:1', ('ghcr.io/x/"><script>', None))):
            self.assertEqual(registry_page(ref), expected, ref)

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

    def test_schema_sources_in_the_qa7_form(self):  # CAT-29c
        text = ("# QA-7\nkubevirt.io:\n  software: KubeVirt (CDI) / x\n  copyright:\n    - x\n    software: nested\n"
                "core/v1alpha1:\n  software: Talos\r\n  version: 1.14.3\nnone.io:\n  version: 1\n")
        self.assertEqual(schema_sources(text), {"kubevirt.io": "KubeVirt (CDI) / x", "core/v1alpha1": "Talos", "none.io": None})
        for bad in ('"quoted.io":\n  software: X\n', "flow.io: {software: X}\n", "a.io:\n  software: 'X'\n", "a.io:\n  software: X # note\n",
                    "a.io:\n  software: X\u202e\n", "---\na.io:\n  software: X\n"):
            self.assertEqual(schema_sources(text + bad), {}, bad)  # nothing named rather than a name for the wrong group
        self.assertEqual(schema_sources(None), {})

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
    INDEX: ClassVar[dict] = {"serial": 9, "generators": {
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
        self.assertRegex(html, r'<meta property="og:image" content="https://kadet-hub\.org/og/[\w-]+\.png">')  # CAT-58: no tools, the title alone
        self.assertIn('<meta property="og:image:alt" content="kadet-hub.org: Kapitan generator releases, 26 October to 1 November 2026">', html)
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
            seo = subprocess.run([sys.executable, "-I", SEO_CHECK, out], capture_output=True, text=True, check=False)
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



class Schedule(unittest.TestCase):
    def test_two_daily_runs(self):  # CAT-36h
        with open(os.path.join(HERE, "..", ".github", "workflows", "release.yml"), encoding="utf-8") as f:
            crons = re.findall(r'^    - cron: "([^"]+)"', f.read(), re.MULTILINE)
        self.assertEqual(crons, ["17 4 * * *", "47 10 * * *"])


if __name__ == "__main__":
    unittest.main()
