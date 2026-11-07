---
title: "Nextcloud Helm chart: Bitnami subcharts and Kapitan"
date: 2026-11-03
topics: [helm, bitnami, kapitan]
description: "Nextcloud Helm chart and Bitnami: what the 9.4.1 subcharts run today, the chart on your own PostgreSQL and Valkey, and a Kapitan recipe tested on kind."
---

The Nextcloud Helm chart 9.4.1 packages Bitnami's PostgreSQL, MariaDB and
Redis charts as optional subcharts, all switched off by default. Switched
on, they run images from `bitnamilegacy`, a catalog Bitnami no longer
updates. The chart can also use a database and a cache that run outside
it, with credentials from existing Secrets. The
[nextcloud recipe](/recipes/nextcloud/) rebuilds the chart for
[Kapitan](/glossary/#kapitan) and puts a CloudNativePG cluster and Valkey
in place of the subcharts. What Bitnami changed is in the
[Bitnami post](/blog/bitnami/), and the replacements for other charts are
in [Bitnami chart alternatives](/guides/bitnami-chart-alternatives/).

## What chart 9.4.1 declares

With Helm 4.3.1:

```sh
helm show chart oci://ghcr.io/nextcloud/helm/nextcloud --version 9.4.1
```

The output lists four dependencies:

```yaml
dependencies:
- condition: postgresql.enabled
  name: postgresql
  repository: oci://registry-1.docker.io/bitnamicharts
  version: 16.7.4
- condition: mariadb.enabled
  name: mariadb
  repository: oci://registry-1.docker.io/bitnamicharts
  version: 20.5.5
- condition: redis.enabled
  name: redis
  repository: oci://registry-1.docker.io/bitnamicharts
  version: 21.1.3
- alias: collabora
  condition: collabora.enabled
  name: collabora-online
  repository: https://collaboraonline.github.io/online
  version: 1.1.60
```

Three come from Bitnami's `bitnamicharts` repository on Docker Hub. The
fourth is the Collabora Online office server from Collabora's own
repository. The chart's `values.yaml` sets all four conditions to `false`.
A default install keeps Nextcloud's data in SQLite
(`internalDatabase.enabled: true`), which the chart's README does not
recommend for production.

The chart archive carries the three Bitnami charts under `charts/`, so an
install fetches nothing from `bitnamicharts`. Only their images come from
Docker Hub.

## What the subcharts run today

```sh
helm template nextcloud oci://ghcr.io/nextcloud/helm/nextcloud --version 9.4.1 \
  --set internalDatabase.enabled=false \
  --set postgresql.enabled=true --set redis.enabled=true | grep -o 'image: .*' | sort -u
```

```text
image: docker.io/bitnamilegacy/postgresql:17.5.0-debian-12-r3
image: docker.io/bitnamilegacy/redis:8.0.1-debian-12-r1
image: docker.io/library/nextcloud:35.0.2-apache
```

The chart's values replace each subchart's image repository with
`bitnamilegacy/<name>` and keep the subchart's tag. Both tags resolve in
`docker.io/bitnamilegacy`. In `docker.io/bitnami` both returned
`manifest unknown` on 2 November 2026, the registry's answer for a tag it
does not have. The chart's README still names `bitnami/postgresql` and
`bitnami/mariadb` as the defaults, but Helm uses what `values.yaml` says.

The PostgreSQL subchart also comes without storage. The chart's values
set `postgresql.primary.persistence.enabled: false`, and the rendered
StatefulSet mounts the data directory from an `emptyDir`. The database is
gone when the pod is deleted or moves to another node. The values give
MariaDB the same default. The two Redis StatefulSets keep their claims.

## The chart with a database and cache of your own

The chart reads an external PostgreSQL and an external Redis from
existing Secrets. These values use the names that the recipes further down
create:

```yaml
internalDatabase:
  enabled: false
externalDatabase:
  enabled: true
  type: postgresql
  existingSecret:
    enabled: true
    secretName: postgresql-cluster-app
    usernameKey: username
    passwordKey: password
    hostKey: host
    databaseKey: dbname
externalRedis:
  enabled: true
  host: valkey
  existingSecret:
    enabled: true
    secretName: valkey-auth
    passwordKey: default-password
```

`postgresql-cluster-app` is the Secret the CloudNativePG operator writes
for a Cluster named `postgresql-cluster`, with a password it generates.
`valkey` is the Service of the Valkey instance, and `valkey-auth` holds
its password. With these values `helm template` renders a Deployment, a
Service and a Secret with the admin account. A server-side dry run of the
three on kind with Kubernetes 1.37.0 passed. That shows the API server
accepts them, not that Nextcloud installs against the database. The
deploy test of the recipe below covers that part.

## The nextcloud recipe

The [nextcloud recipe](/recipes/nextcloud/) in
[kadet-hub/recipes](https://github.com/kadet-hub/recipes) rebuilds chart
9.4.1 as Kapitan [classes](/glossary/#class) for the
[kubernetes](/generators/kubernetes/) generator 1.9.0. Its version 1.0.1
was published on 27 October 2026. It runs
`docker.io/library/nextcloud:35.0.2-apache`, pinned by digest, as one
replica. The chart's cron sidecar runs the background jobs in the same
pod. One claim holds the config, custom apps and themes, the other the
data directory, 8Gi each by default.

In place of the subcharts the recipe includes two other recipes:

- [postgresql](/recipes/postgresql/), one CloudNativePG `Cluster` with
  PostgreSQL 18.6 and three instances by default. It is rebuilt from
  CloudNativePG's `cluster` chart 0.9.0 and rendered by the
  [cloudnative-pg](/generators/cloudnative-pg/) generator 1.1.0. The
  operator itself comes from the [cnpg](/recipes/cnpg/) recipe, installed
  once per cluster in a target of its own before Nextcloud.
- [valkey](/recipes/valkey/), Valkey 9.1.2 as one instance with ACL
  authentication and a claim, rebuilt from the Valkey project's own chart
  0.12.0. Valkey is the BSD-3-Clause fork of Redis.

The recipe keeps the chart's HTTPRoute. It attaches to a Gateway the
cluster already runs, which owns TLS and the listener. Two rules redirect
`/.well-known/carddav` and `/.well-known/caldav` to `/remote.php/dav`, and
a third sends everything else to the Service on port 8080.

A [target](/glossary/#target) sets the host, the Gateway's name and
namespace, and the admin and Valkey passwords as [refs](/glossary/#ref).
The recipe page has the snippet, the fetch inventory pinned by digest and
the commands that verify and compile it.

Apache in the image starts as root and serves as `www-data`, UID 33. The
namespace therefore needs the Pod Security level `baseline`.

## The deploy test on kind

The kadet-hub/recipes CI runs `check nextcloud --level deploys` from its
[ci workflow](https://github.com/kadet-hub/recipes/blob/main/.github/workflows/ci.yml).
[Run 40481509900](https://github.com/kadet-hub/recipes/actions/runs/40481509900)
on 27 October 2026 checked commit `21d393a`, which the tag
`nextcloud-v1.0.1` points to.

`check` first rendered the chart with the recipe's
[`tests/values.yaml`](https://github.com/kadet-hub/recipes/blob/21d393a220614c2e353c431ae0c3bff4b8485c90/nextcloud/tests/values.yaml)
and compared its six objects with the recipe's: the Deployment, the
Service, the Secret, the HTTPRoute and the two claims. They differ in the
selector, where the recipe uses `name` and the chart
`app.kubernetes.io/name`, `instance` and `component`. They also differ in
defaults the recipe writes out, such as `automountServiceAccountToken: true`.

Then `check` deployed the recipe on kind with `kindest/node:v1.37.0`, after
the CloudNativePG operator and Gateway API. The smoke test waited for the
Cluster and read `status.php` through the Gateway until it reported
`"installed":true`. It wrote a file over WebDAV as the admin and read it
back, which needs the database, the data claim and file locking. Last, it
checked that `occ` reports Redis as the file locking backend. The job
ended with `deploys: passed`.

The test target runs one PostgreSQL instance instead of three. The two DAV
redirects are compared at `renders` only, because cloud-provider-kind,
which serves the Gateway on kind, drops the path of a redirect.

Nextcloud's
[admin manual for version 35](https://docs.nextcloud.com/server/35/admin_manual/configuration_server/caching_configuration.html)
says Valkey is "expected to work" as a Redis-compatible backend. Its
formal tests run Redis through the `redis` PHP extension and Valkey
through Nextcloud's own `keyvalue` cache provider. The Docker image sets
up the `redis` extension, so the recipe runs a pairing the manual expects
to work but does not test. The smoke test above is the only test of that
pairing in the recipe's CI.

## What the recipe leaves out

The recipe's README says: "SMTP, notify_push, an office server,
imaginary, metrics and more than one replica are not part of this
version." The single replica follows from the chart's `Recreate` strategy
and its ReadWriteOnce claims.

The recipe renders no backup. Its README lists what a target backs up:
the database through the Barman Cloud Plugin, which no recipe installs,
and the two claims, with Nextcloud in maintenance mode around both.

Some settings stay with the target. `TRUSTED_PROXIES` has no default, and
without it Nextcloud takes the proxy's address for the client's. PHP accepts
uploads up to `PHP_UPLOAD_LIMIT`, 512M by default. Gateway API has no body
limit of its own, so the Gateway implementation's policy has to allow
that size. The image writes the host into `config.php` at install, so a
later change of the host also needs `occ config:system:set trusted_domains`.

Moving a running Helm release and its data to the recipe is not part of
the recipe and has not been tested.
