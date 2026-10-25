---
title: "Keycloak on Kubernetes with Kapitan"
description: "Bitnami keycloak Helm chart alternative: a Kapitan inventory class for Keycloak on Kubernetes with the Keycloak Operator, CloudNativePG and cert-manager."
replaces: [keycloak]
operators: [Keycloak Operator, CloudNativePG, cert-manager]
check: the Keycloak is `Ready` and `/realms/master` answers 200 over TLS
lastmod: 2026-10-19
---
