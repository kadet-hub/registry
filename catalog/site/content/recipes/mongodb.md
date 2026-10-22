---
title: "MongoDB on Kubernetes without Bitnami, with Kapitan"
description: "Bitnami mongodb Helm chart alternative: a Kapitan inventory class for MongoDB Community Server (SSPL) on Kubernetes, without an operator, checked on kind."
replaces: [mongodb]
operators: []
check: the StatefulSet is ready and `mongosh` authenticates as root and gets `ok` from `ping`
lastmod: 2026-10-19
---
