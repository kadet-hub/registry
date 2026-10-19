---
title: "Redis on Kubernetes without Bitnami: Valkey with Kapitan"
description: "Bitnami redis Helm chart alternative: a Kapitan inventory class for Valkey, the BSD-licensed Redis fork, on Kubernetes, without an operator, checked on kind."
replaces: [redis]
operators: []
check: the StatefulSet is ready and `valkey-cli ping` answers `PONG`
---
