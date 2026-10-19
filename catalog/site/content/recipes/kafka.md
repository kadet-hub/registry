---
title: "Kafka on Kubernetes without Bitnami, with Kapitan"
description: A Kapitan inventory class for Apache Kafka on Kubernetes in KRaft mode with Strimzi, in place of the Bitnami kafka chart, checked on kind.
replaces: [kafka]
operators: [Strimzi]
check: the Kafka is `Ready` and a message is produced and consumed
---
