---
title: Bitnami chart alternatives, chart by chart
layout: prose
description: What replaces the frozen Bitnami charts for PostgreSQL, RabbitMQ, Kafka, Keycloak, Grafana, Loki, Thanos, Argo CD, cert-manager and kube-prometheus.
---

Bitnami stopped publishing new images and charts to Docker Hub on 28
August 2025
([bitnami/containers#83267](https://github.com/bitnami/containers/issues/83267)).
The packaged charts stay at `docker.io/bitnamicharts` without updates, and
the versioned images moved to `docker.io/bitnamilegacy`, which is meant
only for migrations. A chart pinned today keeps deploying images that no
longer get security fixes.

For most of the popular charts the replacement is the operator the
project itself maintains, with the project's own images. That splits the
job in two: installing the operator and its CRDs, which the project
documents, and writing the custom resources for each instance, which is
where a Kapitan generator renders reviewed YAML from inventory parameters.
The generators below render custom resources only; none installs an
operator.

## The replacements

Facts checked against each project's release pages and install docs on
18 October 2026.

| Bitnami chart | Replacement | Images | Generator |
|---|---|---|---|
| `postgresql`, `postgresql-ha` | [CloudNativePG](https://cloudnative-pg.io/docs/1.30/installation_upgrade) | `ghcr.io/cloudnative-pg/cloudnative-pg`, `ghcr.io/cloudnative-pg/postgresql` | [cloudnative-pg](/generators/cloudnative-pg/) |
| `rabbitmq`, `rabbitmq-cluster-operator` | [RabbitMQ Cluster Operator](https://www.rabbitmq.com/kubernetes/operator/install-operator) and [Messaging Topology Operator](https://www.rabbitmq.com/kubernetes/operator/install-topology-operator) | `ghcr.io/rabbitmq/cluster-operator`, `ghcr.io/rabbitmq/messaging-topology-operator`, `rabbitmq` (Docker Official Image) | [rabbitmq](/generators/rabbitmq/) |
| `kafka` | [Strimzi](https://strimzi.io/docs/operators/latest/deploying) | `quay.io/strimzi/operator`, `quay.io/strimzi/kafka` | [strimzi](/generators/strimzi/) |
| `keycloak` | [Keycloak Operator](https://www.keycloak.org/operator/installation) | `quay.io/keycloak/keycloak-operator`, `quay.io/keycloak/keycloak` | [keycloak](/generators/keycloak/) |
| `grafana`, `grafana-operator` | [Grafana Operator](https://grafana.github.io/grafana-operator/docs/installation/) | `ghcr.io/grafana/grafana-operator`, `docker.io/grafana/grafana` | [grafana](/generators/grafana/) |
| `grafana-loki` | [Loki Operator](https://loki-operator.dev/docs/prologue/quickstart.md/) | `docker.io/grafana/loki-operator`, `docker.io/grafana/loki` | [loki](/generators/loki/) |
| `thanos` | [Thanos Operator](https://github.com/thanos-community/thanos-operator/blob/main/docs/installation.md) | `quay.io/thanos/thanos-operator`, `quay.io/thanos/thanos` | [thanos](/generators/thanos/) |
| `argo-cd` | [Argo CD](https://argo-cd.readthedocs.io/en/stable/operator-manual/installation/) | `quay.io/argoproj/argocd` | [argocd](/generators/argocd/) |
| `cert-manager` | [cert-manager](https://cert-manager.io/docs/installation/) | `quay.io/jetstack/cert-manager-controller`, `-webhook`, `-cainjector` | [certmanager](/generators/certmanager/) |
| `kube-prometheus` | [Prometheus Operator](https://prometheus-operator.dev/docs/getting-started/installation/) | `quay.io/prometheus-operator/prometheus-operator`, `quay.io/prometheus/prometheus`, `quay.io/prometheus/alertmanager` | [prometheus-operator](/generators/prometheus-operator/) |

## Where the install differs from a chart

CloudNativePG, Strimzi, Argo CD, cert-manager and the Prometheus Operator
publish release manifests for `kubectl apply` next to a Helm chart, so
the operator can come from the release YAML pinned by version and the
instances from the generator.

RabbitMQ publishes release manifests and a kubectl plugin but no Helm
chart of its own. Its install page sends Terraform and OpenTofu users to
`oci://registry-1.docker.io/bitnamicharts`, which is the frozen catalog
this page is about; the release manifests avoid it.

The Loki Operator has neither a Helm chart nor release manifests. Outside
OpenShift it installs through OLM from the OperatorHub.io bundle, whose
channel is alpha, or with `make deploy` from a checkout of
[grafana/loki](https://github.com/grafana/loki/tree/main/operator).

The Thanos Operator has no release and no tag. Its images are built from
`main`, its install is a bundle from the `main` branch, and its README
says the APIs are in alpha state. Until it releases, the `ThanosRuler`
of the Prometheus Operator, which the
[prometheus-operator](/generators/prometheus-operator/) generator renders,
is the released alternative for rule evaluation.

The Keycloak Operator's Helm chart is marked experimental; its install
page recommends OLM, and the `kubectl apply -k` route takes a tagged
version of `keycloak/keycloak-k8s-resources`. The Argo CD Helm chart is
maintained by the community in argo-helm, not by the Argo CD project, and
the kube-prometheus Helm chart by prometheus-community.

## Charts without a generator yet

`redis`, `mongodb` and `mysql` have no generator on kadet-hub yet.
[Wanted generators](/wanted/) lists the open requests; a 👍 there or a new
request is how one gets prioritised.

## Moving one release

A migration per chart follows the same order:

1. Install the operator next to the Bitnami release, from its pinned
   release manifest or chart.
2. Describe the instance in the inventory and render it with the
   generator; review the YAML in the pull request.
3. Move the data with the project's own tool: `pg_dump` or CloudNativePG's
   `bootstrap.initdb.import`, shovels or federation for RabbitMQ,
   MirrorMaker 2 for Kafka, a realm export for Keycloak.
4. Switch clients, then uninstall the Bitnami release and delete its
   PersistentVolumeClaims once the old data is no longer needed.

[Verifying a generator before you pull it](/guides/supply-chain-security-for-kapitan-generators/)
covers checking the artifact's signature and provenance.
