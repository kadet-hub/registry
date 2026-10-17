---
title: "Bitnami Helm alternatives: render manifests yourself"
date: 2026-10-27
topics: [helm, bitnami, generators]
description: Bitnami's free charts and images no longer get updates. Options for PostgreSQL, from the upstream operator chart to a verified generator.
---

If you installed PostgreSQL, Redis or nginx from a Bitnami chart, the
packaged chart you pinned and the images it pulls no longer receive
updates, and the legacy images are meant only to buy time for a migration.
For PostgreSQL the move with the least friction is an operator its own
project maintains, CloudNativePG, together with images from that project.
Its custom resources can come from the upstream `cluster` chart or be
rendered in your own repository, for example with the
[cloudnative-pg](/generators/cloudnative-pg/) generator. Both work. Neither
replaces Bitnami one to one, because a chart or a generator only produces
manifests; the images still need a source you trust.

## What Broadcom changed, and when

Bitnami announced the change in
[bitnami/containers#83267](https://github.com/bitnami/containers/issues/83267),
opened on 16 July 2025 under the title "Upcoming changes to the Bitnami
catalog (effective August 28th, 2025)". The issue states that "since August
28th, we have not published new Bitnami container images or Helm charts to
Docker Hub in OCI format". The deletion of the public catalog
`docker.io/bitnami` was postponed to 29 September 2025, with three 24-hour
brownouts on 28 August, 2 September and 17 September.

Images and charts are affected differently:

- Versioned image tags moved to `docker.io/bitnamilegacy`. That catalog
  "will receive no further updates or support and should only be used for
  temporary migration purposes". Tags based on debian-8, debian-9,
  debian-10, centos-7 and ol-7 were not copied.
- `docker.io/bitnami` keeps a limited set of hardened images that "are
  intended for development and are only available on the 'latest' tag".
  Versioned, supported images are part of the paid Bitnami Secure Images
  offering.
- Packaged charts "will remain available at `docker.io/bitnamicharts` as OCI
  artifacts, but they will no longer receive updates". The FAQ adds that
  deploying them "will not work out-of-the-box unless you override the
  bundled images with valid ones".
- The chart source at [bitnami/charts](https://github.com/bitnami/charts)
  stays available under Apache 2.0.

The documented stopgap is to keep the chart version and point every image
repository at `bitnamilegacy`, for PostgreSQL with
`--set image.repository=bitnamilegacy/postgresql` and the same for
`os-shell` and `postgres-exporter`, plus
`global.security.allowInsecureImages=true`. That keeps a release running. It
does not get you a patched PostgreSQL.

On 24 September 2025 the CNCF
[stated](https://www.cncf.io/blog/2025/09/24/cncfs-helm-project-remains-fully-open-source-and-unaffected-by-recent-vendor-deprecations/)
that "these changes do not impact the Helm project itself" and that
"Bitnami Helm Charts are a specific vendor-maintained implementation". It
advised users to "begin exploring migration or mirroring strategies". Helm
itself stays a CNCF graduated project under Apache 2.0.

## What the PostgreSQL chart looks like today

On 17 October 2026, the source of `bitnami/postgresql` in bitnami/charts is
at chart version 17.1.2, last changed on 8 September 2026. Its default image
is `docker.io/bitnami/postgresql:17.6.0-debian-12-r4`, and that tag does not
resolve. The same tag does resolve in `docker.io/bitnamilegacy`. The OCI
chart `docker.io/bitnamicharts/postgresql:17.1.2` does not exist, while
16.7.0, the version from the announcement's example, still does. The source
keeps moving, but nothing published matches it, so consuming it means
packaging the chart and choosing images yourself.

## The options

| Option | Who maintains the manifests | Images | Cost of staying |
|---|---|---|---|
| Bitnami chart with `bitnamilegacy` | nobody, frozen | frozen, no fixes | grows with every CVE |
| Bitnami Secure Images | Broadcom | Broadcom | subscription |
| Upstream CloudNativePG charts | CloudNativePG project | `ghcr.io/cloudnative-pg/postgresql` | chart values to track |
| Operator plus rendered manifests | you, from a generator | `ghcr.io/cloudnative-pg/postgresql` | an inventory and a compile step |

The last two share the operator. CloudNativePG 1.30.1 was released on 23
September 2026 as `cnpg-1.30.1.yaml` and as the chart `cloudnative-pg`
0.29.1. Moving to it is a platform change, not a chart swap. The Bitnami
chart renders StatefulSets and Services directly; a CloudNativePG `Cluster`
is a resource the operator reconciles into instances, services and
failover. Existing data
moves with a logical import; the operator's
[import documentation](https://github.com/cloudnative-pg/cloudnative-pg/blob/v1.30.1/docs/src/database_import.md)
describes it as `pg_dump` over the network followed by `pg_restore`.

For the `Cluster` itself the upstream project ships a `cluster` chart.
`helm template` of `cluster` 0.9.0 with `instances=3` and
`storage.size=10Gi` produced the Cluster, a ConfigMap of monitoring queries and a `helm test`
Job. The image came out as `ghcr.io/cloudnative-pg/postgresql:16`, because
the chart's `version.postgresql` defaults to `"16"`. If you go this way,
pin `cluster.imageName`.

## Rendering the Cluster with a generator

The other way is to keep the manifests in your repository and render them
from an inventory. The [example](https://github.com/kadet-hub/examples/tree/main/bitnami)
does this with the cloudnative-pg generator 1.0.1, which is built for
CloudNativePG 1.30.1 and the Barman Cloud Plugin 0.15.1 (see
[compatibility](/compatibility/)). The target maps the Bitnami defaults of
one database and one owner onto a three-instance cluster:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/cloudnative-pg:1.0.1@sha256:281417a421b0053070fbdc552f9032a3f8d564c0ca2047ec500842a0d060a8f7
        output_path: lib/cloudnative-pg
    compile:
      - output_path: manifests/
        input_type: kadet
        output_type: yml
        input_paths: [lib/cloudnative-pg]
  namespace: databases
  generators:
    cloudnative-pg:
      clusters:
        app-db:
          image_name: ghcr.io/cloudnative-pg/postgresql:18.6-system-trixie@sha256:5efb66993894055f0aa50bd94337c6c4ff2e2129f4d433c527151aebbf283fb0
          storage: 10Gi
          bootstrap:
            initdb: {database: app, owner: app}
```

The generator fills `instances: 3` and turns `storage: 10Gi` into
`storage.size`. The operator creates the `app` database, the `app` role and
a Secret `app-db-app` with the credentials and a connection URI, which
replaces the password Secret the Bitnami chart rendered.

Kapitan 0.36.3 checks neither digests nor attestations when it fetches, so
`kapitan compile --fetch` gives you no integrity check. It also needs the
`kapitan[oci]` extra for OCI sources; without it the compile stops with
"The 'oras' package is required for OCI dependencies". The example
therefore verifies first and fetches itself:

```sh
id=https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
gh attestation verify "oci://ghcr.io/kadet-hub/index@$(oras resolve ghcr.io/kadet-hub/index:latest)" \
  --owner kadet-hub --cert-identity "$id"
gh attestation verify oci://ghcr.io/kadet-hub/cloudnative-pg@sha256:281417a4... \
  --owner kadet-hub --cert-identity "$id"
oras pull -o .oci ghcr.io/kadet-hub/cloudnative-pg@sha256:281417a4...
tar -xf .oci/cloudnative-pg.tar -C lib/cloudnative-pg
uvx --python 3.13 --from 'kapitan[omegaconf,reclass-rs]==0.36.3' \
  --with omegaconf==2.4.0.dev4 kapitan compile --inventory-backend omegaconf
```

Between the two `verify` calls, `run.sh` checks that the attested index
lists that digest as version 1.0.1 and not yanked. The omegaconf pin is not
optional: without it the resolver installed a newer omegaconf and the
compile failed with `cannot import name 'ListMergeMode'`.

The compile produced one file, `compiled/app-db/manifests/databases/app-db-cluster.yml`.
Plain `kubeconform -strict` reports "could not find schema for Cluster",
so the generator's shipped CRD schemas go in as the schema location:

```sh
kubeconform -strict -summary \
  -schema-location 'lib/cloudnative-pg/schemas/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' \
  compiled/
# Summary: 1 resource found in 1 file - Valid: 1, Invalid: 0, Errors: 0, Skipped: 0
```

The schemas are closed, so a value carried over from Bitnami habits fails.
Adding `replicaCount: 2` under `spec` gives
"additional properties 'replicaCount' not allowed". A schema check is not
the operator's admission webhook; [Checking custom resources against their
CRDs](/guides/checking-custom-resources-against-crds/) covers what it
misses.

## Trade-offs

A generator renders manifests, not images. In this example the images come
from the CloudNativePG project, pinned by digest, and patching them is now
your job: bump the digest, recompile, review the diff. Renovate can propose
the generator updates with the
[kadet-hub preset](https://github.com/kadet-hub/renovate-config), but not
the PostgreSQL image inside your inventory.

The generator does not install the operator or the Barman Cloud Plugin, and
it is built for one CloudNativePG line. When you upgrade the operator, pick
a generator version built for it.

Kapitan is one more tool to learn. For a single database the upstream
`cluster` chart with a pinned image is less to set up. Rendering pays off
when the same pattern repeats across clusters and environments, and when
you want the rendered YAML in review instead of in a release. The
[generator, Helm chart or jinja2](/guides/generator-helm-or-jinja2/) guide
compares the inputs.

A local compile runs the generator's Python with your environment and
credentials. The consumer workflow described in
[Kapitan generators as supply-chain artifacts](/blog/kapitan-generators-as-supply-chain-artifacts/)
runs the same compile in a sandbox without network.
