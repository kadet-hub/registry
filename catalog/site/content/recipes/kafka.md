---
title: "Kafka on Kubernetes without Bitnami, with Kapitan"
description: "Bitnami kafka Helm chart alternative: a Kapitan inventory class for Apache Kafka on Kubernetes in KRaft mode with the Strimzi operator, checked on kind."
replaces: [kafka]
operators: [Strimzi]
check: the Kafka is `Ready` and a message is produced and consumed
lastmod: 2026-10-19
---
