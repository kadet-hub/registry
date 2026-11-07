---
title: "External Secrets Operator with Vault AppRole and Kapitan refs"
layout: prose
description: "Which secret goes in a Kapitan ref and which in Vault: the AppRole secret ID as a gpg ref, an admin token synced from Vault and rotated, tested on kind."
lastmod: 2026-11-07
aliases: [/blog/external-secrets-operator-vault-kapitan/]
---

A [Kapitan](/glossary/#kapitan) project can keep every secret as a
[ref](/glossary/#ref), encrypted in Git and revealed at deploy time.
External Secrets Operator takes the other route. It reads a secret
manager such as Vault from inside the cluster and writes Kubernetes
Secrets from it. Most clusters end up with both, and then each secret
needs a place. This guide puts one app on both and shows where each of its
secrets goes and why.

The app is Vaultwarden, from the [vaultwarden](/recipes/vaultwarden/)
[recipe](/glossary/#recipe) 1.0.0. Its admin token comes from Vault
through External Secrets. External Secrets logs in to Vault with an
AppRole, and the AppRole's secret ID is the one secret the
[inventory](/glossary/#inventory) carries, as a gpg ref. The project is
[secrets-end-to-end](https://github.com/kadet-hub/examples/tree/main/secrets-end-to-end)
in kadet-hub/examples. Its `check` script runs it on a new
[kind](/glossary/#kind) cluster on every change and once a week, with
External Secrets 2.14.0, Vault 2.2.1 and Kapitan 0.36.3. It writes a new
admin token to Vault and fails unless Vaultwarden takes it after a
restart.

## Which secret goes where {#split}

A ref changes with a commit. Its ciphertext lives in the repository's
`refs/` directory, and a new value reaches the cluster with the next
compile and deploy, which reveal it. A secret in Vault changes without
the repository. External Secrets reads it again every refresh interval
and rewrites the Secret, and nobody compiles or commits.

So the question for each secret is who changes it and when. A secret
that whoever runs Vault rotates belongs in Vault. A secret that has to
exist before External Secrets can read anything cannot come from
External Secrets, and belongs in a ref. That second kind is the bootstrap
secret, sometimes called secret zero.

The example has one of each:

| | AppRole secret ID | Vaultwarden admin token |
|---|---|---|
| Kind | bootstrap | runtime |
| Issued by | Vault, once | whoever runs Vault, at every rotation |
| Kept in | `refs/`, encrypted for a gpg key | Vault, `secret/vaultwarden` |
| Reaches the cluster | `kapitan refs --reveal` in the deploy | External Secrets, every 10 seconds |
| A new value needs | a new ref, a commit and a deploy | `vault kv put` and a restart of Vaultwarden |

External Secrets needs the secret ID to log in to Vault, so it cannot
fetch the secret ID from Vault. The admin token, and any secret the app
later keeps in Vault, comes through that login.

## How External Secrets logs in to Vault {#auth}

External Secrets' Vault provider has several login methods, and they
differ in what the inventory has to carry. Only AppRole is tested here.

| Method | Secret in the inventory | Note |
|---|---|---|
| token | the Vault token | Tokens other than root tokens expire with their TTL unless renewed. |
| AppRole | the secret ID; the role ID is not secret | Each login returns a token of its own with `token_ttl`. The secret ID can be issued without expiry. |
| Kubernetes or JWT auth | none | Vault checks a ServiceAccount token of the pod, through the cluster's TokenReview API or its signing keys. |

Kubernetes or JWT auth leaves no secret in the inventory, and the split
reduces to the right column of the first table. In return, Vault has to
reach the cluster's API server or hold its signing keys, which a Vault
that another team runs outside the cluster may not offer. AppRole works
from anywhere that reaches Vault, and its one secret has to get into the
cluster some other way. Here that way is the ref.

## What a refs backend needs {#backends}

A ref is a tag such as `?{gpg:vaultwarden/vault-secret-id}` in the
inventory and a file of the same path under `refs/`. Three steps touch
it, and they need different access:

| Step | gpg | vaultkv, vaulttransit, cloud KMS |
|---|---|---|
| `kapitan refs --write`, or the first compile of a ref with a function such as `\|\|random:str` | the recipients' public keys | a Vault token, or KMS credentials |
| `kapitan compile` without `--reveal`, for refs that exist | nothing | nothing |
| `kapitan refs --reveal` or `kapitan compile --reveal` | a recipient's private key | the backend's decrypt or read access |

The middle row is the one that is easy to get wrong. Kapitan reads an
existing ref file and writes its tag with a short hash, so a CI job can
compile a repository with a committed `refs/` directory and no
credentials at all. A pull request to Kapitan's docs,
[kapicorp/kapitan#1646](https://github.com/kapicorp/kapitan/pull/1646),
adds this to the refs documentation. Its author tested gpg, vaultkv,
vaulttransit, gkms, awskms and azkms. `check` tests gpg, with an empty
keyring, as below. The `base64` and `plain` backends need
nothing at any step and encrypt nothing, so their ref files are as secret
as the values.

## The target {#target}

`inventory/targets/vaultwarden.yml`:

```yaml
classes:
  - recipes.vaultwarden
parameters:
  namespace: vaultwarden
  kapitan:
    vars:
      target: vaultwarden
    secrets:
      gpg:
        recipients:
          - name: secrets-end-to-end@example.com
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/external-secrets:1.0.6@sha256:184e8a60f92c0c09eae32973ceaf909b2da53457e88233161ffb90c4b9a63e60
        output_path: lib/external-secrets
    compile:
      # The recipe's Secret vaultwarden. External Secrets writes a Secret of
      # that name from Vault.
      - input_type: remove
        input_paths:
          - compiled/${kapitan.vars.target}/manifests/vaultwarden/vaultwarden-secret.yml
        output_path: .
      - input_type: kadet
        input_paths: [lib/external-secrets]
        output_path: manifests/
        output_type: yml
  applications:
    vaultwarden:
      domain: https://vaultwarden.example.com
      # The recipe requires it. Its Secret is removed above.
      admin_token: from-vault
  generators:
    kubernetes:
      secrets:
        vault-approle:
          string_data:
            secret-id:
              value: ?{gpg:vaultwarden/vault-secret-id}
    external_secrets:
      secretstores:
        vault:
          spec:
            provider:
              vault:
                server: http://vault.vault.svc.cluster.local:8200
                path: secret
                version: v2
                auth:
                  appRole:
                    path: approle
                    roleId: vaultwarden
                    secretRef:
                      name: vault-approle
                      key: secret-id
      externalsecrets:
        vaultwarden:
          store: vault
          refresh_interval: 10s
          spec:
            data:
              - secretKey: ADMIN_TOKEN
                remoteRef:
                  key: vaultwarden
                  property: admin_token
```

The [kubernetes](/generators/kubernetes/) generator, which the recipe
pins, renders the Secret `vault-approle` with the ref. The
[external-secrets](/generators/external-secrets/) generator renders the
SecretStore `vault` and the ExternalSecret `vaultwarden`. It renders
External Secrets' custom resources only, so `check` installs External
Secrets itself from the project's release manifest, as the
[cluster add-ons post](/blog/kubernetes-cluster-add-ons/) does.

The recipe expects its admin token as a ref and renders a Secret
`vaultwarden` with the key `ADMIN_TOKEN`, which its StatefulSet reads.
Here that Secret comes from External Secrets. The target drops the
recipe's file with Kapitan's `remove` input, and the ExternalSecret
writes a Secret of the same name with the same key, so the StatefulSet
stays as the recipe renders it. The recipe still requires the parameter
`admin_token`, which therefore holds a placeholder that reaches no
output. Without the `remove` entry, the output would hold the recipe's
Secret `vaultwarden` with the placeholder, and every deploy would apply
it over the Secret that External Secrets writes.

The gpg recipient is named by its user ID. Kapitan looks the key up when
it writes a ref and stores the key's fingerprint in the ref file, so a
later compile does not look anything up.

## Vault {#vault}

`vault-server.yaml` stands in for a Vault outside the cluster. It runs
Vault's dev server, which keeps everything in memory and mounts KV
version 2 at `secret/`, behind a ClusterIP Service. Its root token comes
from a Secret that `check` creates with a random value, and it starts
with `-dev-no-store-token`, so it writes no token file. Nothing outside
the cluster reaches this Vault. `check` runs the vault CLI inside the
server's container with `kubectl exec`. Vault is licensed BUSL-1.1.

`check` sets Vault up as its admin would:

```sh
vault auth enable approle
vault policy write vaultwarden - <<'EOF'
path "secret/data/vaultwarden" {
  capabilities = ["read"]
}
EOF
vault write auth/approle/role/vaultwarden token_policies=vaultwarden token_ttl=10m
vault write auth/approle/role/vaultwarden/role-id role_id=vaultwarden
secret_id=$(vault write -f -field=secret_id auth/approle/role/vaultwarden/secret-id)
printf %s "$token" | vault kv put secret/vaultwarden admin_token=-
```

The policy reads the one path of the admin token. The role ID is set to
`vaultwarden`, so the SecretStore can name it, and Vault issues the
secret ID. `check` reads the role back:

```console
Vault: AppRole vaultwarden with secret_id_ttl 0, token_ttl 600, policies vaultwarden, admin token in secret/vaultwarden
```

`secret_id_ttl` 0 is the AppRole default and means that the secret ID
does not expire. A secret ID that expires would turn the ref into a
secret to rotate as well.

## Writing the ref {#ref}

The secret ID goes into the ref through stdin, encrypted for the
recipient the target lists:

```sh
printf %s "$secret_id" | kapitan refs --write gpg:vaultwarden/vault-secret-id -t vaultwarden -f -
```

`-t vaultwarden` takes the recipients from the target. The ref file
`refs/vaultwarden/vault-secret-id` holds the ciphertext and the
recipient's fingerprint, here from a local run with the ciphertext cut:

```yaml
data: hF4DX62rRiT3KU4SAQdA...
encoding: original
recipients:
- fingerprint: FDD8F7AB904048215026F28F7AFFF9D3B29E7B57
type: gpg
```

`check` creates a gpg key in a keyring of its own for each run, so its
refs go to a temporary directory. A repository commits `refs/`, and the
private key stays with whoever deploys.

## Compiling without the key {#compile}

`check` compiles with `GNUPGHOME` pointing to an empty keyring. The
compiled Secret holds the ref's tag:

```yaml
apiVersion: v1
kind: Secret
metadata:
  labels:
    name: vault-approle
  name: vault-approle
  namespace: vaultwarden
stringData:
  secret-id: ?{gpg:vaultwarden/vault-secret-id:75893683}
type: Opaque
```

The eight characters after the last colon are the start of a SHA-256
over the ref's path and ciphertext. A new value changes them, so a diff
of `compiled/` shows that a ref changed without showing the value.
`check` fails if the secret ID or its base64 encoding appears anywhere in
`compiled/`, and if `kapitan refs --reveal` succeeds with the empty
keyring. From the CI run:

```console
compiled without a gpg key: 5 files
EX-26: compiled/vaultwarden/manifests/vaultwarden/vault-approle-secret.yml holds ?{gpg:vaultwarden/vault-secret-id:75893683}, not the secret ID
EX-26: reveal without the key fails: GPGError: no secret key
```

## Deploying {#deploy}

The deploy reveals with the key and pipes into `kubectl apply`, so the
revealed manifests are not written to disk:

```sh
kapitan refs --reveal -f compiled/vaultwarden | kubectl apply -f -
```

`check` applies the Secret `vault-approle`, the SecretStore and the
ExternalSecret first and the rest once the Secret `vaultwarden` exists.
Applied together, Vaultwarden's pod can start before External Secrets has
written its Secret and wait in `CreateContainerConfigError` until it
has. The SecretStore and the ExternalSecret as compiled:

```yaml
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata:
  labels:
    name: vault
  name: vault
  namespace: vaultwarden
spec:
  provider:
    vault:
      auth:
        appRole:
          path: approle
          roleId: vaultwarden
          secretRef:
            key: secret-id
            name: vault-approle
      path: secret
      server: http://vault.vault.svc.cluster.local:8200
      version: v2
---
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  labels:
    name: vaultwarden
  name: vaultwarden
  namespace: vaultwarden
spec:
  data:
    - remoteRef:
        key: vaultwarden
        property: admin_token
      secretKey: ADMIN_TOKEN
  refreshInterval: 10s
  secretStoreRef:
    kind: SecretStore
    name: vault
```

`key: vaultwarden` is the path below the KV mount `secret`, and the
provider adds the `data/` of KV version 2 itself. From the CI run:

```console
EX-26: External Secrets logged in with the revealed secret ID and wrote the admin token into the Secret vaultwarden in 1s
  SecretStore: Ready True, Valid: store validated
  ExternalSecret: Ready True, SecretSynced: secret synced
  Secret vaultwarden: keys ADMIN_TOKEN, owner ExternalSecret/vaultwarden
EX-26: admin login with the token from Vault: 200
```

The owner reference makes the ExternalSecret the Secret's controller.

## Rotating the admin token {#rotation}

`check` writes a new token to Vault with `vault kv put` and waits for
the Secret. Then it logs in to Vaultwarden's admin page with both tokens,
restarts Vaultwarden and logs in again:

```console
EX-26: the Secret vaultwarden holds the new token 10s after it was written to Vault
EX-26: admin login with the new token, before the restart: 401
EX-26: admin login with the old token, before the restart: 200
restarted in 4s
EX-26: admin login with the new token, after the restart: 200
EX-26: admin login with the old token, after the restart: 401
```

The Secret follows within the refresh interval, and Vaultwarden does
not. It reads `ADMIN_TOKEN` from its environment, and the kubelet sets
the environment from the Secret when it starts the container. Until the
restart, the old token logs in and the new one gets 401. After `kubectl
rollout restart statefulset/vaultwarden` it is the other way round.

External Secrets does not restart pods. A rotation that has to take
effect without a person needs a controller that restarts a workload when
its Secret changes, or an app that reads the value from a mounted file
when it uses it. Neither is tested here. Settings saved on Vaultwarden's
admin page go to `config.json` on its volume and take precedence over the
environment, so a token saved there no longer follows Vault.

Vaultwarden answers the fourth admin login from one address within 300
seconds with 429 Too Many Requests, by its defaults
`ADMIN_RATELIMIT_MAX_BURST` 3 and `ADMIN_RATELIMIT_SECONDS` 300. The first
local run logged in four times before the restart and failed on that.
`check` now logs in three times per pod start.

## What the CI run showed {#ci}

[Run 42003380730](https://github.com/kadet-hub/examples/actions/runs/42003380730)
of the examples workflow tested commit `3343fcf` of
[kadet-hub/examples#146](https://github.com/kadet-hub/examples/pull/146)
on 5 November 2026, on GitHub's `ubuntu-24.04` runner, with the kind node
image `kindest/node:v1.37.0`. The durations below are what `check`
printed, in whole seconds, or come from the log's timestamps.

Verifying index serial 113, the recipe and the two generators and
pulling them took 14 seconds. kind had the cluster ready 38 seconds
later. External Secrets and Vault were available 33 seconds after that,
and setting up Vault took about one second. Creating the gpg key and
writing the ref took 7 seconds, with uv installing Kapitan for the first
`uv run`. The compile without the key took 3.

External Secrets wrote the Secret `vaultwarden` one second after the
ExternalSecret was applied. Vaultwarden was ready and took the first
login 9 seconds later. The new token reached the Secret 10 seconds after
it was written to Vault, the full refresh interval. Two local runs took 3
and 7 seconds, depending on where in the interval the write fell. The
restart took 4 seconds, and the whole check 125.

## What it leaves out {#not-tested}

The admin token is stored in Vault as plain text, and Vaultwarden logs a
notice about it at every start. Vaultwarden also accepts an Argon2id PHC
string of the token, which the recipe's README recommends, so that the
Secret holds only a hash. That is not tested here.

Also not tested: Vault's Kubernetes and JWT auth, rotating the secret
ID, ref backends other than gpg, a reveal inside Argo CD, and a Vault
outside the cluster behind TLS. The
[Argo CD plugin post](/blog/argocd-config-management-plugin-kapitan/#refs-and-secrets)
covers what a reveal in Argo CD's repo server would expose.
