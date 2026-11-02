---
title: "Docker tag and digest: which one Kubernetes runs"
date: 2026-11-04
topics: [supply chain, kapitan, validation]
description: "A Kubernetes image reference with a tag and a digest runs the digest and drops the tag. Tested on kind, and why both belong in one literal line."
---

An image reference can carry a tag and a [digest](/glossary/#digest) at
once, as in `busybox:1.37.0@sha256:73aaf090…`. Kubernetes runs the image
the digest names. The tag is removed before the pull and never compared
with the digest. If the two disagree, the pod runs the digest's image while
the spec shows the tag's version.

The [recipes](/recipes/) in kadet-hub/recipes could produce exactly that
mismatch. They kept the tag in one file and the digest in another, until
[kadet-hub/recipes#50](https://github.com/kadet-hub/recipes/pull/50) put
both into one literal line.

Everything below ran on 2026-11-02 with kind v0.33.0 and its default node
image `kindest/node:v1.37.0@sha256:a1ed56cf…` (Kubernetes v1.37.0,
containerd v2.3.4), kubectl v1.37.2 and oras 1.3.6.

## A tag that disagrees with its digest

The two busybox tags resolved to these digests:

    $ oras manifest fetch --descriptor docker.io/library/busybox:1.36.1
    {"mediaType":"application/vnd.oci.image.index.v1+json","digest":"sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662","size":9535}
    $ oras manifest fetch --descriptor docker.io/library/busybox:1.37.0
    {"mediaType":"application/vnd.oci.image.index.v1+json","digest":"sha256:a7dbc319b1438115a207e11930dc4bb3e643dcb3ec0bdd694bb36cd8fad289ec","size":9535}

Each is the digest of an OCI image index, the list of per-platform images
behind the tag. Tags can move, so a later run may resolve other digests.

The pod takes the tag 1.37.0 and the digest of 1.36.1. That is the state a
version bump leaves behind when the digest stays:

    apiVersion: v1
    kind: Pod
    metadata:
      name: tag-and-digest
    spec:
      restartPolicy: Never
      containers:
      - name: busybox
        image: busybox:1.37.0@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662
        command: [sh, -c, "busybox | head -1"]

The API server accepts it, and the kubelet pulls and starts it:

    $ kubectl get events --field-selector involvedObject.name=tag-and-digest -o jsonpath='{range .items[*]}{.reason}{": "}{.message}{"\n"}{end}'
    Scheduled: Successfully assigned default/tag-and-digest to post-digest-24c921-control-plane
    Pulling: Pulling image "busybox:1.37.0@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662"
    Pulled: Successfully pulled image "busybox:1.37.0@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662" in 2.15s (2.15s including waiting). Image size: 2217006 bytes.
    Created: Container created
    Started: Container started

The container prints the version of the binary it runs:

    $ kubectl logs tag-and-digest
    BusyBox v1.36.1 (2023-05-18 22:34:17 UTC) multi-call binary.

The pod's image fields:

    $ kubectl get pod tag-and-digest -o jsonpath='{.spec.containers[0].image}{"\n"}{.spec.containers[0].imagePullPolicy}{"\n"}{.status.containerStatuses[0].image}{"\n"}{.status.containerStatuses[0].imageID}{"\n"}'
    busybox:1.37.0@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662
    IfNotPresent
    sha256:b116e155074440ffd9e449559433feb4cd2341eb3554b1da1c638c976e56451d
    docker.io/library/busybox@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662

`.spec.containers[].image` keeps the string as written, tag included.
`.status.containerStatuses[].imageID` holds the repository and the digest
without a tag. It is the field that tells you which image runs. Its digest
is the one oras resolved for 1.36.1.

`.status.containerStatuses[].image` carries no tag either. containerd
reports the image's first tag there, and the node-local image ID when the
image has none
([container_status.go](https://github.com/containerd/containerd/blob/v2.3.4/internal/cri/server/container_status.go#L40-L66)).
That ID, `sha256:b116e155…`, is the digest of the image's config. The node
stored no tag for the image it pulled by digest:

    $ docker exec post-digest-24c921-control-plane crictl images --digests | grep -E 'IMAGE|busybox'
    IMAGE                                           TAG                  DIGEST              IMAGE ID            SIZE
    docker.io/library/busybox                       <none>               73aaf090f3d85       b116e15507444       2.22MB

A second pod with `busybox:1.37.0` and no digest prints `BusyBox v1.37.0`.
Its `imageID` ends in `a7dbc319…`, the digest of 1.37.0. Its
`.status.containerStatuses[].image` is `docker.io/library/busybox:1.37.0`.

## The tag is never looked up

The tag `no-such-tag` does not exist:

    $ oras manifest fetch --descriptor docker.io/library/busybox:no-such-tag
    Error response from registry: failed to find "docker.io/library/busybox:no-such-tag": docker.io/library/busybox:no-such-tag: not found

A third pod uses it in front of the 1.36.1 digest, with
`imagePullPolicy: Always` so that the kubelet asks for a pull:

    apiVersion: v1
    kind: Pod
    metadata:
      name: no-such-tag
    spec:
      restartPolicy: Never
      containers:
      - name: busybox
        image: busybox:no-such-tag@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662
        imagePullPolicy: Always
        command: [sh, -c, "busybox | head -1"]

Its events report
`Successfully pulled image "busybox:no-such-tag@sha256:73aaf090…"`, and it
runs 1.36.1:

    $ kubectl logs no-such-tag
    BusyBox v1.36.1 (2023-05-18 22:34:17 UTC) multi-call binary.

The kubelet hands the reference to the container runtime as written. Its
`applyDefaultImageTag` appends `:latest` only when a reference has neither
a tag nor a digest
([image_manager.go](https://github.com/kubernetes/kubernetes/blob/v1.37.0/pkg/kubelet/images/image_manager.go#L422-L439),
Kubernetes v1.37.0).

containerd's CRI plugin normalizes the reference with `ParseDockerRef`
before it pulls
([image_pull.go](https://github.com/containerd/containerd/blob/v2.3.4/internal/cri/server/images/image_pull.go#L153)).
The function comes from distribution/reference v0.6.0, the version
containerd v2.3.4 depends on. Its documentation says what happens to the
tag:

> For references containing both a tag and a digest, it returns a digested reference.

Its example turns `docker.io/library/busybox:latest@sha256:7cc4b5ae…`
into `docker.io/library/busybox@sha256:7cc4b5ae…`
([normalize.go](https://github.com/distribution/reference/blob/v0.6.0/normalize.go#L88-L121)).
containerd also resolves a reference against the images already on the
node through `ParseDockerRef`
([service.go](https://github.com/containerd/containerd/blob/v2.3.4/internal/cri/server/images/service.go#L160-L186)).
The presence check behind `IfNotPresent` therefore ignores the tag as well.

The Kubernetes documentation states the outcome in its list of image name
examples. It describes `registry.k8s.io/pause:3.5@sha256:1ff6c18f…` as
"Image name with tag and digest. Only the digest will be used for
pulling."
([Images](https://kubernetes.io/docs/concepts/containers/images/#image-names)).

## The tag still sets the pull policy

When `imagePullPolicy` is omitted, the API server defaults it from the tag.
`SetDefaults_Container` sets `Always` for the tag `latest` and
`IfNotPresent` for any other
([defaults.go](https://github.com/kubernetes/kubernetes/blob/v1.37.0/pkg/apis/core/v1/defaults.go#L83-L93)).
The tag comes from `ParseImageName`, which returns it even when a digest is
present
([parsers.go](https://github.com/kubernetes/kubernetes/blob/v1.37.0/pkg/util/parsers/parsers.go#L32-L55)).
A server-side dry run shows both cases:

    $ kubectl run latest-and-digest --restart=Never --image=busybox:latest@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662 --dry-run=server -o jsonpath='{.spec.containers[0].imagePullPolicy}{"\n"}'
    Always
    $ kubectl run digest-only --restart=Never --image=busybox@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662 --dry-run=server -o jsonpath='{.spec.containers[0].imagePullPolicy}{"\n"}'
    IfNotPresent

The documentation's list of defaults says: "if you omit the
`imagePullPolicy` field, and you specify the digest for the container
image, the `imagePullPolicy` is automatically set to `IfNotPresent`"
([default image pull policy](https://kubernetes.io/docs/concepts/containers/images/#imagepullpolicy-defaulting)).
With `:latest` in front of the digest, the tag decides and the result is
`Always`. Under `Always` the runtime contacts the registry at every
container start, although the digest already fixes the image
([image pull policy](https://kubernetes.io/docs/concepts/containers/images/#image-pull-policy)).

## Two files, one image

The recipes are Kapitan [inventory](/glossary/#inventory) classes. Until
kadet-hub/recipes#50, each kept an image's tag in
`applications.<name>.version` in its `init.yml`, and the digest in the
image line of another class file. In the miniflux recipe, `init.yml` set
`version: 2.3.4` and `miniflux.yml` had this line:

    image: miniflux/miniflux:${applications.miniflux.version}@sha256:72e49f513a63104506aab98ba8cfc3a409d4fde23550a583dec07ec941f1e94e

The `${...}` is an [interpolation](/glossary/#interpolation) that Kapitan
fills in from the parameter. A target that raised the version without the
digest compiled to manifests with the new tag and the old digest. That is
the first pod above. The spec and every diff of the compiled manifests show
the new version, and the kubelet runs the old image.

The fix writes each image as one literal,
`<registry>/<repository>:<tag>@sha256:<digest>`:

    image: miniflux/miniflux:2.3.4@sha256:72e49f513a63104506aab98ba8cfc3a409d4fde23550a583dec07ec941f1e94e

`applications.<name>.version` is gone wherever it only fed image tags.
`check lint`, the linter the recipes run in CI, now fails on a line of a
class file that holds both `@sha256:` and `${`:

    for n, line in enumerate(text.splitlines(), 1):
        if "@sha256:" in line and "${" in line:
            errors.append(f"{f}:{n}: image reference takes its tag from an interpolation (RCP-66)")

A reference without a digest does not match this check, and the recipes'
specification leaves those to review
([RCP-66](https://github.com/kadet-hub/recipes/blob/main/docs/specs/recipes.md)).

## Renovate reads the tag from the same line

Renovate writes references in this form. Its Docker documentation says
that "When pinning a digest, Renovate retains the Docker tag in the `FROM`
line for readability", with `FROM node:14.15.1@sha256:d938c176…` as the
example
([Digest Pinning](https://docs.renovatebot.com/docker/#digest-pinning)).
The `pinDigests` option pins images "by means of their SHA256 digest and
not only by tag"
([pinDigests](https://docs.renovatebot.com/configuration-options/#pindigests)).

Renovate's updates start from the tag it finds in the file
([How It Works](https://docs.renovatebot.com/docker/#how-it-works)):

> If the image tag in use "looks" like a version (e.g. `myimage:1`, `myimage:1.1`, `myimage:1.1.0`, `myimage:1-onbuild`) then Renovate checks the Docker registry for upgrades

The same page describes pull requests for a new digest behind an unchanged
tag
([Digest Updating](https://docs.renovatebot.com/docker/#digest-updating)).

In kadet-hub/recipes, Renovate's regex managers capture the tag as
`currentValue` and the digest as `currentDigest` from the same image line.
Those are the capture groups the
[regex manager documentation](https://docs.renovatebot.com/modules/manager/regex/#required-capture-groups)
asks for. The old miniflux line had `${applications.miniflux.version}`
where that version belongs.
