# demo

Test fixture for the gate selftest: a recipe with a vendored CRD. The gate
pulls and renders podinfo's chart for it (REC-7), which it does not rebuild.

Source: `oci://ghcr.io/stefanprodan/charts/podinfo:6.9.2@sha256:971fef0d04d5b3d03d035701dad59411ea0f60e28d16190f02469ddfe5587588`

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
