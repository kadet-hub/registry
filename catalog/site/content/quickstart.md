---
title: "Kapitan quickstart: Uptime Kuma on Kubernetes with kind"
description: "Kapitan quickstart: install Kapitan, fetch a recipe pinned by digest, verify it, compile it and run Uptime Kuma on a kind cluster in about five minutes."
layout: quickstart
---

## Coming from Helm?

The recipe takes the place of the chart, and the target takes the place
of `values.yaml`. What you would pass with `--set` goes under `parameters`
in `inventory/targets/uptime-kuma.yml`, and the target can override any
value the recipe's classes set, not only the ones a template exposes.
`kapitan compile` takes the place of `helm template`: it writes manifests,
and nothing keeps a release in the cluster.

[Writing a Helm chart vs Kapitan](/blog/helm-chart-vs-kapitan-inventory/)
rebuilds metrics-server, cert-manager and kube-prometheus-stack as one
inventory and compares the objects on kind.
[Helm vs Kustomize vs Kapitan on one Kubernetes app](/blog/same-app/)
renders the same app with all three tools for two environments. For a
Bitnami chart, [Bitnami chart alternatives](/guides/bitnami-chart-alternatives/)
names the replacement and the recipe where there is one.

## Coming from Kustomize?

The recipe's classes play the part of a base, and the target plays the
part of an overlay: the inventory merges the classes in order, and the
target's `parameters` override them.
[Helm vs Kustomize vs Kapitan on one Kubernetes app](/blog/same-app/)
compares overlays for two environments with the same app as an inventory.

A field that neither the recipe nor a chart sets is changed after
rendering, with a patch in Kustomize and with the
[mutate](/generators/mutate/) generator in Kapitan. Three posts make the
same change both ways on rendered charts:
[adding fields with a JSON patch](/blog/kustomize-json-patch-helm-chart/),
[setting an environment variable with `valueFrom`](/blog/kustomize-patch-env-helm-chart/)
and [deleting a resource](/blog/kustomize-delete-resource-helm-chart/).
