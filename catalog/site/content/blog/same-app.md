---
title: The same app in Helm, Kustomize and Kapitan
date: 2026-11-03
topics: [kapitan, helm, kustomize, comparison]
description: One app, two environments, three tools, matching manifests. Where Kapitan saves work and where Helm and Kustomize stay ahead, checked by a script.
---

Comparisons between Helm, Kustomize and Kapitan usually compare features.
This one compares output. The
[example](https://github.com/kadet-hub/examples/tree/main/same-app) renders
the same small app with all three tools, and `./check` fails unless the
manifests match for each environment. Every number below comes from that
directory.

## The app

Two services in namespace `shop`: `web` and `api`. Each has a Deployment, a
ClusterIP Service and a ConfigMap mounted into the pod. Pods run with the
restricted Pod Security profile. The environments differ in these values:

| | dev | prod |
|---|---|---|
| web image tag | 1.5.0-rc.1 | 1.4.2 |
| web replicas, requests | 1, 50m/64Mi | 3, 250m/256Mi |
| api image tag | 2.0.0-rc.3 | 1.9.1 |
| api replicas, requests | 1, 50m/64Mi | 2, 500m/512Mi |
| log level | debug | info |
| PodDisruptionBudget | none | web and api |

The api reads the web URL from its ConfigMap, `web_url:
http://web.shop.svc:80`. That value matters later.

The Helm side is one generic chart rendered once per app with a base and an
environment values file. The Kustomize side is a base per app and an overlay
per environment. The Kapitan side is an inventory that feeds the
[kubernetes generator](/generators/kubernetes/) from kadet-hub, pinned by
digest:

```yaml
dependencies:
  - type: oci
    source: ghcr.io/kadet-hub/kubernetes:1.2.0@sha256:52017626e77dd5bf7293ce465ff0c3dc7a61dae1ae8353a56a53ffebe1bfb67c
    output_path: lib/kubernetes
```

`check` normalizes all three outputs (one document per object, sorted, keys
sorted) and diffs them. It drops one label, `app.kubernetes.io/managed-by`,
because it names the tool. Everything else must match.

```console
$ ./check
dev: helm = kapitan (6 objects)
dev: kustomize = kapitan (6 objects)
prod: helm = kapitan (8 objects)
prod: kustomize = kapitan (8 objects)
```

## One app

I built `web` alone first and counted the files and lines each tool needs,
excluding rendered output and the fetched generator:

| | files | lines |
|---|---|---|
| Helm | 9 | 131 |
| Kustomize | 9 | 152 |
| Kapitan | 5 | 65 |

The numbers need context. The generator sets fields explicitly that
Kubernetes would default anyway: the rolling update strategy, every probe
threshold, `defaultMode: 420`, `sessionAffinity: None`. The Helm templates
and the Kustomize base spell them out so the output matches. A chart written
from scratch would be shorter.

The bigger point is who owns the template. Of Helm's 131 lines, 108 are the
chart. You write and maintain it. Kapitan's 65 lines are inventory only. The
templating lives in the generator, 4166 lines of Python that someone else
maintains and that you pin, verify and run. It is the same trade as pulling a
generic chart from a chart repository, with the difference that the generator
reads the whole inventory instead of one values tree.

The one-app prod target in Kapitan, `inventory/targets/prod.yml`:

```yaml
classes: [common, apps.web]
parameters:
  web_tag: 1.4.2
  log_level: info
  components:
    web:
      replicas: 3
      resources:
        requests: {cpu: 250m, memory: 256Mi}
        limits: {memory: 512Mi}
      pdb_min_available: 2
```

## Adding a second app

Then I added `api` with the same pattern and diffed against the one-app
version:

| | files changed | lines added | lines removed |
|---|---|---|---|
| Helm | 3 | 25 | 0 |
| Kustomize | 9 | 149 | 2 |
| Kapitan | 5 | 47 | 2 |

Helm wins this round. The chart is generic, so a new app is three values
files. Kapitan's 47 lines include 9 for the JSON output described below; the
api itself is 38 lines, mostly the component block in
`classes/apps/api.yml`. Kustomize has no parameters, so the usual move is
copying the base and renaming. You can share one base through `namePrefix`
and replacements, but labels, selectors, container names and mount paths
then become patches of their own.

## A value derived from another

The api needs the web Service URL. In Kapitan it is an interpolation, so it
follows the web definition:

```yaml
web_url:
  value: http://web.${namespace}.svc:${components:web:ports:http:service_port}
```

Helm releases cannot read each other's values, so the Helm side repeats the
literal. The Kustomize side does too:

```console
$ grep -rn web_url helm kustomize kapitan/inventory
helm/values/api-prod.yaml:6:  web_url: http://web.shop.svc:80
helm/values/api-dev.yaml:6:  web_url: http://web.shop.svc:80
kustomize/overlays/prod/api.yaml:7:  web_url: http://web.shop.svc:80
kustomize/overlays/dev/api.yaml:7:  web_url: http://web.shop.svc:80
kapitan/inventory/classes/apps/api.yml:20:            web_url:
```

To show what that costs, I changed only the web Service port to 8081 in each
tool, in a copy of the example, and ran `check`:

```console
--- /tmp/tmp.TpmPDYldGS/prod.kapitan
+++ /tmp/tmp.TpmPDYldGS/prod.helm
@@ -1,7 +1,7 @@
 apiVersion: v1
 data:
   log_level: info
-  web_url: http://web.shop.svc:8081
+  web_url: http://web.shop.svc:80
```

The same diff appears for Kustomize and for dev, four mismatches in total,
and `check` exits 1. Kapitan followed the change. In Helm and Kustomize the
stale URL renders without an error.

Both tools have a workaround. An umbrella chart with `global` values can
share an input between subcharts, but you restructure the values around it.
Kustomize `replacements` can copy the Service port into part of the string
with `delimiter: ":"` and `index: 2`. I tested that in a copy of the prod
overlay: six lines, and the URL followed. It works per overlay and per field,
and it breaks when the string format changes. The example keeps the
literal.

## Output that is not Kubernetes

The same inventory also renders `endpoints.json` per environment, through a
six-line jinja2 template and a three-line compile entry:

```json
{
"api": {"url": "http://api.shop.svc:80", "image": "ghcr.io/example/api:1.9.1"},
"web": {"url": "http://web.shop.svc:80", "image": "ghcr.io/example/web:1.4.2"}
}
```

That file can feed smoke tests, monitoring or docs. With the port change above
it says 8081 as well. Helm and Kustomize render Kubernetes objects only. The
equivalent there is a separate script that parses values files or rendered
YAML, and it is one more place to keep in sync. The same mechanism covers
Terraform: kadet-hub lists generators for AWS, AzureRM, Google Cloud and Open
Telekom Cloud that read the same inventory.

## What Helm and Kustomize do better

Helm's ecosystem is the main reason to stay. Most vendors publish a chart,
Artifact Hub makes them searchable, and `helm install`, `upgrade` and `rollback`
keep release history in the cluster. Kapitan has no release concept. It
writes files, and you apply them with `kubectl`, Argo CD or Flux. For
third-party software, a vendor chart maintained by the vendor beats a
generator maintained by someone else. Kapitan can render charts through its
`helm` input type, so you do not have to give them up.

Kustomize ships inside `kubectl`. In this example `kubectl kustomize` and the
standalone binary produced identical output. Nothing to install, and patching
vendor YAML you do not control is where Kustomize is strongest. Kapitan has a
`kustomize` input type for that case too.

Both have a gentler start. A values file and a patch are plain YAML.
Kapitan asks you to learn classes, targets, interpolation and the generator's
schema before the first manifest, and it needs a Python toolchain. Argo CD and Flux render Helm and Kustomize natively. With Kapitan you
commit compiled output or add a compile step in CI.

## Fetching generators honestly

Kapitan 0.36.3 checks neither attestations nor digests when it fetches
dependencies, so `kapitan compile --fetch` gives no integrity check. It also
runs generator code with your environment and credentials. `check` does not
use `--fetch`. On first run it verifies the generator's attestation with
`gh attestation verify` against the kadet-hub release workflow, pulls by
digest with `oras` and unpacks into `kapitan/lib/kubernetes`.

That is not the full consumer flow. It does not check the attested index
for yanked versions, and it compiles on your machine without a sandbox. In
CI, use the [consumer
workflow](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#workflow),
which does both and compiles in gVisor without network. The
[supply-chain guide](/guides/supply-chain-security-for-kapitan-generators/)
explains why.

## Running it

You need helm, kustomize and uv, plus oras and a logged-in gh for the first fetch:

```console
$ git clone https://github.com/kadet-hub/examples
$ cd examples/same-app
$ ./check
```

`check` runs Kapitan through `uv run` with
`kapitan[omegaconf,reclass-rs]==0.36.3`, the version the kadet-hub sandbox
pins. Versions and every command behind the numbers above are in `NOTES.md`.

If your stack is one or two apps built from vendor charts, Helm and
Kustomize are the better fit. Kapitan pays off once values start depending
on each other across apps, or the same facts need to reach Kubernetes,
Terraform and docs. To start, see [Generator, Helm chart or
jinja2?](/guides/generator-helm-or-jinja2/) and the
[catalog](/).
