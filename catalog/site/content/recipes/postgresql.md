---
title: "PostgreSQL on Kubernetes without Bitnami, with Kapitan"
description: "Bitnami postgresql Helm chart alternative: a Kapitan inventory class for PostgreSQL on Kubernetes with CloudNativePG, also for postgresql-ha, checked on kind."
replaces: [postgresql, postgresql-ha]
operators: [CloudNativePG]
check: the Cluster is `Ready` and `select 1` runs as the app user through the pooler
lastmod: 2026-10-19
---
