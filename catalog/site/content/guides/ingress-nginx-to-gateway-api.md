---
title: Migrate ingress-nginx to Gateway API with Kapitan
layout: prose
description: ingress-nginx is retired. Moving Kapitan targets from Ingresses to Gateway API routes, side by side, with the annotation mapping and the defaults that differ.
---

ingress-nginx is retired: best-effort maintenance ended in March 2026, and
the project no longer ships releases or security fixes
([announcement](https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/)).
Kubernetes recommends Gateway API as the successor. In a [Kapitan](/glossary/#kapitan) project
the move is an [inventory](/glossary/#inventory) change per [target](/glossary/#target), and Ingress and Gateway can
run side by side until DNS points at the new address.

## Before and after

With the [kubernetes generator](/generators/kubernetes/), an Ingress lives
under `parameters.ingresses`:

```yaml
parameters:
  ingresses:
    web:
      namespace: shop
      annotations:
        nginx.ingress.kubernetes.io/ssl-redirect: "true"
      hosts:
        - name: shop.example.com
          paths:
            - path: /
              path_type: Prefix
              backend_name: web
              port_name: http
```

The same host as a Gateway with the `services` shorthand renders an HTTPS
listener, an HTTP to HTTPS redirect route and the backend route:

```yaml
parameters:
  generators:
    kubernetes:
      gateways:
        public:
          namespace: gateway
          gateway_class: eg
          services:
            web:
              hostname: shop.example.com
              namespace: shop
              tls_secret: shop-example-com-tls
              cluster_issuer: letsencrypt
              redirect_status_code: 308
              backend:
                name: web
                port: 80
```

Keep both in the target while you test the Gateway on its own address,
switch DNS, then delete the `ingresses` entry. Rules the shorthand cannot
express go under `gateways.<gw>.routes`, and resources the generator does
not model, such as implementation policies, under
`generators.kubernetes.manifests`.

## Annotations

Most annotations have a Gateway API field, some only an implementation
extension. The kubernetes generator's README maps the common ones to the
Gateway API 1.6.3 standard channel and to the generator key that renders
each: [ingress-nginx annotations](https://github.com/kadet-hub/generators/blob/main/kubernetes/README.md#ingress-nginx-annotations).
[ingress2gateway](https://github.com/kubernetes-sigs/ingress2gateway)
converts many of them for existing clusters and warns about the rest; its
output is a useful cross-check for the inventory you write.

## Defaults that differ

The migration is not a rename. These behave differently even when a field
exists:

- **Redirect status.** ingress-nginx redirects to HTTPS with 308, which
  keeps the request method. The `services` shorthand defaults to 301; set
  `redirect_status_code: 308` to match. 308 is Extended support in Gateway
  API, so check that your implementation offers it.
- **Path rewrites.** `rewrite-target: /$2` with a capture group has no
  equivalent. The common case, stripping a prefix, is `URLRewrite` with
  `ReplacePrefixMatch` and an empty replacement.
- **Backend TLS.** `backend-protocol: HTTPS` does not verify the backend
  certificate by default. BackendTLSPolicy always does and needs a
  hostname and a CA.
- **CORS.** ingress-nginx allows any origin and credentials by default.
  The Gateway API CORS filter has no default origins, methods or headers,
  and caches preflights for 5 seconds unless you set `maxAge`.
- **Regex paths.** ingress-nginx matches case-insensitively and applies
  `use-regex` to every path of the host. Gateway API regex matches are
  implementation-specific.
- **Canary weights.** Weights are proportional: `canary-weight: "10"`
  becomes weight 90 on the main backend and 10 on the canary.

Body size limits, IP allowlists, external auth, session affinity and
snippets have no standard field. They need a policy of your Gateway
implementation, for example Envoy Gateway's BackendTrafficPolicy and
SecurityPolicy.

## Checking the result

Compile, then validate the routes against the Gateway API [CRDs](/glossary/#crd) before
anything reaches a cluster. [Server-side dry runs](/glossary/#server-side-dry-run) catch what the JSON
Schemas do not; see
[Validate Kubernetes custom resources against their CRDs](/guides/checking-custom-resources-against-crds/).
