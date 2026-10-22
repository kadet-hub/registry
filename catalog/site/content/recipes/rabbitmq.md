---
title: "RabbitMQ on Kubernetes without Bitnami, with Kapitan"
description: "Bitnami rabbitmq Helm chart alternative: a Kapitan inventory class for RabbitMQ on Kubernetes with the RabbitMQ Cluster Operator, checked on kind."
replaces: [rabbitmq]
operators: [RabbitMQ Cluster Operator, cert-manager]
check: the RabbitmqCluster reports `AllReplicasReady`
lastmod: 2026-10-19
---
