# demo

Test fixture for the gate selftest: a recipe with a vendored CRD from a
compose source, Miniflux's, which it does not rebuild. check proves it at
`renders` without a comparison (REC-9).

Source: `https://github.com/miniflux/v2/blob/238c5614e584ebc87894e7d9f10bc91373a0b2c2/contrib/docker-compose/basic.yml@sha256:2fc122f1b1c9cc550e0ae0b1d442a445d9a408909d0fcfdf55abb647c3856120`

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
