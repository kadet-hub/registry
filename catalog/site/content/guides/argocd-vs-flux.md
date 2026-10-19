---
title: Argo CD vs Flux, deployed side by side on kind
layout: prose
description: Argo CD vs Flux on one app from one Git commit, with install size, sync time and drift handling measured on kind, and where Helm and Kustomize fit in.
---

Argo CD and Flux both pull Kubernetes manifests from Git and keep a cluster
in step with them. Both are CNCF graduated projects: Flux since
[November 30, 2022](https://www.cncf.io/projects/flux/), Argo since
[December 6, 2022](https://www.cncf.io/projects/argo/). This comparison
deploys the same app from the same Git commit once through each, on its own
kind cluster, and a CI job fails unless both reach their ready state and
behave as described below. The code is
[`argocd-vs-flux`](https://github.com/kadet-hub/examples/tree/main/argocd-vs-flux)
in kadet-hub/examples; the numbers below are from one local run of its
check on kind in Docker.

## Render, then deliver

Helm, Kustomize and [Kapitan](/glossary/#kapitan) render manifests. Argo CD
and Flux deliver them: they fetch a revision from Git, apply it and report
whether the cluster matches. So "Helm vs Argo CD" is not a choice between
two tools for the same job: Argo CD or Flux deploys what Helm, Kustomize or
Kapitan produced.

Both delivery tools render Helm charts and Kustomize directories themselves,
but they treat Helm differently. Argo CD runs `helm template` and applies
the result as its own objects, so `helm ls` does not show the app
([Argo CD FAQ](https://github.com/argoproj/argo-cd/blob/v3.5.5/docs/faq.md#after-deploying-my-helm-application-with-argo-cd-i-cannot-see-it-with-helm-ls-and-other-helm-commands)).
Flux's helm-controller performs Helm actions such as install, upgrade and
rollback, and keeps the release in Helm's storage
([HelmRelease](https://github.com/fluxcd/helm-controller/blob/v1.6.5/docs/spec/v2/helmreleases.md)).

Kapitan writes plain YAML files, which both read without extra tooling:
Argo CD as a directory source with `recurse: true`
([directory apps](https://github.com/argoproj/argo-cd/blob/v3.5.5/docs/user-guide/directory.md)),
Flux by generating a `kustomization.yaml` for a path that has none
([Kustomization](https://github.com/fluxcd/kustomize-controller/blob/v1.9.6/docs/spec/v1/kustomizations.md#generating-a-kustomizationyaml-file)).

## The example

One Kapitan [inventory](/glossary/#inventory) has three
[targets](/glossary/#target). `web` renders the app with the
[kubernetes](/generators/kubernetes/) [generator](/glossary/#generator): a
Namespace, a Deployment of `nginx-unprivileged` with two replicas under the
restricted Pod Security profile, and a Service. `argocd` renders the
Application with the [argocd](/generators/argocd/) generator, `flux` the
GitRepository and Kustomization with the [flux](/generators/flux/)
generator:

```yaml
# inventory/targets/argocd.yml
parameters:
  generators:
    argocd:
      applications:
        web:
          project: default
          destination: web
          source:
            repoURL: http://gitea.git.svc.cluster.local:3000/kadet/app.git
            targetRevision: main
            path: web
            directory:
              recurse: true
          sync_policy:
            automated:
              prune: true
              selfHeal: true
```

```yaml
# inventory/targets/flux.yml
parameters:
  generators:
    flux:
      git_repositories:
        app:
          url: http://gitea.git.svc.cluster.local:3000/kadet/app.git
          ref: main
      kustomizations:
        web:
          source: app
          path: ./web
          prune: true
```

The argocd generator fills in `server: https://kubernetes.default.svc` for
the destination; the flux generator writes the `sourceRef`, a 1 minute
interval on the GitRepository and the recommended Kustomization settings,
including a 60 minute interval.

The check pushes the compiled app as one commit to a Gitea inside the
cluster, because the commit has to exist before either tool can deploy it.
It then installs Argo CD 3.5.5 or Flux 2.9.6 from the release's
`install.yaml`, pinned by sha256, on Kubernetes 1.37.0, applies the tool's
target and asserts with Chainsaw that the Application is `Synced` and
`Healthy`, or the Kustomization `Ready`, at exactly the pushed commit, and
that both replicas are available. `argocd-vs-flux/check argocd` and
`argocd-vs-flux/check flux` run the same locally, given Docker, kind,
kubectl, Chainsaw and a logged-in `gh` for verifying the generators.

## What each installs

| | Argo CD 3.5.5 | Flux 2.9.6 |
|---|---|---|
| [CRDs](/glossary/#crd) in `install.yaml` | 3 | 15 |
| Pods | 7 | 7 |
| Images | 3: `argocd`, `dex`, `redis` | 7, one per controller |
| `install.yaml` applied until all workloads available | 68 s | 72 s |
| Memory working set of those pods after the check | 277 MiB | 162 MiB |

The install time is mostly image pulls: over three runs Flux took between
72 and 102 seconds. Memory comes from the kubelet's summary API, with the
tool idle and one app deployed.

Argo CD's seven pods are the application controller, the repo server, the
API server that serves the web UI and CLI, the ApplicationSet controller,
the notifications controller, Redis and Dex for SSO. A headless
[core install](https://github.com/argoproj/argo-cd/blob/v3.5.5/docs/operator-manual/core.md)
drops the API, notifications and SSO and relies on Kubernetes RBAC.

Flux's `install.yaml` holds all seven controllers, including image
automation and source-watcher. `flux install` and `flux bootstrap` install
four by default: source, kustomize, helm and notification controller
([defaults](https://github.com/fluxcd/flux2/blob/v2.9.6/pkg/manifestgen/install/options.go#L46-L47)).
None of them serves a UI.

## Time to sync

From creating the Application to the Deployment reporting available took
10 seconds, and as long from creating the Kustomization. Both include
pulling the nginx image, so at this size the tools do not differ in a way
that matters.

After the first sync, Argo CD checks Git for new commits every 120 seconds
plus up to 60 seconds of jitter
([`timeout.reconciliation`](https://github.com/argoproj/argo-cd/blob/v3.5.5/docs/operator-manual/argocd-cm.yaml)),
Flux at the GitRepository's interval, 1 minute here. Both accept a webhook
from the Git server to skip the wait: Argo CD on its API server
([webhooks](https://github.com/argoproj/argo-cd/blob/v3.5.5/docs/operator-manual/webhook.md)),
Flux through a `Receiver`
([receivers](https://github.com/fluxcd/notification-controller/blob/v1.9.4/docs/spec/v1/receivers.md)).

## Drift

The check scales the Deployment to one replica with `kubectl scale`.

Argo CD's application controller continuously compares the live objects
with Git
([architecture](https://github.com/argoproj/argo-cd/blob/v3.5.5/docs/operator-manual/architecture.md)).
With `selfHeal` on, it scaled the Deployment back to two replicas 2 seconds
later. Without `selfHeal` it would mark the Application `OutOfSync` and
leave the change in place
([automated sync](https://github.com/argoproj/argo-cd/blob/v3.5.5/docs/user-guide/auto_sync.md#automatic-self-healing)).

Flux did not react. After 30 seconds the Deployment still had one replica
and the Kustomization still reported `Ready`. kustomize-controller
corrects drift when it reconciles: at the Kustomization's interval, 60
minutes here, or on request. Setting the `reconcile.fluxcd.io/requestedAt`
annotation, which `flux reconcile kustomization` does, restored two replicas
1 second later
([triggering a reconcile](https://github.com/fluxcd/kustomize-controller/blob/v1.9.6/docs/spec/v1/kustomizations.md#triggering-a-reconcile)).
A shorter interval narrows the window at the cost of more applies.

## Choosing

Choose Argo CD when people need a UI to see and sync applications, when one
installation should deploy to many clusters registered as Secrets
([clusters](https://github.com/argoproj/argo-cd/blob/v3.5.5/docs/operator-manual/declarative-setup.md#clusters)),
or when drift should be undone within seconds.

Choose Flux when a cluster should run controllers only, with Kubernetes
RBAC as the access model and no API server or UI of its own, when Helm
releases should stay Helm releases, or when image updates should be written
back to Git by the image automation controllers
([image updates](https://fluxcd.io/flux/guides/image-update/)). A
Kustomization can also apply to a remote cluster through a kubeconfig
Secret
([remote clusters](https://github.com/fluxcd/kustomize-controller/blob/v1.9.6/docs/spec/v1/kustomizations.md#kubeconfig-remote-clusters)).

With either tool, the argocd and flux generators render the delivery
objects from the same Kapitan inventory as the app, so a new target and its
Application or Kustomization are one change. The
[Helm alternatives guide](/guides/helm-alternatives-for-kubernetes/)
compares the tools that render the app itself.
