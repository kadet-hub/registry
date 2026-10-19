---
title: Helm alternatives for Kubernetes, compared on one app
layout: prose
description: Kustomize, Pulumi, cdk8s, Tanka and Kapitan as Helm alternatives for Kubernetes, each rendering the same app to manifests a CI job checks for equality.
---

Most comparisons of Helm alternatives list features. This one starts from
output: the same two-service app in two environments, rendered with Helm,
Kustomize, Pulumi, cdk8s, Tanka and [Kapitan](/glossary/#kapitan), and a check in CI that fails
unless every tool produces the same objects. The code is in
[kadet-hub/examples](https://github.com/kadet-hub/examples):
[`same-app`](https://github.com/kadet-hub/examples/tree/main/same-app) for
Helm, Kustomize and Pulumi,
[`config-tools`](https://github.com/kadet-hub/examples/tree/main/config-tools)
for Tanka and cdk8s, both against the same Kapitan [inventory](/glossary/#inventory).

## The app

Namespace `shop` holds `web` and `api`, each a Deployment, a ClusterIP
Service and a ConfigMap mounted into the pod, under the restricted Pod
Security profile. Dev and prod differ in image tags, replicas, requests and
log level, and prod adds PodDisruptionBudgets: 6 objects in dev, 8 in prod.
The api's ConfigMap holds `web_url: http://web.shop.svc:80`, which depends on
the web Service port. Every tool renders those objects identically once
objects and keys are sorted and the tool's own `managed-by` label is
dropped.

## The tools at a glance

| | Written in | Values from | A value derived from another | Output | Applies to the cluster |
|---|---|---|---|---|---|
| Helm | Go templates | values files per release | no: releases cannot read each other's values | Kubernetes | yes, with release history |
| Kustomize | YAML patches | overlays | only through `replacements`, per field | Kubernetes | through `kubectl apply -k` |
| Pulumi | TypeScript, Python, Go, C#, Java, YAML | stack config and code | yes, in code | any cloud resource; Kubernetes YAML only in render mode | yes, with state and previews |
| cdk8s | TypeScript, Python, Go, Java | code | yes, in code | Kubernetes | no, writes files |
| Tanka | Jsonnet | Jsonnet objects | yes, through late binding | Kubernetes | yes, `tk apply` and `tk diff` |
| Kapitan | YAML inventory, generators in Python | classes and targets | yes, `${...}` [interpolation](/glossary/#interpolation) across the inventory | any file: Kubernetes, Terraform, docs | no, writes files |

The derived-value column is tested, not read from documentation: changing
only the web Service port made Helm and Kustomize render a stale `:80` in
the api's ConfigMap without an error, while Tanka, cdk8s and Kapitan
followed the change. The Pulumi program computes `web_url` from the port
variable, the same way cdk8s does.

## Kustomize

Kustomize ships inside `kubectl`, needs no install and patches YAML you do
not control better than any of the others. It has no parameters, so a
second app usually starts as a copy of the first app's base; in the example
the second app touched 9 files and added 149 lines, against 3 files and 25
lines in Helm, whose chart was already generic. Use it for vendor YAML and
small differences between environments.

## Pulumi

Pulumi programs resources in a general-purpose language and deploys them
itself, with state, `pulumi preview` and `pulumi refresh` for drift, across clouds and
Kubernetes. That is its strength and the reason it is a different kind of
tool: Helm, Kustomize, Tanka, cdk8s and Kapitan produce manifests, Pulumi
owns the deployment.

For a Git-reviewed manifest workflow the Kubernetes provider has a render
mode, `renderYamlToDirectory`, which the example uses. Three facts from
running it:

- The provider marks it "BETA FEATURE". It still tries the kubeconfig's
  cluster to tell namespaced [custom resources](/glossary/#crd) from cluster-scoped ones, and
  continues without one. Secrets are written to the YAML in plaintext.
- Rendering still needs a stack and state; the example uses the local file
  backend in a temporary directory, so no Pulumi Cloud account is involved.
- The provider round-trips every object through Kubernetes' typed Go structs,
  so explicit zero values disappear. In the example both readiness probes
  lost `initialDelaySeconds: 0`, which is the API default; the check drops
  that field before comparing.

The provider is a plugin of about 180 MB that the CLI downloads at run time.
Its npm install script fetches it without a checksum; the example installs
it with `pulumi plugin install --checksum` and disables automatic plugin
downloads. Use Pulumi when one program should own cloud resources and their
Kubernetes workloads together, and you accept state as the source of truth.

## cdk8s and Tanka

cdk8s generates typed classes for every Kubernetes [kind](/glossary/#kind), so a misspelt field
fails the TypeScript compiler before anything renders; Tanka and Kapitan
rendered the same typo without an error and silently dropped a
PodDisruptionBudget. Tanka is the smallest and fastest toolchain here, about
0.1 s per render, at the cost of Jsonnet as the language. Both stop at
Kubernetes, and both consume Helm charts. The
[`config-tools` notes](https://github.com/kadet-hub/examples/tree/main/config-tools)
have the measurements.

## Kapitan

Kapitan keeps values in a YAML inventory of [classes](/glossary/#class) and [targets](/glossary/#target) and
renders them through [generators](/glossary/#generator), so the code that turns values into objects
is someone else's maintained, versioned artifact rather than templates in
your repository. One inventory drives Kubernetes manifests, Terraform and any
other file, and `${...}` lets any target reference a value from another
file. It writes files and leaves applying them to `kubectl`, Argo CD or
Flux; it has no release history like Helm's. It can render Helm charts,
Kustomize and Jsonnet as inputs, so adopting it does not mean rewriting
those.

kadet-hub lists Kapitan generators for Kubernetes and Terraform, each
version scanned, compiled in a sandbox and published as a signed OCI
artifact. [Recipes](/recipes/) combine them into replacements for popular
Bitnami charts, deployed and checked on a kind cluster in CI, and
[Kapitan generator vs Helm chart vs Kustomize](/guides/generator-helm-or-jinja2/)
covers the choice when you write one yourself.

## When Helm stays

Most vendors publish a Helm chart, Artifact Hub indexes them, and
`helm upgrade` and `helm rollback` keep release history in the cluster. For
third-party software a chart its vendor maintains is hard to beat. Helm also
handled the second app with the fewest changes in the example. The
alternatives above win where your own configuration grows: values that
depend on each other, several environments, or one source for Kubernetes
and infrastructure.
