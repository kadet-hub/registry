---
title: "kindest/node images: picking the version for your kind release"
date: 2026-11-06
topics: [ci, testing, supply chain]
description: "A kindest/node image belongs to the kind release that built it. Where to find its digest, how to pin it, and a CI matrix that follows kind's releases."
---

A `kindest/node` image is the container image that kind runs as a
Kubernetes node. Its tag names the Kubernetes version inside, such as
`v1.37.0`. The tag does not name the kind release that built the image, and
kind supports an image only with that release. The release notes list the
images of each release with their digests. The tag on Docker Hub can point
to a build for another release.

Everything below was checked on 2026-11-03 against kind v0.33.0, the latest
release on that day, its release notes and Docker Hub. The cluster further
down ran on Docker 29.9.2.

## Which image belongs to your kind release

`kind version` prints the release. kind's quick start sends you to the notes
of that release to find images suitable for it
([Creating a Cluster](https://kind.sigs.k8s.io/docs/user/quick-start/#creating-a-cluster)).
The [notes of v0.33.0](https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0)
list four:

    v1.37.0: kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5
    v1.36.4: kindest/node:v1.36.4@sha256:099e049362a1526b2db71494e1947aae99bd16290d7c895f2b7ea312e3cbfaed
    v1.35.8: kindest/node:v1.35.8@sha256:07b2536e30b803ed61d1677a79df6115f798ce64c80f9e22f6ed45afd09323c0
    v1.34.11: kindest/node:v1.34.11@sha256:44e222ee2132dab25ff87301682f89eb82c7880ea3a1bf543bfe9708fd08d67d

The part after `@` is the [digest](/glossary/#digest) of an OCI image index,
the list that points to the amd64 and the arm64 image. v1.37.0 is the
default node image of v0.33.0. Below the list the notes say:

> **NOTE**: You *must* use the `@sha256` digest to guarantee an image built for this release, until such a time as we switch to a different tagging scheme.

kind's design page on the node image says what is supported: "node images
will create a working Kubernetes node at the advertised version with the
kind version they were released with (and best effort with other releases)"
([Node Image](https://kind.sigs.k8s.io/docs/design/node-image/)).

## Why the tag is not enough

The tag carries only the Kubernetes version, and several kind releases can
build the same one. `v1.26.15` is listed in the notes of v0.23.0, v0.24.0
and v0.25.0, each time with another digest:

    v0.23.0: kindest/node:v1.26.15@sha256:84333e26cae1d70361bb7339efb568df1871419f2019c80f9a12b7e2d485fe19
    v0.24.0: kindest/node:v1.26.15@sha256:1cc15d7b1edd2126ef051e359bf864f37bbcf1568e61be4d2ed1df7a3e87b354
    v0.25.0: kindest/node:v1.26.15@sha256:c79602a44b4056d7e48dc20f7504350f1e87530fe953428b792def00bc1076dd

The tag on Docker Hub resolves to the last of them:

    $ skopeo inspect --raw docker://docker.io/kindest/node:v1.26.15 | sha256sum
    c79602a44b4056d7e48dc20f7504350f1e87530fe953428b792def00bc1076dd  -

Docker Hub reports the tag as last pushed on 8 November 2024, the day of
v0.25.0. kind v0.23.0, given `kindest/node:v1.26.15` without a digest, pulls
the image built for v0.25.0.

A tag can also point to an image built ahead of the kind release that
supports it. In January 2025, a CI that picked the newest kind and
`kindest/node` versions got a `kindest/node:v1.32.1` built with containerd 2.
The cluster came up, and `kind load docker-image` failed with
`ERROR: failed to detect containerd snapshotter`. The report names kind
v0.26.0 with that image
([kubernetes-sigs/kind#3853](https://github.com/kubernetes-sigs/kind/issues/3853)).
A kind maintainer answered in the issue:

> You should scrape the release notes instead of the docker hub tags.

kind v0.27.0 followed in February 2025. Its notes say that "kind v0.27.0+
will be required to use `kind load ...` subcommands with these new
containerd 2.0+ images (built by kind v0.27+)". The notes of v0.32.0 say
the same for the next containerd upgrade and add that full compatibility of
node images between kind releases is not guaranteed. Older notes carry
similar constraints. On cgroup v1 hosts, kind v0.20.0 needs images built
with v0.20.0 or later. Kubernetes 1.24 images and later need kind v0.13.0 or
later.

## Pinning the image

On the command line, the reference with tag and digest goes to `--image`:

    kind create cluster --image kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5

In a config file the image is set per node, with the digest as well
([Setting Kubernetes version](https://kind.sigs.k8s.io/docs/user/quick-start/#setting-kubernetes-version)):

    kind: Cluster
    apiVersion: kind.x-k8s.io/v1alpha4
    nodes:
    - role: control-plane
      image: kindest/node:v1.35.8@sha256:07b2536e30b803ed61d1677a79df6115f798ce64c80f9e22f6ed45afd09323c0
    - role: worker
      image: kindest/node:v1.35.8@sha256:07b2536e30b803ed61d1677a79df6115f798ce64c80f9e22f6ed45afd09323c0

`--image` overrides the image of every node in the config file
([create.go](https://github.com/kubernetes-sigs/kind/blob/v0.33.0/pkg/cluster/internal/create/create.go#L227-L235)).

We created a cluster from such a file, with the control plane only, and
added `-v 1` for kind's debug lines:

    $ kind create cluster --name node-image-post --config kind-config.yaml -v 1 --kubeconfig ./kind-post.kubeconfig
    Creating cluster "node-image-post" ...
     • Ensuring node image (kindest/node:v1.35.8) 🖼️  ...
    DEBUG: docker/images.go:67] Pulling image: kindest/node:v1.35.8@sha256:07b2536e30b803ed61d1677a79df6115f798ce64c80f9e22f6ed45afd09323c0 ...
     ✓ Ensuring node image (kindest/node:v1.35.8) 🖼️
    # ... preparing nodes, control plane, CNI and StorageClass

The status line shows the tag only, because kind drops the digest for
display. The pull uses the full reference. The node then reported
Kubernetes v1.35.8 and containerd 2.3.4.

## kind stuck at "Ensuring node image" {#ensuring-node-image-stuck}

With the Docker provider, this step runs `docker inspect --type=image` on the
reference and, when the image is missing, `docker pull`. A failed pull is
retried four times, after pauses of one to four seconds. Then kind stops
with `failed to pull image`
([images.go](https://github.com/kubernetes-sigs/kind/blob/v0.33.0/pkg/cluster/internal/providers/docker/images.go#L35-L81)).
kind shows none of the pull's output and sets no timeout on it.

The pull is large. The amd64 image of v1.37.0, the entry `sha256:1aac8018…`
of the index that the v1.37.0 digest names, has two layers:

    $ skopeo inspect --raw docker://docker.io/kindest/node@sha256:1aac8018c42eb5d48fae5be507caaee789fc6d9b9b3f560359dd4157ac00d4f6 | jq '{mediaType, layers: (.layers | length), compressed_bytes: ([.layers[].size] | add)}'
    {
      "mediaType": "application/vnd.oci.image.manifest.v1+json",
      "layers": 2,
      "compressed_bytes": 388182150
    }

That is 388 MB to download. At 1 MB/s it takes about six and a half
minutes (388 s), all of it on the "Ensuring node image" line with no sign of
progress. `-v 1` prints the "Pulling image" line above and a line per retry.
A kind maintainer points out that the container runtime does the download,
not kind. The suggested workaround is to pull the image yourself first,
since kind does not pull an image that is already present
([kubernetes-sigs/kind#3199](https://github.com/kubernetes-sigs/kind/issues/3199)):

    docker pull kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5

`docker pull` shows the progress of each layer. In CI, the pull as a step of
its own shows its time apart from the cluster creation.

## Three Kubernetes minors in kadet-hub's CI

The kadet-hub/recipes CI checks every [recipe](/glossary/#recipe) on the
three Kubernetes minors upstream supports. The minors, their patch releases
and their node images come from one file, `kubernetes-versions.json` in
kadet-hub/renovate-config. At the tag `kubernetes-versions-2026-11-02` it
reads:

```json
{
  "kind": {
    "version": "v0.33.0",
    "sha256": {
      "linux-amd64": "aee6151561422756b764a4ae28e7f44cda5af5a9eead3cc9985112b1de8d8e0d",
      "linux-arm64": "20022bee6cfcd5086cb7234d218e3454e6090022f2a8f55d1fa7fcf42c3867a2"
    }
  },
  "kubernetes": [
    {
      "minor": "1.37",
      "version": "1.37.0",
      "node_image": "kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5",
      "kubeconform": "1.37.0"
    },
    {
      "minor": "1.36",
      "version": "1.36.4",
      "node_image": "kindest/node:v1.36.4@sha256:099e049362a1526b2db71494e1947aae99bd16290d7c895f2b7ea312e3cbfaed",
      "kubeconform": "1.36.4"
    },
    {
      "minor": "1.35",
      "version": "1.35.8",
      "node_image": "kindest/node:v1.35.8@sha256:07b2536e30b803ed61d1677a79df6115f798ce64c80f9e22f6ed45afd09323c0",
      "kubeconform": "1.35.8"
    }
  ]
}
```

`kind.sha256` holds the SHA-256 of the kind binaries for Linux on amd64 and
arm64. Each `node_image` is the line from the v0.33.0 notes. `kubeconform`
is the Kubernetes version the schema check validates against.

A workflow in renovate-config recomputes the file every day from three
sources
([spec](https://github.com/kadet-hub/renovate-config/blob/main/docs/specs/kubernetes-versions.md)).
`https://dl.k8s.io/release/stable.txt` names the newest stable Kubernetes
release, v1.37.2 on 3 November 2026. The body of kind's latest GitHub release
supplies the node images and their digests. The digests GitHub reports for
the release's assets supply the binary hashes. The window is the three
newest minors for which that kind release has an image. kind v0.33.0 also
lists v1.34.11, which is the fourth and stays out. A new Kubernetes minor
without a kind image leaves the window where it is.

A change of the file reaches `main` through a pull request and gets a tag
`kubernetes-versions-YYYY-MM-DD`. Consumers fetch the file by commit SHA,
with the tag as a comment after the URL. The `select` job of the recipes CI
turns it into job outputs, and the `check` job is a matrix of recipe and
minor (trimmed from `.github/workflows/ci.yml`):

```yaml
select:
  outputs:
    recipes: ${{ steps.select.outputs.recipes }}
    kind: ${{ steps.kubernetes.outputs.kind }}
    kubernetes: ${{ steps.kubernetes.outputs.kubernetes }}
  steps:
    # ... the recipes this run checks
    - id: kubernetes
      env:
        URL: https://raw.githubusercontent.com/kadet-hub/renovate-config/843255e023682724c3325f287bafbf061a1c8b6f/kubernetes-versions.json # kubernetes-versions-2026-11-02
      run: |
        set -euo pipefail
        curl -fsSL --retry 3 "$URL" | jq -r '"kind=\(.kind | tojson)", "kubernetes=\(.kubernetes | tojson)"' | tee -a "$GITHUB_OUTPUT"

check:
  needs: [select, lint]
  strategy:
    fail-fast: false
    matrix:
      recipe: ${{ fromJSON(needs.select.outputs.recipes) }}
      kubernetes: ${{ fromJSON(needs.select.outputs.kubernetes) }}
  name: check ${{ matrix.recipe.name }} --level ${{ matrix.recipe.level }} on ${{ matrix.kubernetes.minor }}
  steps:
    # ... checkout and tools
    - env:
        KIND_VERSION: ${{ fromJSON(needs.select.outputs.kind).version }}
        KIND_SHA256: ${{ fromJSON(needs.select.outputs.kind).sha256['linux-amd64'] }}
      run: |
        curl -fsSLo "$RUNNER_TEMP/bin/kind" "https://github.com/kubernetes-sigs/kind/releases/download/$KIND_VERSION/kind-linux-amd64"
        echo "$KIND_SHA256  $RUNNER_TEMP/bin/kind" | sha256sum -c --quiet
        chmod +x "$RUNNER_TEMP/bin/kind"
    - env:
        NODE_IMAGE: ${{ matrix.kubernetes.node_image }}
        # ... recipe and level
      run: |
        # ...
        uv run --locked --project check check/check.py "$RECIPE" --level "$LEVEL" --node-image "$NODE_IMAGE" --report report.txt || status=$?
```

`check.py` hands the image to `kind create cluster --image`. kind comes from
the same file, so the binary is always the release that built the images. A
kind pin of its own would let Renovate move kind without the images.

Renovate moves commit and tag in one update. The preset in renovate-config
has a regex manager for this URL form, with the `git-tags` datasource and a
versioning that sorts the date tags. When a kind release adds a new minor,
the recipes get one pull request that replaces the oldest minor in the
matrix.

## Building a custom node image {#kind-build-node-image}

An image that kind has not published, such as the v1.37.2 that stable.txt
names, can be built locally. `kind build node-image` takes a Kubernetes source tree, a release tarball as a file or
URL, or a release version
([Building Images](https://kind.sigs.k8s.io/docs/user/quick-start/#building-images)):

    kind build node-image --type release v1.37.2 --image kindest/node:v1.37.2-local
    kind create cluster --image kindest/node:v1.37.2-local

Without `--image` the result is tagged `kindest/node:latest`. The build adds
Kubernetes to kind's base image, which holds what a node needs to run in a
container. The kind binary names its default base image,
`docker.io/kindest/base:v20260820-69b56db7` in v0.33.0. Build the image with
the kind release that will create the cluster. The image is then present
locally, and "Ensuring node image" pulls nothing. The `url`, `file` and
`release` types exist since kind v0.24.0. A build from source needs what an
upstream Kubernetes build needs, Docker with buildx included.
