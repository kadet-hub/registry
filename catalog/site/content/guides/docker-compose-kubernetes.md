---
title: "Docker Compose and Kubernetes from one Kapitan inventory"
layout: prose
description: "Miniflux and PostgreSQL from one Kapitan inventory, deployed to kind and started with docker compose up, and what does not map between the two."
lastmod: 2026-11-07
aliases: [/blog/docker-compose-kubernetes/]
---

Many self-hosted apps ship a Docker Compose file. Teams that run some of
them on a Docker host and others on Kubernetes end up with a Compose file
and a set of manifests for the same app, with the image, the environment
and the passwords written twice. This guide keeps one
[Kapitan](/glossary/#kapitan) [inventory](/glossary/#inventory) with two
[targets](/glossary/#target) that include the same
[class](/glossary/#class). One compiles Kubernetes manifests, the other a
Compose file.

The project is
[compose-kubernetes](https://github.com/kadet-hub/examples/tree/main/compose-kubernetes)
in kadet-hub/examples. Its `check` script deploys the first target to a
new [kind](/glossary/#kind) cluster and starts the second with
`docker compose up` on the CI runner, on every change and once a week.
The app is Miniflux, a feed reader, with its PostgreSQL database, from the
[recipe](/glossary/#recipe) [miniflux](/recipes/miniflux/) 1.0.0. That
recipe was migrated from Miniflux's own Compose file, so the guide also
shows how much of that file comes back.

## The shared class {#shared}

`inventory/classes/miniflux.yml` is what both targets include:

```yaml
classes:
  - recipes.miniflux.miniflux
  - recipes.miniflux.db
parameters:
  applications:
    miniflux:
      database:
        user: miniflux
        name: miniflux
        password: ?{base64:miniflux/database-password||random:str:32}
      admin:
        username: admin
        password: ?{base64:miniflux/admin-password||random:str:24}
```

The two classes it includes come with the recipe. They define the
components `miniflux` and `miniflux-db` in the format of the
[kubernetes](/generators/kubernetes/) generator: the images pinned by
[digest](/glossary/#digest), the environment, a readiness probe that runs
`pg_isready` in the database container, and a volume for PostgreSQL's
data. Miniflux reads its database connection from `DATABASE_URL`, which
the recipe builds from the user, the name and the password set here.

The passwords are [refs](/glossary/#ref). On the first compile, the
`random:str` function creates each value from letters, digits, `-` and
`_`. A URL reserves none of them, and the database password ends up in
`DATABASE_URL`. Kapitan stores the values in the refs directory. The
compiled output holds a ref tag such as
`?{base64:miniflux/database-password:86e11e39}` until `--reveal` or
`kapitan refs --reveal` replaces it with the value. The `base64` backend
encrypts nothing. A real project uses `gpg`, a cloud KMS or Vault for the
same refs.

## Two targets {#targets}

The target `cluster` takes the recipe as a whole:

```yaml
classes:
  - recipes.miniflux
  - miniflux
parameters:
  namespace: miniflux
  kapitan:
    vars:
      target: cluster
  generators:
    kubernetes:
      namespaces:
        miniflux:
          labels:
            pod-security.kubernetes.io/enforce: baseline
  components:
    miniflux:
      healthcheck:
        readiness:
          type: http
          port: http
          path: /healthcheck
```

`recipes.miniflux` is the recipe's `init.yml`. It includes the two
component classes again and adds the kubernetes generator's pin and
compile entry. The target adds the namespace, at the Pod Security level
`baseline`, because the postgres image starts as root.

It also adds a readiness probe for Miniflux, which the recipe lacks.
`/healthcheck` answers `OK` once Miniflux reaches its database. Without
the probe, the rollout counted Miniflux as available as soon as the
container started. In the first CI run, `check` then opened a
port-forward to a Miniflux that did not listen yet, and the port-forward
ended at the refused connection. The probe is an HTTP request from the
kubelet, which a Compose health check cannot express, so it belongs in
this target. In the shared class it fails the compile of `compose`.

The target `compose` cannot include `init.yml`, because its compile entry
would run the kubernetes generator in this target as well. Setting
`compile: []` in the target does not remove that entry. In a local compile
with Kapitan 0.36.3 and the omegaconf backend, the generator still ran. So
the target gets the components
through the shared class only. That is also why the shared class sets the
database user and name and the admin's username, the three values
`init.yml` sets too. What the target adds is the compile entry for the
Compose file and what only a Docker host needs:

```yaml
classes:
  - miniflux
parameters:
  kapitan:
    vars:
      target: compose
    compile:
      - input_type: kadet
        input_paths:
          - components/compose
        output_path: .
        output_type: yml
  compose:
    services:
      miniflux:
        ports:
          - 127.0.0.1:8080:8080
        depends_on:
          miniflux-db:
            condition: service_healthy
        restart: unless-stopped
      miniflux-db:
        restart: unless-stopped
```

## From components to a Compose file {#compose}

kadet-hub's [docker](/generators/docker/) generator 1.0.2 renders
Dockerfiles, not Compose files. The Compose file therefore comes from
`components/compose/__init__.py`, a [kadet](/glossary/#kadet) component
of 77 lines in the example. It reads `parameters.components`, the input of
the kubernetes generator, and maps the keys the recipe uses:

| Component key | Compose |
|---|---|
| `image` | `image` |
| `env`, plain value | `environment`, as a string |
| `env` with `secretKeyRef` to the component's Secret | `environment`, with the value from the Secret's `string_data` |
| `healthcheck.readiness` of type `command` | `healthcheck` with `test: [CMD, ...]`, `interval`, `timeout` and `retries` from the probe or the kubelet's defaults |
| `volume_mounts` of a `volume_claims` entry | a named volume, mounted at `mount_path` |
| `application`, `type`, `ports`, `service`, `volume_claims` | dropped |

Any other key fails the compile with `no Compose mapping for` and the key.
This is deliberate. A key that the cluster gets and the Docker host
silently does not is the drift this setup is meant to prevent. After the
mapping, the component merges the target's `compose.services` over the
result.

Compiled without `--reveal`, the target `compose` writes
`compiled/compose/compose.yml`. This is the file from the CI run below:

```yaml
services:
  miniflux:
    depends_on:
      miniflux-db:
        condition: service_healthy
    environment:
      ADMIN_PASSWORD: ?{base64:miniflux/admin-password:80986ca4}
      ADMIN_USERNAME: admin
      CREATE_ADMIN: '1'
      DATABASE_URL: postgres://miniflux:?{base64:miniflux/database-password:474bdc35}@miniflux-db/miniflux?sslmode=disable
      DEBUG: '1'
      RUN_MIGRATIONS: '1'
    image: miniflux/miniflux:2.3.4@sha256:72e49f513a63104506aab98ba8cfc3a409d4fde23550a583dec07ec941f1e94e
    ports:
      - 127.0.0.1:8080:8080
    restart: unless-stopped
  miniflux-db:
    environment:
      POSTGRES_DB: miniflux
      POSTGRES_PASSWORD: ?{base64:miniflux/database-password:474bdc35}
      POSTGRES_USER: miniflux
    healthcheck:
      interval: 10s
      retries: 3
      test:
        - CMD
        - pg_isready
        - -U
        - miniflux
      timeout: 30s
    image: postgres:18.6@sha256:edb0c08dc33befd0262ab3b5cf1c4f3f8cfd8b09e88c05b45adee29d6761ddb6
    restart: unless-stopped
    volumes:
      - miniflux-db:/var/lib/postgresql
volumes:
  miniflux-db: {}
```

## One image, both outputs {#image}

To move Miniflux to another release before the recipe does, the shared
class sets the image of the component:

```yaml
  components:
    miniflux:
      image: miniflux/miniflux:2.3.5
```

`check` does this in a copy of the inventory, with the recipe's image and
the next patch version, compiles both targets with and without the change,
and fails unless the image line of the Deployment and of `compose.yml`
changed and nothing else. It only compiles that version, so it leaves out
the digest. The diff from the CI run:

```diff
diff -ru before/compiled/cluster/manifests/miniflux/miniflux-deploy.yml after/compiled/cluster/manifests/miniflux/miniflux-deploy.yml
--- before/compiled/cluster/manifests/miniflux/miniflux-deploy.yml
+++ after/compiled/cluster/manifests/miniflux/miniflux-deploy.yml
@@ -41,7 +41,7 @@
                   name: miniflux
             - name: DEBUG
               value: '1'
-          image: miniflux/miniflux:2.3.4@sha256:72e49f513a63104506aab98ba8cfc3a409d4fde23550a583dec07ec941f1e94e
+          image: miniflux/miniflux:2.3.5
           imagePullPolicy: IfNotPresent
           name: miniflux
           ports:
diff -ru before/compiled/compose/compose.yml after/compiled/compose/compose.yml
--- before/compiled/compose/compose.yml
+++ after/compiled/compose/compose.yml
@@ -10,7 +10,7 @@
       DATABASE_URL: postgres://miniflux:?{base64:miniflux/database-password:474bdc35}@miniflux-db/miniflux?sslmode=disable
       DEBUG: '1'
       RUN_MIGRATIONS: '1'
-    image: miniflux/miniflux:2.3.4@sha256:72e49f513a63104506aab98ba8cfc3a409d4fde23550a583dec07ec941f1e94e
+    image: miniflux/miniflux:2.3.5
     ports:
       - 127.0.0.1:8080:8080
     restart: unless-stopped
```

Both compiles run without `--reveal`, so the diff holds ref tags and no
password.

## Deployed both ways {#deploy}

On kind, `check` applies the revealed output of the target `cluster`:

```sh
kapitan compile -t cluster --reveal
kubectl apply -f compiled/cluster/manifests/miniflux-namespace.yml
kubectl apply -R -f compiled/cluster/manifests -l name=miniflux-db
kubectl -n miniflux rollout status statefulset/miniflux-db
kubectl apply -R -f compiled/cluster/manifests
```

The Namespace goes first, because `kubectl apply -R` reads the directory
`miniflux/` before the file `miniflux-namespace.yml` next to it. The
database goes next, selected by the `name` label the generator puts on
every object, and `check` waits for its rollout. That step stands in for
the `depends_on` of the Compose file, which has no counterpart in
Kubernetes. Miniflux exits while PostgreSQL refuses connections, and the
kubelet restarts it with growing delays. In a local run with everything
applied at once, Miniflux sat in `CrashLoopBackOff` when `check` stopped
on it.

On the Docker host, no file has to hold the passwords. `check` compiles
the target `compose` without `--reveal` and reveals into the standard
input of `docker compose`:

```sh
kapitan refs --reveal -f compiled/compose/compose.yml |
  docker compose -p miniflux -f - up -d --wait
```

`--wait` returns once PostgreSQL reports healthy and Miniflux runs. The
values still end up in the containers' environment, where
`docker inspect` shows them.

On both runtimes `check` then runs the same steps against Miniflux's port,
through a port-forward to the Service on kind and through the published
port under Compose. `/healthcheck` must answer `OK`. Logged in as the
admin with the password from the ref, `/v1/version` must report the
recipe's tag, and a category created through `/v1/categories` must come
back in the list. A category is a row in PostgreSQL, so the last step
shows that Miniflux reached its database with the password from the other
ref.

## What the CI run showed {#ci}

[Run 42006701130](https://github.com/kadet-hub/examples/actions/runs/42006701130)
of the examples workflow tested commit `6991df2` of
[kadet-hub/examples#147](https://github.com/kadet-hub/examples/pull/147)
on 5 November 2026, on GitHub's `ubuntu-24.04` runner, with docker compose
v5.7.0 and the kind node image `kindest/node:v1.37.0`. The durations below
come from the log's timestamps or are what `check` printed, in whole
seconds.

Verifying the index, the recipe and the generator and pulling them took
12 seconds. All compiles, the changed image and the refused
`security_profile` included, were done 29 seconds after `check` started.
kind had the cluster ready 37 seconds later. The database, then Miniflux,
were rolled out 23 seconds after the first `kubectl apply`. Under Compose,
the step from `kapitan refs --reveal` to a running Miniflux took 18
seconds, image pulls included. The end of the log, without Compose's pull
progress:

```console
deployed to kind in 23s
EX-30: Miniflux 2.3.4 on kind answers /healthcheck, stored and listed category 2
Docker Compose version v5.7.0
started with docker compose in 18s
miniflux miniflux/miniflux:2.3.4@sha256:72e49f513a63104506aab98ba8cfc3a409d4fde23550a583dec07ec941f1e94e Up Less than a second
miniflux-db postgres:18.6@sha256:edb0c08dc33befd0262ab3b5cf1c4f3f8cfd8b09e88c05b45adee29d6761ddb6 Up 11 seconds (healthy)
EX-30: Miniflux 2.3.4 on compose answers /healthcheck, stored and listed category 2
compose-kubernetes: passed in 111s
```

On both runtimes the new category got the ID 2. Miniflux creates the
category `All` for a new user, and each runtime started with an empty
database.

## How much of Miniflux's Compose file comes back {#round-trip}

The recipe was migrated from
[`contrib/docker-compose/basic.yml`](https://github.com/miniflux/v2/blob/238c5614e584ebc87894e7d9f10bc91373a0b2c2/contrib/docker-compose/basic.yml)
of Miniflux 2.3.4. Compiled back, the file differs in these places:

| Miniflux's file | Target `compose` |
|---|---|
| service `db`, `container_name: postgres` | service `miniflux-db`, container named by Compose; the recipe renames the service and drops `container_name` |
| `miniflux/miniflux:latest`, `postgres:latest` | `2.3.4` and `18.6`, both pinned by digest in the recipe |
| passwords `secret` and `test123` | refs with random values |
| `ports: ["80:8080"]` | `127.0.0.1:8080:8080`, from the target |
| `restart: always` | `restart: unless-stopped`, from the target |
| health check every 10s with `start_period: 30s` | every 10s with a timeout of 30s and 3 retries; the recipe drops `start_period` |

`depends_on` with `condition: service_healthy` comes back from the target.
The environment of both services and the volume come back from the
recipe's components with the same names, and with the same values apart
from the passwords and the host name `miniflux-db` in `DATABASE_URL`.

## What does not map {#gaps}

Some of what the cluster gets has no counterpart on a Docker host. Apart
from the refusal of `security_profile`, `check` does not test these
differences.

### The Service {#service}

On kind, the Service `miniflux` listens on port 80 and forwards to the
container's 8080. Compose has no Service. Services reach each other by
service name on the container port, as
[Docker's documentation](https://docs.docker.com/compose/how-tos/networking/)
describes. `DATABASE_URL` names the host `miniflux-db` and no port, so the
same URL works on both runtimes. A client of Miniflux uses port 80 in the
cluster and 8080 on the Docker host.

### Probes {#probes}

The component turns the readiness probe of `miniflux-db` into a Compose
health check with the same command. On Kubernetes the probe decides
whether the pod gets traffic through the Service. Under Compose the status
feeds `depends_on` and `docker compose ps`. A liveness probe restarts a
container that still runs, while Docker's restart policies act on a
container that stops
([Docker's documentation](https://docs.docker.com/engine/containers/start-containers-automatically/)).
A Docker health check runs inside the container, so HTTP, TCP and gRPC
probes, which the kubelet runs from outside, need a client in the image.
The component refuses liveness and startup probes and those probe types.
The HTTP probe that the target `cluster` adds for Miniflux is one of them.

### Pod Security {#pod-security}

`security_profile` fills the fields of a Pod Security level in a pod. In
the shared class it fails the compile of `compose`. `check` adds it to a
copy of the class and requires that failure:

```text
EX-30b: the target compose refuses security_profile in the shared class: components.miniflux: no Compose mapping for ['security_profile']
```

Compose has fields for some of the same settings, such as `user`,
`cap_drop` and `security_opt: [no-new-privileges:true]`. Nothing on a
Docker host refuses a container by level, as the Namespace's label
`pod-security.kubernetes.io/enforce: baseline` does in the cluster. A key
that only one runtime has a use for belongs in that runtime's target.

### NetworkPolicy {#networkpolicy}

The recipe renders none. On Compose, every service on the project's
network reaches every port of the others. Separate networks keep services
apart, but have no port rules.

### Secrets {#secrets}

On Kubernetes the passwords sit in Secrets, and the pods' environment
refers to them. Compose's `secrets` are files mounted into the container,
and no environment variable can refer to one. The component writes the
value into `environment`.

### Volume size {#volume-size}

The volume claim asks for 1Gi. A named volume of Docker's `local` driver,
as here, has no size limit.

## Running it

You need kind, kubectl, oras, uv, jq, curl, Docker with the compose
plugin, and `gh` logged in:

```console
$ git clone https://github.com/kadet-hub/examples
$ cd examples/compose-kubernetes
$ ./check
```

`check` verifies the recipe and the kubernetes generator against
kadet-hub's signed [index](/glossary/#index) and their
[attestations](/glossary/#attestation) before it pulls them by digest, and
does not use `kapitan compile --fetch`. The
[Pi-hole post](/blog/pihole-powerdns-kubernetes/#verify-then-pull-by-digest)
shows the commands.
