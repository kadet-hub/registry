# demo

Test fixture for the gate selftest: a recipe with a vendored CRD.

Source: `oci://ghcr.io/example/charts/demo:1.0.0@sha256:0000000000000000000000000000000000000000000000000000000000000000`

Level: `deploys`

## Include

```yaml
classes:
  - recipes.demo
parameters:
  namespace: demo
```

## Required parameters

No parameter has to be set.
