---
title: "Keycloak on Kubernetes without Bitnami, with Kapitan"
description: "Bitnami keycloak Helm chart alternative: a Kapitan inventory class for Keycloak on Kubernetes with the Keycloak Operator, CloudNativePG and cert-manager."
replaces: [keycloak]
operators: [Keycloak Operator, CloudNativePG, cert-manager]
check: the Keycloak is `Ready` and `/realms/master` answers 200 over TLS
---
