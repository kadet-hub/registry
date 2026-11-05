---
title: "Argo CD config management plugin for Kapitan"
date: 2026-11-15
topics: [kapitan, ci, security]
description: "Argo CD config management plugin that runs kapitan compile in a sidecar of the repo server, tested on kind, with what it can reach and who can push."
stack:
  recipes: [blackbox-exporter]
  generators: [kubernetes]
  example: argocd-cmp
---

[Kapitan](/glossary/#kapitan) writes plain YAML, and Argo CD reads YAML
from Git. In between, someone runs `kapitan compile` and commits
`compiled/`, usually a CI job. Some teams do not want that job, because
it needs a runner with Kapitan and adds a second commit to every change.
Argo CD has a place for tools it does not ship, the config management
plugin. It is a sidecar of Argo CD's repo server that turns a checkout
into manifests. This post builds one that compiles one Kapitan
[target](/glossary/#target) per Application.

The project is
[argocd-cmp](https://github.com/kadet-hub/examples/tree/main/argocd-cmp)
in kadet-hub/examples. Its `check` script installs Argo CD 3.6.1 with the
plugin into a new [kind](/glossary/#kind) cluster on every change and once
a week. It pushes a Kapitan project to a Git server in the cluster,
changes one parameter, pushes again, and fails when Argo CD does not roll
out both commits. The project uses one [recipe](/glossary/#recipe),
[blackbox-exporter](/recipes/blackbox-exporter/) 1.0.0, the Prometheus
blackbox exporter.

## How Argo CD runs a plugin

The repo server clones the repository and renders the manifests that the
application controller applies. A sidecar plugin is a second container in
the repo server's pod. Its command is `argocd-cmp-server`, a small gRPC
server that the repo server's init container copies into a shared volume.
For each Application that uses the plugin, the repo server streams the
repository to the sidecar as a tar archive, and the sidecar runs the
plugin's `generate` command in the Application's path. Everything the
command prints to stdout must be Kubernetes objects in YAML or JSON.

Argo CD's
[documentation](https://github.com/argoproj/argo-cd/blob/v3.6.1/docs/operator-manual/config-management-plugins.md)
for v3.6.1 describes the setup. Three details shape this plugin. The
sidecar must run as user 999. The plugin's configuration is a file at
`/home/argocd/cmp-server/config/plugin.yaml` and not a Kubernetes
resource. Values the Application sets under `spec.source.plugin.env`
reach the command with the prefix `ARGOCD_ENV_`.

## The plugin

`kapitan-plugin.yaml` is a ConfigMap whose key `plugin.yaml` holds the
configuration:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ConfigManagementPlugin
metadata:
  name: kapitan
spec:
  generate:
    command: [bash, -c]
    args:
      - |
        set -euo pipefail
        shopt -s globstar nullglob
        kapitan compile -t "$ARGOCD_ENV_TARGET" >&2
        files=(compiled/"$ARGOCD_ENV_TARGET"/**/*.yml compiled/"$ARGOCD_ENV_TARGET"/**/*.yaml)
        if ((${#files[@]} == 0)); then
          echo "no YAML files in compiled/$ARGOCD_ENV_TARGET" >&2
          exit 1
        fi
        for f in "${files[@]}"; do
          echo ---
          cat "$f"
        done
```

`kapitan compile -t` compiles the target the Application names in its env
`TARGET`. Kapitan's log goes to stderr, because stdout carries the
manifests. The loop prints every YAML file under `compiled/<target>`, so
each of them has to be a Kubernetes object. A target that also compiles
documentation or scripts as YAML needs a narrower pattern.

The check for an empty result is there because of a warning in Argo CD's
documentation. A plugin that prints nothing gives an Application with
automated `prune` an empty desired state, and Argo CD deletes everything
the Application deployed. A target that compiles to nothing is a mistake,
so the plugin fails instead.

The configuration leaves three things out. There is no `init` command,
because nothing has to be fetched (next section). There is no `discover`
section. Discovery lets Argo CD pick a plugin for an Application that
names no tool, and without it the plugin renders only Applications that
ask for `kapitan` by name. The sidecar logs exactly that when it
starts. There is no `version` either. With one, every Application would
have to name `kapitan-<version>` and change with each bump.

## The sidecar

`repo-server-patch.yaml` is a strategic merge patch for the Deployment
`argocd-repo-server` of Argo CD's release manifest:

```yaml
spec:
  template:
    spec:
      containers:
        - name: kapitan
          image: docker.io/kapicorp/kapitan:0.36.3@sha256:04b9ca04f5041851631fb1041fbafe37b1ca6c3ad99a81d6ccd40f5ebd20f857
          command: [/var/run/argocd/argocd-cmp-server]
          env:
            - name: PYTHONWARNINGS
              value: ignore
          securityContext:
            runAsNonRoot: true
            runAsUser: 999
            allowPrivilegeEscalation: false
            capabilities:
              drop: [ALL]
            readOnlyRootFilesystem: true
            seccompProfile:
              type: RuntimeDefault
          volumeMounts:
            - name: var-files
              mountPath: /var/run/argocd
            - name: plugins
              mountPath: /home/argocd/cmp-server/plugins
            - name: kapitan-plugin
              mountPath: /home/argocd/cmp-server/config/plugin.yaml
              subPath: plugin.yaml
            - name: kapitan-tmp
              mountPath: /tmp
      volumes:
        - name: kapitan-plugin
          configMap:
            name: kapitan-plugin
        - name: kapitan-tmp
          emptyDir: {}
```

```sh
kubectl apply -f kapitan-plugin.yaml
kubectl -n argocd patch deployment argocd-repo-server --patch-file repo-server-patch.yaml
```

The image is Kapitan's own, version 0.36.3, pinned by
[digest](/glossary/#digest). It brings the omegaconf and reclass-rs
inventory backends, bash and git. The volumes `var-files` and `plugins`
come with Argo CD's manifest. The first holds `argocd-cmp-server`, the
second the socket the repo server talks to. The sidecar gets a `/tmp` of
its own, as the documentation asks, and Kapitan writes `compiled/` into
the copy of the repository there, so the root filesystem stays read-only.
Kapitan's dependencies print deprecation warnings on every run, and
`PYTHONWARNINGS=ignore` keeps them out of the error Argo CD shows when a
compile fails.

With Argo CD's Helm chart, the same container goes into
`repoServer.extraContainers`. The [argocd](/generators/argocd/) generator
renders Applications, ApplicationSets and AppProjects, not Argo CD
itself, so it cannot add the sidecar.

## What goes into Git

The repository Argo CD reads holds the Kapitan project and what it
needs to compile:

```text
.kapitan
fetch/targets/recipes.yml
inventory/targets/blackbox-exporter.yml
inventory/classes/recipes/blackbox-exporter/
lib/kubernetes/
```

The plugin runs `kapitan compile` without `--fetch`, and the recipe and
the [kubernetes](/generators/kubernetes/) generator it pins are committed.
`--fetch` would check neither the signed [index](/glossary/#index) nor
an [attestation](/glossary/#attestation). It also cannot fetch the
recipe. Kapitan 0.36.3 reads the [inventory](/glossary/#inventory) before
it fetches, and the recipe is a class of that inventory, so the compile
stops with `Class recipes.blackbox-exporter not found`
(kapicorp/kapitan#1638). And it would need the repo server's pod to reach
ghcr.io.

`check` verifies the recipe and the generator as the registry's
[consumer docs](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#verifying-a-recipe-by-hand)
describe and pulls them by digest into `inventory/classes/recipes/` and
`lib/`. The Pi-hole post shows
[the commands](/blog/pihole-powerdns-kubernetes/#verify-then-pull-by-digest).
A pin change becomes the same steps on a workstation, then a commit. A
Renovate pull request that moves a pin changes only the pin. The sidecar
compiles what is in `lib/`, so such a pull request is complete only once
someone has verified and pulled the new version into the repository.

The target is the recipe's example plus two settings:

```yaml
classes:
  - recipes.blackbox-exporter
parameters:
  namespace: blackbox-exporter
  kapitan:
    vars:
      target: blackbox-exporter
  components:
    blackbox-exporter-prometheus-blackbox-exporter:
      replicas: 1
      security_context:
        seccompProfile:
          type: RuntimeDefault
```

The Application creates the namespace with the Pod Security level
`restricted`. The recipe sets no seccomp profile, which that level
requires, and in the first local run the ReplicaSet could not create a
pod until the target added it.

## The Application

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: blackbox-exporter
  namespace: argocd
spec:
  project: default
  source:
    repoURL: http://gitea.git.svc.cluster.local:3000/kadet/apps.git
    targetRevision: main
    path: .
    plugin:
      name: kapitan
      env:
        - name: TARGET
          value: blackbox-exporter
  destination:
    server: https://kubernetes.default.svc
    namespace: blackbox-exporter
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions: [CreateNamespace=true]
    managedNamespaceMetadata:
      labels:
        pod-security.kubernetes.io/enforce: restricted
```

`path` is the directory that holds `.kapitan`. A second target gets a
second Application with another `TARGET`. Each Application renders on its
own, and each render reads the whole inventory first.

## Rolling out a change

`check` pushes the project as one commit to Gitea, creates the
Application and waits until Argo CD reports it `Synced` at that commit and
`Healthy`, with source type `Plugin`, and the exporter's Deployment has
one available replica. Then it changes one parameter in the target and
pushes:

```diff
-      replicas: 1
+      replicas: 2
```

Argo CD learns about a push from a webhook or by polling, by default every
120 seconds plus up to 60 seconds of jitter (`timeout.reconciliation`).
`check` sets the annotation `argocd.argoproj.io/refresh: normal` on the
Application, which is what Argo CD's webhook handler sets for a push. It
then requires the same state at the new commit, with two available
replicas.

## What the CI run showed

[Run 41969033152](https://github.com/kadet-hub/examples/actions/runs/41969033152)
of the examples workflow tested commit `b309a90` of
[kadet-hub/examples#144](https://github.com/kadet-hub/examples/pull/144)
on 5 November 2026, on GitHub's `ubuntu-24.04` runner, with the kind node
image `kindest/node:v1.37.0`. The durations below come from the log's
timestamps or are what `check` printed, in whole seconds.

Verifying the index, the recipe and the generator and pulling them took
15 seconds. kind had the cluster ready 40 seconds later. Argo CD, with the
sidecar patched in, had every Deployment available 51 seconds after the
first `kubectl apply`. The token and network checks took 11 seconds.

Argo CD reported the Application `Synced` at the first commit and
`Healthy` 14 seconds after `check` created it. After the second push and
the refresh it took another 14 seconds until the same held at the new
commit, with two replicas available. The plugin's two `generate` calls
took 9.4 and 9.5 seconds, most of that time. They compiled one target
with four objects: a ConfigMap, a Deployment, a Service and a
ServiceAccount. At the end the sidecar's memory working set was 25 MiB,
the repo server's 30 MiB. The whole check took 148 seconds.

## What the sidecar can reach

The sidecar shares the repo server's pod, and with it the pod's network
and service account. `check` tests both.

The pod has no Kubernetes API token. Argo CD's manifest sets
`automountServiceAccountToken: false` on the repo server's pod, and
`check` fails if the sidecar finds a token. The plugin has no identity
to read or change cluster objects with.

The network is open. Argo CD's manifest ships NetworkPolicies for ingress
only, so the sidecar reaches the internet and every Service in the
cluster. `check` opens a connection from the sidecar to ghcr.io on port
443, then applies `repo-server-egress.yaml`, which allows the pod DNS,
Argo CD's Redis and the Git server, and requires the same connection to
fail. Both commits render under that policy, so the plugin needs no
other network. A repo server that serves other Applications also needs
their Git hosts and chart registries, and a NetworkPolicy names IP
ranges, not host names. Redis is reachable, but it requires the password
from the Secret `argocd-redis`, and in the repo server's pod only the
repo server's own container gets it.

Every Application that uses the plugin is rendered in the same container,
as the same user, under the same `/tmp`. When a render ends, Argo CD kills
the command's process group, but not a process that started a session of
its own. Such a process can read the sources of the Applications rendered
after it. This comes from reading `cmpserver/plugin/plugin.go` of v3.6.1
and is not tested. The plugin does not get the repository credentials
that the repo server holds, because `provideGitCreds` is off by default.

## Who can push

The plugin runs code from the repository. kadet generators in `lib/` are
Python modules that Kapitan imports. Kapitan renders Jinja2 templates in
a plain `jinja2.Environment`, not in Jinja2's sandbox. The `external`
input runs any program the inventory names. And `.kapitan` in the
repository sets the default of every compile flag, `reveal` and `fetch`
included (`from_dot_kapitan` in Kapitan 0.36.3's `cli.py`), so the
command line in `plugin.yaml` is not a control.

Everyone who can push to the branch an Application tracks therefore runs
code in the sidecar, with the reach described above. Protect that branch
as you would protect a CI job that compiles with credentials: required
reviews, no direct pushes. The AppProject limits which objects of the
output Argo CD applies and where. It does not limit what the plugin runs.

## Refs and secrets

Kapitan [refs](/glossary/#ref), such as `?{gkms:prod/db-password}`, stand
for secrets. Without `--reveal`, the compiled output holds the ref's tag
in place of the value. The plugin passes no `--reveal`, but the
repository's `.kapitan` can turn it on. What keeps a value closed is
whether the sidecar can decrypt it.

- `base64` and `plain` refs encrypt nothing. Anyone who can read the
  repository can read them, the sidecar included.
- `gpg` refs need a private key in the sidecar.
- `gkms`, `awskms` and `azkms` refs need cloud credentials, `vaultkv` a
  Vault token. A cloud workload identity belongs to the pod's
  ServiceAccount, not to one container. EKS's IRSA webhook, for example,
  adds its token to every container of a pod unless the pod lists the
  container under `eks.amazonaws.com/skip-containers`. A repo server with
  such an identity hands it to the sidecar as well.

Once the sidecar can decrypt a ref, everyone who can push can reveal it,
for example into a ConfigMap, which Argo CD shows in its UI. Argo CD also
keeps generated manifests in plaintext in its Redis cache
([secret management](https://github.com/argoproj/argo-cd/blob/v3.6.1/docs/operator-manual/secret-management.md)).
The same page recommends creating secrets on the destination cluster, for
example with External Secrets, as the
[cluster add-ons post](/blog/kubernetes-cluster-add-ons/) does. The
recipe here renders no Secret.

## What it costs

The pull request no longer shows the compiled change. Reviewers see the
inventory diff, and the compiled manifests show up only in Argo CD and
in the cluster. `argocd app diff` or a local compile shows them before a
merge.

Every new commit compiles in the sidecar, once per Application. The repo
server waits 60 seconds for manifests by default
(`server.repo.server.timeout.seconds` and
`controller.repo.server.timeout.seconds`), and the sidecar stops a
command after 90 seconds (`ARGOCD_EXEC_TIMEOUT`). A compile that takes
longer fails, and Argo CD shows the error on the Application. One target
with four objects took 9.5 seconds in the CI run. Kapitan reads the whole
inventory for every target, so a large inventory takes longer per
Application.

kadet-hub's consumer workflow compiles in a gVisor sandbox and checks the
output before anything reaches the cluster, as in the
[first platform post](/blog/first-platform/). The sidecar runs none of
those checks.
