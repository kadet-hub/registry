---
title: "Self-hosted Google Photos alternative: Immich on Kubernetes"
date: 2026-11-10
topics: [kapitan, operators, verification]
description: "Immich on Kubernetes with CloudNativePG from four Kapitan recipes: EXIF timeline, offline geocoding, shared albums, smart search and backups, tested on kind."
---

Immich is a photo and video library that you run yourself in place of
Google Photos or iCloud Photos. Its phone apps upload the camera roll in
the background. The server sorts photos into a timeline by the date the
camera wrote, puts them on a map, lets you share albums with other
accounts and finds photos by what they show. Immich's documentation
recommends Docker Compose for installing it. The Compose file runs four
containers: the server, the machine learning service, Valkey for the
job queue, and PostgreSQL from Immich's own image with the vector
extension VectorChord.

This post runs the same four services on Kubernetes from four
[recipes](/glossary/#recipe) that kadet-hub publishes for
[Kapitan](/glossary/#kapitan). PostgreSQL runs as a Cluster of the
CloudNativePG [operator](/glossary/#operator), which creates the
database, its user and its password, and creates the PostgreSQL pod
again when it goes away. The project is
[immich-cnpg](https://github.com/kadet-hub/examples/tree/main/immich-cnpg)
in kadet-hub/examples. Its `check` script deploys it to a new
[kind](/glossary/#kind) cluster on every change and once a week, and
fails when a step below stops working.

## What each recipe brings

A recipe is a directory of Kapitan classes, published as a signed OCI
artifact. All four render with the [kubernetes](/generators/kubernetes/)
generator 1.14.0, and `postgresql` also with the
[cloudnative-pg](/generators/cloudnative-pg/) generator 1.1.0.

- [immich](/recipes/immich/) 1.0.0 runs Immich v3.3.5, rebuilt from
  Immich's Helm chart 0.13.4. It renders two Deployments, the server
  and machine learning on the CPU, and the 10Gi claim `immich-library` for
  the originals, thumbnails and database dumps. It includes the next two
  recipes and points the server at them.
- [postgresql](/recipes/postgresql/) 1.1.0 renders one CloudNativePG
  Cluster with PostgreSQL 18.6. Immich needs two extensions in its
  database, and the recipe has an option for each. `pgvector` stores the
  vectors of smart search and face recognition. `earthdistance` finds
  the nearest place for a GPS position. CloudNativePG's image ships both,
  so `immich` sets `DB_VECTOR_EXTENSION=pgvector` instead of VectorChord.
- [valkey](/recipes/valkey/) 1.0.2 runs Valkey 9.1.2 as one instance with
  a password and an 8Gi claim. Immich queues its background jobs in it:
  metadata extraction, thumbnails, smart search, backups.
- [cnpg](/recipes/cnpg/) 1.0.2 runs the CloudNativePG operator 1.30.1 and
  its CRDs, rebuilt from the project's chart. It runs once per cluster
  and watches every namespace, so it gets a target of its own.

Immich connects as the database owner `app`, which is no superuser. The
two extensions need a superuser, so CloudNativePG creates them when it
creates the Cluster. In the Compose file Immich connects as `postgres`.

## The fetch inventory

Kapitan 0.36.3 reads the [inventory](/glossary/#inventory) before it
fetches dependencies, so a recipe cannot be fetched by the inventory that
uses it. The four recipes are pinned in a separate fetch inventory,
`fetch/targets/recipes.yml`:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/recipes/immich:1.0.0@sha256:7a3d4b118f952edb9606cb176769ebf1a7675a8a76f0a993083ec25c0d183bb6
        output_path: inventory/classes/recipes/immich
      - type: oci
        source: ghcr.io/kadet-hub/recipes/postgresql:1.1.0@sha256:4af1be4c0e95e21fdc5f4029a9509364df93e995be83b8673e15a71dc08abf27
        output_path: inventory/classes/recipes/postgresql
      - type: oci
        source: ghcr.io/kadet-hub/recipes/valkey:1.0.2@sha256:263dfc2e41097c7c6bd016baadcc8384e79afd10910506a892e9994ee7ece918
        output_path: inventory/classes/recipes/valkey
      - type: oci
        source: ghcr.io/kadet-hub/recipes/cnpg:1.0.2@sha256:76038710239a93ead3d44c0162aee4396fa0ab9f96b160b6487d2d437152f4da
        output_path: inventory/classes/recipes/cnpg
```

Version and [digest](/glossary/#digest) come from the signed
[index](/glossary/#index). The digest decides what is pulled. The
index record of `immich` lists the recipes it includes, each at the
digest pinned above:

```sh
jq -c '.recipes["immich"]["1.0.0"].includes[] | [.name, .version]' index.json
```

```text
["postgresql","1.1.0"]
["valkey","1.0.2"]
```

## Verify, then pull by digest

The registry's
[consumer docs](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#verifying-a-recipe-by-hand)
give the steps, and `check` runs them for all four recipes. For
immich:

```sh
id=https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
gh release download --repo kadet-hub/registry --pattern 'index.json*'
gh attestation verify index.json --bundle index.json.sigstore.json --owner kadet-hub --cert-identity "$id"
d=sha256:7a3d4b118f952edb9606cb176769ebf1a7675a8a76f0a993083ec25c0d183bb6
tmp=$(mktemp -d)
gh attestation verify "oci://ghcr.io/kadet-hub/recipes/immich@$d" --owner kadet-hub --cert-identity "$id"
oras pull -o "$tmp" "ghcr.io/kadet-hub/recipes/immich@$d"
mkdir -p inventory/classes/recipes/immich
tar -xf "$tmp/immich.tar" -C inventory/classes/recipes/immich --no-same-owner
```

The first [attestation](/glossary/#attestation) check proves that the
registry's release workflow signed the index. The second proves the same
for the recipe. `check` also requires the index to list `1.0.0` under
`immich` with that digest and `yanked: null`. The recipes pin their two
generators by digest, and `check` verifies and pulls those into `lib/`
the same way. Kapitan then compiles without `--fetch`, which checks
neither digests nor attestations.

## Two targets

`inventory/targets/cnpg.yml` installs the operator and, through the
option `recipes.cnpg.crds`, its CRDs:

```yaml
classes:
  - recipes.cnpg
  - recipes.cnpg.crds
parameters:
  namespace: cnpg-system
  kapitan:
    vars:
      target: cnpg
```

`inventory/targets/immich.yml`:

```yaml
classes:
  - recipes.immich
parameters:
  namespace: immich
  kapitan:
    vars:
      target: immich
  applications:
    valkey:
      password: ?{base64:immich/valkey-password||random:str:40}
    postgresql:
      # One node: further instances on it would share its disk.
      instances: 1
```

The Valkey password is the one value the recipes require. It is a
[ref](/glossary/#ref): the first compile creates a random value of 40
characters under `refs/immich/valkey-password`. The base64 backend only
encodes, so use one that encrypts, such as gpg or Vault, for an install
that matters. The database password needs no ref, because CloudNativePG
generates it into the Secret `postgresql-cluster-app`, from which Immich
reads it.

`instances: 1` replaces the recipe's three PostgreSQL instances. Three
instances protect against a lost node only when they run on three
nodes. On one machine they share its disk. The library claim keeps the
recipe's 10Gi, which `applications.immich.library_storage` changes.

## Compile and deploy

With Kapitan 0.36.3 and its `omegaconf` extra installed as the consumer
docs describe:

```sh
printf 'global:\n  inventory-backend: omegaconf\n' > .kapitan
kapitan compile
kapitan compile --reveal
```

The first compile creates the ref. The second writes its value into the
Secret `valkey-auth`.

```sh
kubectl create namespace cnpg-system
kubectl label namespace cnpg-system pod-security.kubernetes.io/enforce=restricted
kubectl apply --server-side -R -f compiled/cnpg
kubectl -n cnpg-system rollout status deploy/cnpg-cloudnative-pg

kubectl create namespace immich
kubectl label namespace immich pod-security.kubernetes.io/enforce=baseline
kubectl apply --server-side -f compiled/immich/manifests/immich/postgresql-cluster-cluster.yml
kubectl -n immich wait cluster/postgresql-cluster --for=condition=Ready --timeout=600s
kubectl apply --server-side -R -f compiled/immich
```

`--server-side` is needed for the operator's CRDs. A client-side apply
stores the whole object in an annotation, which the API server refuses
above 256 KiB, and the `Cluster` CRD is larger. The operator runs as a
non-root user under the Pod Security level `restricted`. Immich's server
and machine learning images run as root, which only `baseline` admits.

The Cluster goes first. Immich's server exits when PostgreSQL refuses
its connection, and Kubernetes waits longer before each restart. In a
local test run that applied everything at once, the server had
restarted twice before PostgreSQL accepted connections.

## Using it

```sh
kubectl -n immich port-forward service/immich-server 2283:2283
```

Then open `http://localhost:2283`. The first account that signs up
becomes the admin, so sign up before anyone else can reach the server.
The admin creates the other accounts. The phone apps need a URL they
reach from the phone, which a port-forward to your laptop is not.

## What the CI run showed

[Run 41938826188](https://github.com/kadet-hub/examples/actions/runs/41938826188)
of the examples workflow tested commit `f1fbc17` of
[kadet-hub/examples#137](https://github.com/kadet-hub/examples/pull/137)
on 5 November 2026, on GitHub's `ubuntu-24.04` runner. The durations
below are what `check` printed, in whole seconds, or come from the log's
timestamps.

Verifying index serial 108, the four recipes and the two generators and
pulling them took 29 seconds. Installing Kapitan with uv and the two
compiles took 11 more, for 20 files in `compiled/cnpg` and 16 in
`compiled/immich`. kind had the cluster ready 43 seconds later. The
operator was ready 7 seconds after that, the Cluster 36 seconds after
the operator, and Valkey, the server and machine learning 38 seconds
after the Cluster. `check` printed 81 seconds for the deploy, image
pulls included.

`check` then signed up the admin. The server had imported its geodata
into PostgreSQL 10 seconds later. It generated four JPEGs with Pillow,
each filled with one colour, with a time, a UTC offset and a GPS position
in their EXIF data. It uploaded them with the current time as their file
dates, so the dates below can only come from the EXIF data. Three
seconds after the upload Immich had read all four:

```text
eiffel-tower: 2024-07-14T10:12:00.000Z local, UTC+2, Paris 16 Passy, Île-de-France, France
louvre: 2024-07-15T16:40:00.000Z local, UTC+2, Paris 01 Louvre, Île-de-France, France
times-square: 2023-12-31T23:30:00.000Z local, UTC-5, Weehawken, New Jersey, United States
opera-house: 2025-01-26T12:00:00.000Z local, UTC+11, The Rocks, New South Wales, Australia
timeline buckets: {"2025-01":1,"2024-07":2,"2023-12":1}
```

The first value is the time the camera wrote, which Immich keeps as
local time although it ends in `Z`. The second is the offset from the
EXIF data. The New Year's Eve photo from Times Square was taken at 04:30
on 1 January 2024 in UTC. The timeline buckets by local time, so it
sits in December 2023. The last line counts the photos per month.

City, state and country come from the GeoNames data in the server
image, so no request leaves the cluster for them. The server takes the
nearest GeoNames place with 500 or more inhabitants, up to 25 km away.
For Times Square that is Weehawken, across the Hudson in New Jersey. For
the two Paris photos it is the arrondissement. `check` therefore
compares the country and only prints the city.

Next, the admin created a second account. Before anything was shared,
that account got HTTP 400 for the photo of the Eiffel Tower. The admin
then created the album `Paris 2024` with the two Paris photos and added
the second account as viewer. The second account now saw the album, its
two photos and their thumbnails, and still got 400 for the photo from
New York.

Machine learning downloaded its models when the first jobs after the
upload needed them. From Hugging Face came the CLIP model
`ViT-B-32__openai` for smart search, 352 MB for images and 254 MB for
text, and `buffalo_l` for faces, 191 MB. The two OCR models, 22 MB
together, came from ModelScope. 16 seconds after the metadata, a smart
search found all four photos. "a red photo", "a green photo", "a blue
photo" and "a yellow photo" each ranked the photo of that colour first. Machine learning
fetches the models at the `main` revision of their repositories, so
what a new pod downloads can change without a change to the recipe. The
models sit in an `emptyDir`, so every new machine learning pod downloads
them again.

Deleting the server pod cost 14 seconds until the new pod served the
library again. Deleting the PostgreSQL pod took longer. `kubectl delete`
returned after 182 seconds. CloudNativePG's instance manager first shuts
PostgreSQL down in smart mode, which waits for the clients to
disconnect, for up to `smartShutdownTimeout`, 180 seconds by default.
Immich keeps its connections open, so the wait ran out. The operator
created the pod again on the same claim, it was ready 11 seconds later,
and Immich answered at once without a restart. After each deletion the
timeline still held the four photos, one photo still had its country,
an original came back byte for byte and the second account still saw
the album.

## Backing it up

An Immich install holds two things worth keeping. The library claim
`immich-library` holds the originals under `upload/`, the thumbnails and
transcoded videos Immich can create again, and `backups/`. The database
holds everything else: accounts, albums and who they are shared with,
the metadata, and which file belongs to which photo. Immich dumps the
database into `backups/` on the claim every night at 02:00 and keeps the
last 14 dumps, so a copy of the claim holds both. The dump runs as
`pg_dump` with the database owner `app`.

A copy of the claim, through the server pod:

```sh
kubectl -n immich exec deploy/immich-server -c immich-server -- tar -C /data -cf - . > immich-library.tar
```

Between the nightly runs, an admin starts a dump through the API with
`POST /api/jobs` and the body `{"name": "backup-database"}`. A dump
restores into a new, empty database as the superuser `postgres`:

```sh
mkdir library && tar -xf immich-library.tar -C library
primary=$(kubectl -n immich get cluster postgresql-cluster -o jsonpath='{.status.currentPrimary}')
kubectl -n immich exec "$primary" -c postgres -- psql -c 'create database restore_check'
gunzip -c library/backups/<dump>.sql.gz |
  kubectl -n immich exec -i "$primary" -c postgres -- psql -v ON_ERROR_STOP=1 -q -d restore_check
```

In the CI run the job wrote
`immich-db-backup-20261105T003356-v3.3.5-pg18.6.sql.gz`, 19 MB. The name
holds the time, the Immich version and the PostgreSQL version. The copy
of the claim held the four originals byte for byte. The dump, restored
into an empty database, held the four photos' checksums and the album's
viewer. Dump, copy and restore took 17 seconds together.

Immich's own restore is not tested. It replays the dump as `app`, which
may not drop and create the extensions `vector` and `earthdistance`, so
the immich recipe's README expects it to fail. Pointing Immich at a
restored database is not tested either. CloudNativePG's own backups, base
backups with continuous WAL archiving, need an object store such as S3
or a CSI driver with volume snapshots. kind has neither, and the
`postgresql` recipe configures no backup.

## What it leaves out

External access and TLS. Both Services are `ClusterIP`, and the recipe
renders no Ingress or HTTPRoute. The phone apps and other people's
browsers reach Immich only through one, with a certificate for its
host name. Uploads of videos can be large, so a proxy in front of
Immich needs a body size limit that allows them.

GPU and hardware acceleration. Machine learning runs on the CPU image.
Immich also publishes machine learning images for CUDA, OpenVINO, ROCm
and Arm NN, such as `v3.3.5-cuda`, and the recipe's README marks GPU
images and hardware acceleration as not tested. kind has no GPU.

High availability. One PostgreSQL instance, one server, one Valkey, all
on one node. With three instances on three nodes CloudNativePG would
promote a replica when the primary's node fails. That is not tested
here, because kind runs one node.

Backups off the machine. `check` copies the claim to the machine that
runs `kubectl` and deletes the copy at the end. Moving copies to
another machine or an object store on a schedule is not part of the
stack.

The face recognition and OCR jobs run on every upload. `check` does
not test their results.
