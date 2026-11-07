---
title: "Kubernetes multiple environments with a diff for every promotion"
layout: prose
description: "Kubernetes multiple environments from one Kapitan inventory: dev, stage and prod on two clusters, the compile diff of a promotion, and a CI guard."
lastmod: 2026-11-07
aliases: [/blog/kapitan-multiple-environments/]
---

Most teams run the same app more than once: dev for trying things, stage
for rehearsing the release, prod for users. The three should differ in a
few values, such as the hostname or the number of replicas, and in nothing
else. This guide builds that with one [Kapitan](/glossary/#kapitan)
[inventory](/glossary/#inventory) for three environments on two clusters.
It shows where each value is set, which environments a change reaches,
and a CI check that fails when prod drifts from stage.

The project is
[multi-env](https://github.com/kadet-hub/examples/tree/main/multi-env) in
kadet-hub/examples. Its `check` script compiles the inventory, rolls a
change through the environments in a copy, and deploys all three
environments to two [kind](/glossary/#kind) clusters. CI runs it on every
change and once a week, and every output below comes from it.

## The setup

The app is [miniflux](/recipes/miniflux/), a feed reader with a PostgreSQL
of its own, from the kadet-hub [recipe](/glossary/#recipe) 1.0.0. It runs
miniflux 2.3.4 and PostgreSQL 18.6, rendered by the
[kubernetes](/generators/kubernetes/) generator 1.14.0. dev and stage
share the cluster `multienv-a`, prod runs alone on `multienv-b`. Each
environment is a [target](/glossary/#target), and the targets differ in
these values:

| | dev | stage | prod | set in |
|---|---|---|---|---|
| cluster | multienv-a | multienv-a | multienv-b | cluster class |
| namespace | miniflux-dev | miniflux | miniflux | `common`, dev's target |
| replicas | 1 | 2 | 3 | env class |
| memory limit | 128Mi | 256Mi | 256Mi | `common`, dev's env class |
| hostname | news.dev.example.com | news.stage.example.com | news.example.com | env class |
| storage class | standard | standard | local-retain | cluster class |

The hostnames are under `example.com`, which RFC 2606 reserves for
examples. `local-retain` stands in for the storage class of a prod
cluster. It keeps a volume when its claim is deleted, where kind's
`standard` deletes it.

## Three classes per target {#classes}

Each target names three [classes](/glossary/#class): `common`, then its
environment, then its cluster. Kapitan merges them in that order, so an
environment overrides `common`, and a cluster overrides both. The target
`prod`, complete:

```yaml
classes:
  - common
  - env.prod
  - cluster.b
parameters:
  kapitan:
    vars:
      target: prod
```

`common` holds what every environment runs. Its values are prod's, so
the env classes for stage and prod have little to say:

```yaml
classes:
  - recipes.miniflux
parameters:
  namespace: miniflux
  applications:
    miniflux:
      database:
        password: ?{base64:${kapitan.vars.target}/database-password||random:str:32}
      admin:
        password: ?{base64:${kapitan.vars.target}/admin-password||random:str:32}
  components:
    miniflux:
      resources:
        requests:
          cpu: 100m
          memory: 128Mi
        limits:
          memory: 256Mi
      env:
        BASE_URL: https://${hostname}/
      # Not in the recipe. Ready once the HTTP server runs, after the migrations.
      healthcheck:
        readiness:
          type: http
          port: http
          path: /healthcheck
    miniflux-db:
      volume_claims:
        miniflux-db:
          spec:
            storageClassName: ${cluster.storage_class}
```

The passwords are [refs](/glossary/#ref) whose path holds the target's
name, so each environment gets its own random password on the first
compile. `BASE_URL` and the storage class are built by
[interpolation](/glossary/#interpolation) from facts that the env and
cluster classes set. Those classes do not need to know where miniflux
reads them. The readiness probe is not in the recipe, and the
[deploy](#deploy) shows why it is needed. `inventory/classes/env/stage.yml`:

```yaml
parameters:
  hostname: news.stage.example.com
  components:
    miniflux:
      replicas: 2
```

`env/dev.yml` also sets smaller resources. A cluster class holds the
cluster's name and storage class, `inventory/classes/cluster/b.yml`:

```yaml
parameters:
  cluster:
    name: multienv-b
    storage_class: local-retain
```

dev and stage would both land in the namespace `miniflux` on
`multienv-a`. That is the one thing the target `dev` overrides, next to
its name:

```yaml
classes:
  - common
  - env.dev
  - cluster.a
parameters:
  # dev shares cluster a with stage.
  namespace: miniflux-dev
  kapitan:
    vars:
      target: dev
```

One `kapitan compile` writes all three targets, into `compiled/dev`,
`compiled/stage` and `compiled/prod`, six files each.

## A change on its way to prod {#promotion}

`METRICS_COLLECTOR: 1` turns on miniflux's `/metrics` endpoint for
Prometheus. `check` rolls that setting through the environments in a copy of the
project. After each step it compiles without `--reveal` and compares
`compiled/` with the step before, using `diff -r`. First the setting goes
into `env/dev.yml`:

```console
EX-28a: METRICS_COLLECTOR in env/dev.yml changes dev
diff -r before/dev/manifests/miniflux-dev/miniflux-deploy.yml work/compiled/dev/manifests/miniflux-dev/miniflux-deploy.yml
45a46,47
>             - name: METRICS_COLLECTOR
>               value: '1'
```

Only dev's Deployment changed. Promoting it means adding the same two
lines to `env/stage.yml`, which changes stage alone, and then to
`env/prod.yml`, which changes prod alone. `check` fails when a step
changes another target than the one expected.

Once all three env classes carry the setting, it belongs in `common`.
`check` removes it from the env classes and adds it under `env` in
`common.yml`:

```console
EX-28a: METRICS_COLLECTOR moved from the env classes to common.yml changes no target
```

An empty diff shows that the move changed nothing that gets deployed.
That holds for any reshuffle of the inventory: compile before and after,
and `diff -r` either prints nothing or the change.

`check` runs `diff -r` because it compiles locally. In a pull request,
the registry's
[compile-diff actions](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#compile-diff-in-pull-requests)
compile the base and the merge commit and post the difference per target
as a comment. This example does not use them.

## The guard {#guard}

Stage is only worth its cost if it runs what prod will run. The values
that may differ between the two are known in advance: replicas follow the
load, the hostname follows the environment, the storage class follows the
cluster. Everything else differing is a mistake, or a promotion that
stopped halfway.

`guard` is a Python script of 85 lines that checks this on compiled
output. It reads every object of two directories, matches them by kind
and name, and compares them field by field. Every field that differs
must appear in `guard-allowed.txt`, which here lists three:

```text
Deployment/miniflux spec.replicas
Deployment/miniflux spec.template.spec.containers[miniflux].env[BASE_URL].value
StatefulSet/miniflux-db spec.volumeClaimTemplates[miniflux-db].spec.storageClassName
```

A list item is addressed by its name when the names in its list are
unique, so reordered environment variables do not count as a change. Ref tokens count as equal, since every target has refs of
its own. On the compiled output of stage and prod:

```console
allowed: Deployment/miniflux spec.replicas: 2 in stage, 3 in prod
allowed: Deployment/miniflux spec.template.spec.containers[miniflux].env[BASE_URL].value: https://news.stage.example.com/ in stage, https://news.example.com/ in prod
allowed: StatefulSet/miniflux-db spec.volumeClaimTemplates[miniflux-db].spec.storageClassName: standard in stage, local-retain in prod
guard: prod differs from stage in 3 allowed field(s) only
```

After the promotion step that adds the metrics setting to stage alone,
the guard exits 1:

```console
NOT ALLOWED: Deployment/miniflux spec.template.spec.containers[miniflux].env[METRICS_COLLECTOR].name: METRICS_COLLECTOR in stage, (absent) in prod
NOT ALLOWED: Deployment/miniflux spec.template.spec.containers[miniflux].env[METRICS_COLLECTOR].value: 1 in stage, (absent) in prod
guard: prod differs from stage in 2 field(s) outside guard-allowed.txt
```

After the step for `env/prod.yml` it passes again. In CI the guard runs
after `kapitan compile`, on the compiled output without `--reveal`:

```sh
python3 guard compiled/stage compiled/prod guard-allowed.txt
```

The guard makes a decision visible that otherwise stays implicit: stage
cannot run ahead of prod in Git. A change to stage outside the allowed
fields reaches prod in the same commit, and the deploy pipeline decides
which of the two gets it first. A team that wants stage ahead for a
while adds the field to `guard-allowed.txt`, and that line shows up in
review.

## On two clusters {#deploy}

`check` creates the kind clusters `multienv-a` and `multienv-b` and
deploys each target to the cluster and namespace that its inventory
names. It reads them with `kapitan inventory --flat`, which prints lines
such as `prod.parameters.cluster.name: multienv-b`. It applies PostgreSQL
first and waits for it, because miniflux exits while it cannot connect.
Then it checks what each environment runs:

```console
EX-28: dev on multienv-a in namespace miniflux-dev: ready replicas 1, memory.max 134217728 (128Mi), API endpoint https://news.dev.example.com/, database claim on standard with reclaim policy Delete
EX-28: stage on multienv-a in namespace miniflux: ready replicas 2, memory.max 268435456 (256Mi), API endpoint https://news.stage.example.com/, database claim on standard with reclaim policy Delete
EX-28: prod on multienv-b in namespace miniflux: ready replicas 3, memory.max 268435456 (256Mi), API endpoint https://news.example.com/, database claim on local-retain with reclaim policy Retain
```

The memory limit is read from `memory.max` in the cgroup of every miniflux
container, which is the limit the kernel enforces. The hostname comes from
miniflux itself. `check` logs in as the admin and reads the Google Reader
API endpoint from the page `/integrations`, which miniflux builds from
`BASE_URL`.

At the end `check` lists how often each miniflux pod restarted. In the
CI run quoted here, one pod of stage restarted once:

```console
  multienv-a miniflux-dev/miniflux-556ccb568f-nt2w2: restart count 0
  multienv-a miniflux/miniflux-55f7b95f65-8nhzr: restart count 0
  multienv-a miniflux/miniflux-55f7b95f65-jwqx4: restart count 1
  multienv-b miniflux/miniflux-bc86d6b65-2dgr4: restart count 0
  multienv-b miniflux/miniflux-bc86d6b65-xdcn2: restart count 0
  multienv-b miniflux/miniflux-bc86d6b65-z5jms: restart count 0
```

In three local runs and three CI runs, at most one pod of stage and one
of prod restarted, at most twice.

miniflux 2.3.4 runs its database migrations without a lock. When two or
three replicas start on an empty database, one of them can fail with an
error such as `pq: column "karakeep_tags" of relation "integrations"
already exists`. It exits, and the kubelet starts it again on the
migrated schema, sometimes after a second collision. dev runs one
replica, so it cannot race. Stage with two replicas runs into the race
that prod's three can, which a stage with one replica would not show.

Without a readiness probe, a pod counts as ready as soon as its container
runs. In one CI run before `common` had the probe, `kubectl rollout
status` returned while a pod was still migrating, that pod then lost the
race, and `check` found 2 of prod's 3 replicas ready. miniflux answers
`/healthcheck` once its HTTP server runs, which is after the migrations.
With the probe on it, `rollout status` waits through the restarts.

## Helm values files and Kustomize overlays {#helm-kustomize}

[Helm vs Kustomize and Kapitan, diffed on one app](/guides/same-app/)
builds dev and prod of the same app with all three tools and compares
the output. The [Helmfile guide](/guides/helmfile-vs-kapitan/#environments)
does the same for environment files. Only what changes with a third
environment and a second cluster is added here.

Helm takes `--values` more than once, and the last file wins, as `helm
template --help` states. `helm template -f common.yaml -f stage.yaml -f
cluster-a.yaml` layers values like the three classes do. The order is in
the command line, not in the values files, and each environment is a
separate `helm template` run.

Kustomize builds an overlay on a base, and an overlay can be the base of
another one.
[Components](https://github.com/kubernetes-sigs/kustomize/blob/kustomize/v5.8.1/examples/components.md),
`kind: Component`, add a block such as a cluster's settings to several
overlays. An overlay per environment, with a component per cluster,
covers this setup. Kustomize has no parameters, so a value built from
another one, such as `BASE_URL` from the hostname, is written out in each
overlay or copied with `replacements`, as the same-app guide shows.

None of the three tools compares environments. A check like the guard
needs each environment's rendered objects in a directory of its own.
Kapitan writes that layout with every compile. With Helm or Kustomize,
the pipeline renders each environment first, which this example does not
test.

## What it does not show

The hostnames reach miniflux and nothing else. kind runs no Ingress or
Gateway controller, so no request arrives by hostname. `local-retain` is
checked on the volume, but no claim is deleted to see the volume stay.
The metrics setting is compiled and never deployed. The deploys are
`kubectl apply`. An Argo CD Application per target, with its destination
from the cluster class, is what a GitOps setup would add.

## Running it

You need kind, kubectl, oras, uv, jq, curl, Docker, and `gh` logged in:

```console
$ git clone https://github.com/kadet-hub/examples
$ cd examples/multi-env
$ ./check
```

`check` verifies the recipe and the generator against kadet-hub's signed
[index](/glossary/#index) and their [attestations](/glossary/#attestation)
before it pulls them by [digest](/glossary/#digest), and does not use
`kapitan compile --fetch`. The
[supply-chain guide](/guides/supply-chain-security-for-kapitan-generators/)
explains why.
