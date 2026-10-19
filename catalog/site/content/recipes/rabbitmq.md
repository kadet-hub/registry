---
title: "RabbitMQ on Kubernetes without Bitnami, with Kapitan"
description: A Kapitan inventory class for RabbitMQ on Kubernetes with the RabbitMQ Cluster Operator, in place of the Bitnami rabbitmq chart.
replaces: [rabbitmq]
operators: [RabbitMQ Cluster Operator, cert-manager]
check: the RabbitmqCluster reports `AllReplicasReady`
---
