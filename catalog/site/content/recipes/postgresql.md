---
title: "PostgreSQL on Kubernetes without Bitnami, with Kapitan"
description: A Kapitan inventory class for PostgreSQL on Kubernetes with CloudNativePG, in place of the Bitnami postgresql and postgresql-ha charts.
replaces: [postgresql, postgresql-ha]
operators: [CloudNativePG]
check: the Cluster is `Ready` and `select 1` runs as the app user through the pooler
---
