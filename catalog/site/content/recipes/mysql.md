---
title: "MySQL on Kubernetes without Bitnami, with Kapitan"
description: "Bitnami mysql Helm chart alternative: a Kapitan inventory class for MySQL Community Server (GPL-2.0) on Kubernetes, without an operator, checked on kind."
replaces: [mysql]
operators: []
check: the StatefulSet is ready and `select 1` runs as the app user in its own database
---
