---
title: "Redis on Kubernetes without Bitnami: Valkey with Kapitan"
description: A Kapitan inventory class for Valkey, the BSD-licensed Redis fork, on Kubernetes in place of the Bitnami redis chart, without an operator.
replaces: [redis]
operators: []
check: the StatefulSet is ready and `valkey-cli ping` answers `PONG`
---
