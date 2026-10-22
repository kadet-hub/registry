---
title: "Helm chart vs operator: PostgreSQL installed both ways on kind"
date: 2026-10-22
topics: [helm, operators, kapitan]
description: "Helm chart vs operator, measured: PostgreSQL from the Bitnami chart and from CloudNativePG on kind, with write gaps on a lost primary and a config change."
---

A Helm chart writes objects when you run `helm install` or `helm upgrade`,
and then it is done. An operator runs in the cluster, watches a custom
resource and keeps acting on it. For a stateless app the difference
hardly matters. For a database it decides what happens when the primary
goes away at night.

This post installs PostgreSQL both ways on the same kind cluster and
measures three things: how long writes stop when the primary pod is
deleted, how long they stop when a parameter that needs a restart
changes, and what happens when someone deletes the Service that clients
use.

## Setup

One kind v0.33.0 cluster with a single node running Kubernetes 1.37.0,
Helm 4.3.1, and each setup in its own namespace:

- **Chart:** the Bitnami `postgresql` chart 18.12.14 from
  `oci://registry-1.docker.io/bitnamicharts/postgresql`, with
  `architecture=replication` and two read replicas. Its default image is
  `bitnami/postgresql:latest`, the only tag Bitnami still publishes for
  free. The [Bitnami post](/blog/bitnami/) covers that change.
- **Operator:** CloudNativePG 1.30.1 from its chart `cloudnative-pg`
  0.29.1, and one `Cluster` with three instances on
  `ghcr.io/cloudnative-pg/postgresql:18.6-system-trixie`, pinned by
  digest.

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: pg
spec:
  instances: 3
  imageName: ghcr.io/cloudnative-pg/postgresql:18.6-system-trixie@sha256:f7e00138159bb45d70b624ba25e446924cb3ed1bf366d13e936c3f81b914064e
  storage:
    size: 1Gi
```

A pod in each namespace inserts one row every 0.2 s through the write
Service (`pg-postgresql-primary` for the chart, `pg-rw` for the
operator), with a one-second connect timeout. A write gap is the longest
time between two successful inserts after the disruption. Each setup ran
three times on a fresh cluster.

## Results

| | Bitnami chart | CloudNativePG |
|---|---|---|
| Objects you install | 12 (2 StatefulSets, 4 Services, 2 NetworkPolicies, 2 PodDisruptionBudgets, a Secret, a ServiceAccount) | 22 for the operator, 11 of them CRDs, plus one `Cluster` |
| Cluster-wide objects | none | 11 CRDs, 3 ClusterRoles, a ClusterRoleBinding, a mutating and a validating webhook |
| Write gap, primary pod deleted | 13.4 to 15.3 s | 2.0 to 2.2 s |
| Write gap, `max_connections` changed | 13.4 to 14.6 s | 0.5 to 1.5 s |
| Write Service deleted | still missing 30 s later | recreated |

## The primary pod dies

With the chart, the read replicas stay replicas. Nothing promotes one, so
writes wait until the StatefulSet controller has created
`pg-postgresql-primary-0` again and PostgreSQL inside it has started. On a
node that already has the image cached that took 13 to 15 s. On a node
that has to pull the image first, or with a volume that has to move to
another node, it takes longer.

CloudNativePG noticed the missing primary and promoted `pg-2`; the event
reads `Failing over from pg-1 to pg-2`. It pointed the `pg-rw` Service
at the new primary, and writes resumed after about 2 s. The deleted pod came
back as a replica of `pg-2`.

Bitnami's `postgresql-ha` chart adds failover with repmgr and Pgpool. On
2026-10-22, its default images `bitnami/postgresql-repmgr` and
`bitnami/pgpool` had no tags left on Docker Hub, so it was not part of
this test.

## A parameter that needs a restart

`max_connections` only takes effect after a restart. With the chart,
`helm upgrade --reuse-values --set primary.extendedConfiguration='max_connections = 200'`
adds the ConfigMap `pg-postgresql-primary-extended-configuration` and a
checksum of it to the pod template, so the StatefulSet replaces the
primary pod. The gap was as long as for a deleted pod, because it is
the same event.

With the operator, the change is one field in the `Cluster`:

```yaml
spec:
  postgresql:
    parameters:
      max_connections: "200"
```

The operator replaced the replica pods first. Then it restarted
PostgreSQL on the primary in place, which is the default
`primaryUpdateMethod: restart`, and `pg-2` stayed primary. Writes stopped
for 0.5 to 1.5 s. Afterwards all three instances reported
`max_connections` as 200.

## Someone deletes the Service

After `kubectl delete service`, the chart's `pg-postgresql-primary` was
still missing 30 s later. Nothing in the cluster knows it should exist
until someone runs Helm again. The operator had recreated `pg-rw` within
the same 30 s. Argo CD with self-heal, or a Flux HelmRelease with
`driftDetection.mode: enabled`, would also put the Service back. Both are
off by default, and neither promotes a replica.

## What the operator costs

The operator is software you run and upgrade. It installs CRDs and
webhooks for the whole cluster, it needs RBAC to manage pods, Services and
Secrets in every namespace it watches, and an operator upgrade can roll
every database it manages. With a chart there is less to run, and `helm rollback` returns to a
previous set of objects, though not to previous data.

For PostgreSQL the trade favours the operator as soon as more than one
instance is involved. Failover, ordered restarts and scheduled backups,
which CloudNativePG runs through its Barman Cloud plugin, are the parts a
chart leaves to you. A stateless service with a maintained
chart and no day-2 operations gains little from an operator.

## Charts for the operator, YAML for the instances

The two are not exclusive. The operator itself installs from a chart, and
the `Cluster` above is plain YAML you can review. The
[cloudnative-pg](/generators/cloudnative-pg/) generator renders that
`Cluster` from a [Kapitan](/glossary/#kapitan) [inventory](/glossary/#inventory),
and the [PostgreSQL recipe](/recipes/postgresql/) installs the operator
from its pinned chart and deploys an instance to kind in CI.
[Bitnami chart alternatives](/guides/bitnami-chart-alternatives/) lists
the operator for the other popular charts.
