# valkey

Valkey as a single instance with ACL authentication and a persistent volume,
rendered by the kadet-hub `kubernetes` generator 1.9.0 from the Valkey
project's own Helm chart 0.12.0 in its standalone mode.

Source: `oci://ghcr.io/valkey-io/valkey-helm/valkey:0.12.0@sha256:8d1e895e2cbd8052de6c94155379a8f5cde14ba5867b429e2b290555d5338820`

Level: `deploys`

The chart comes from [valkey-io/valkey-helm](https://github.com/valkey-io/valkey-helm),
tag `valkey-0.12.0`. Its release workflow pushes the same package to
ghcr.io as to the GitHub release, SHA-256
`64d43433d6b80addb012dd7c21a1bf674bf034dc51210b6bf8eae9ddaf83740f`.

## Replaces

This recipe replaces the `valkey` recipe of kadet-hub/examples, which stood
in for Bitnami's `redis` chart with a StatefulSet written in kadet-hub.
Moving from it changes these objects:

| kadet-hub/examples | This recipe |
|---|---|
| StatefulSet `valkey` with the claim template `data`, 8Gi | Deployment `valkey` with the PersistentVolumeClaim `valkey`, 8Gi |
| `--requirepass` from Secret `valkey`, key `password` | ACL user `default` with all permissions, password from Secret `valkey-auth`, key `default-password` |
| `--appendonly yes` as an argument | `appendonly yes` in `applications.valkey.config` |
| UID and GID 999 | UID and GID 1000, as the chart sets them |
| password ref with the `base64` backend in the class | password set by the target, with the ref backend of your choice |
| TCP readiness and liveness probes | `valkey-cli ping` as startup and liveness probe, no readiness probe |

The data of the StatefulSet's claim `data-valkey-0` is not moved. Copy it
into the new claim before deleting the old one.

## Include

```yaml
classes:
  - recipes.valkey
parameters:
  namespace: valkey
  kapitan:
    vars:
      target: valkey
  applications:
    valkey:
      password: <ref>
```

## Required parameters

`applications.valkey.password` must be set, as a ref with the backend of
your choice. Without it the compile stops with
`Interpolation key 'applications.valkey.password' not found`.

## Settings

| Chart value | Inventory |
|---|---|
| `image.tag` | `applications.valkey.version`, together with the digest in `components.valkey.image` |
| `auth.aclUsers.default.password` | `applications.valkey.password` |
| `valkeyConfig` | `applications.valkey.config` |
| `valkeyLogLevel` | `components.valkey.env.VALKEY_LOG_LEVEL` |
| `dataStorage.requestedSize` | `components.valkey.persistent_volume_claims.valkey.storage` |
| `dataStorage.className` | `components.valkey.persistent_volume_claims.valkey.storage_class` |
| `resources` | `components.valkey.resources` |
| `service.type` | `components.valkey.service.type` |
| `podAnnotations` | `components.valkey.pod_annotations` |
| `nodeSelector`, `tolerations`, `affinity` | `components.valkey.node_selector`, `components.valkey.tolerations`, `components.valkey.affinity` |

The pod annotations `checksum/initconfig` and `checksum/config` are the
chart's hashes for the values in `tests/values.yaml`. They do not change
with `applications.valkey.config`, so after changing it restart the pod with
`kubectl rollout restart deployment/valkey`.

The init script in the ConfigMap `valkey-init-scripts` is the chart's,
rendered for ACL authentication of the user `default` without TLS and
replicas. Chart values that change it, such as `tls`, `replica` or more
`auth.aclUsers`, are not settings of this recipe. The script is
BSD-3-Clause, and its license is in `valkey.yml.LICENSE`.

Any list set in the target is appended to the recipe's list. To replace
one, set the key to `~` in a class included after the recipe and the new
list in the target.

## Left out

The chart's test pod runs only inside `helm test`. `tests/smoke` checks the
same on the installed recipe. It is not rendered:
`Pod/valkey-test-auth-generated`.

## Proof

`check valkey --level deploys` with `tests/values.yaml` and
`tests/target.yml`, on kind `kindest/node:v1.37.0`. The seven objects
differ only in their selector scheme: the Deployment and the Service select
on `name`, the chart on `app.kubernetes.io/name` and `instance`. Both select
the same pods. The chart binds no role.

`tests/smoke` sends PING, SET and GET as the user `default` with the
password from the Secret, and expects PING without a password to be
refused.

## Replacing a Helm release

Not tested.

1. Delete the Deployment `valkey` with `--cascade=orphan`, because its
   selector changes.
2. Delete the release's Helm secrets `sh.helm.release.v1.valkey.*`.
3. Apply the recipe with `kubectl apply --server-side --force-conflicts`.
4. Once the recipe's pod is ready, delete the orphaned ReplicaSet.
