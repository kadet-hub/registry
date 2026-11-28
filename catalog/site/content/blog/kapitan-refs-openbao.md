---
title: "Kapitan refs in OpenBao: CI and pods reveal without a gpg key"
date: 2026-11-30
topics: [kapitan, security, ci]
tools: [OpenBao, GnuPG, Kubernetes]
description: "Kapitan gpg refs moved to vaultkv refs in OpenBao, revealed by CI with AppRole and by a pod with OpenBao Kubernetes auth, tested on kind."
---

A [Kapitan](/glossary/#kapitan) [ref](/glossary/#ref) of the gpg backend
is a value encrypted for one or more gpg keys and committed under
`refs/`. Whoever reveals it needs the private key of one of those
recipients. On the workstation of the person who owns the key, that is
fine. A CI job that deploys, or a workload in the cluster that renders
manifests, needs a copy of a private key, and every copy decrypts every
ref encrypted for that key, the ones in the Git history included.

Kapitan's `vaultkv` backend moves the value out of the repository. The
ref file names a path and a key in a key-value store with Vault's API,
and a reveal reads the value from there with a token. OpenBao, the fork
of Vault under the MPL-2.0 license, has that API. Each consumer logs in
to OpenBao as itself: a CI job with an AppRole, a pod with its
ServiceAccount token. A policy decides what each of them may read.

This post moves two gpg refs to `vaultkv` refs and then deletes the gpg
key. The project is
[openbao-refs](https://github.com/kadet-hub/examples/tree/main/openbao-refs)
in kadet-hub/examples. Its `check` script runs it on a new
[kind](/glossary/#kind) cluster on every change and once a week, with
OpenBao 2.7.3, Kapitan 0.36.3 and the
[kubernetes](/generators/kubernetes/) generator 1.16.0. The generator
renders OpenBao, the app's Secret and a Job that reveals in the cluster.
`check` fails when a step below stops working.

## What a vaultkv ref file holds {#ref-file}

The app's Secret has two refs, `app/db-password` and `app/api-key`.
After the move, `refs/app/db-password` holds this, as the CI run printed
it:

```yaml
data: YXBwOmRiLXBhc3N3b3Jk
encoding: original
type: vaultkv
vault_params:
  addr: null
  always_latest: false
  auth: token
  cacert: null
  capath: null
  client_cert: null
  client_key: null
  crypto_key: null
  engine: kv-v2
  key: null
  mount: secret
  namespace: null
  skip_verify: true
```

`data` is base64 for `app:db-password`: the path `app` in the mount
`secret`, and the key `db-password` in that secret. The value is not in
the file. `vault_params` is the target's `kapitan.secrets.vaultkv`
block, filled up with the defaults of Kapitan's settings model. Kapitan
copies it into every ref file it writes and, on a reveal, takes the
settings from the file rather than from the inventory.

What the repository holds changes with it:

| | gpg ref | vaultkv ref |
|---|---|---|
| The value is in | the ref file, encrypted | OpenBao, `secret/app` |
| A reveal needs | the private key of a recipient | a token whose policy reads the path |
| A new value needs | a new ref file and a commit | a write to OpenBao |
| Lost for good with | the private keys of all recipients | OpenBao's data and its backups |

The last row is the price. A gpg ref lives in every clone of the
repository. A `vaultkv` ref is a pointer, and the values exist only in
OpenBao and in what backs it up.

## The target {#target}

`inventory/targets/app.yml`, without its comments:

```yaml
classes:
  - generators

parameters:
  kapitan:
    vars:
      target: app
    secrets:
      vaultkv:
        auth: token
        addr: null
        engine: kv-v2
        mount: secret
  namespace: app
  generators:
    kubernetes:
      namespaces:
        app:
          labels:
            pod-security.kubernetes.io/enforce: restricted
      secrets:
        app:
          string_data:
            DB_PASSWORD:
              value: ?{vaultkv:app/db-password}
            API_KEY:
              value: ?{vaultkv:app/api-key}
```

With `auth: token`, Kapitan takes the token from `VAULT_TOKEN`, or from
`~/.vault-token` when the variable is unset. Its vault client can also
log in with `userpass`, `ldap`, `approle` and `github`, but not with
Kubernetes or JWT auth (`kapitan/refs/vault_resources.py` in 0.36.3).
Since the auth type sits in every ref file, one type holds for every
consumer. With `token`, each consumer logs in its own way first and
passes the token on.

`addr: null` keeps the address out of the ref files. When the block does
not set `addr`, Kapitan's settings model fills it from `VAULT_ADDR` at
the time the ref is written, and a reveal then connects to the address
in the file, whatever `VAULT_ADDR` says. `check` shows this with a ref
written without a target, which takes its settings from the defaults and
the environment:

```console
probe ref file: addr: http://127.0.0.1:45505
EX-35: revealed with VAULT_ADDR=http://127.0.0.1:9 through the address in the file
```

Port 45505 was the local end of that run's `kubectl port-forward` to
OpenBao. Nothing listens on port 9, and the reveal still worked. Here
the runner reaches OpenBao through the port-forward and the pod through
the Service name, so each brings its own `VAULT_ADDR`. Where every
consumer reaches OpenBao by one URL, `addr` can be that URL instead.

The ref file also shows `skip_verify: true`, the model's default. Over
the plain HTTP of this example it makes no difference. Against an HTTPS
address, Kapitan does not check OpenBao's certificate unless the target
sets `skip_verify: false` and `cacert`, and that path then lands in
every ref file and has to exist on every consumer. TLS is not tested
here.

## Policies {#policies}

OpenBao runs as its dev server, which keeps everything in memory and
mounts a KV version 2 engine at `secret/`. `check` sets it up as an
admin would, with the `bao` CLI in OpenBao's container:

```sh
bao policy write app-write - <<'EOF'
path "secret/data/app" {
  capabilities = ["create", "read", "update"]
}
EOF
bao policy write app-read - <<'EOF'
path "secret/data/app" {
  capabilities = ["read"]
}
EOF
```

KV version 2 keeps the values under `data/`, so the policies name
`secret/data/app` where the CLI and the ref file say `secret/app`.
`app-write` is for whoever writes refs. Kapitan reads the secret, adds
its key and writes the whole secret back (`_encrypt` in
`kapitan/refs/secrets/vaultkv.py`), so the writer needs `read` as well.
`app-read` is for everyone who only reveals.

Before it reads anything, Kapitan checks the token with
`auth/token/lookup-self`, which OpenBao's `default` policy grants.
OpenBao adds `default` to the tokens an auth method issues unless the
role sets `token_no_default_policy=true`. `check` tries both ways of
getting this wrong:

```console
EX-35: default policy only: Permission Denied. make sure the token is authorised to access 'app' on Vault
EX-35: AppRole ci-strict without the default policy: Vault Authentication Error, check if token in env:VAULT_TOKEN is valid and not expired
```

The first token has only `default` and fails on the read. The second
comes from an AppRole with `app-read` and without `default`. It fails
before the read, with a message that blames the token although the token
is valid. Kapitan says Vault in its messages because the backend was
written for Vault's API. A role without `default` would have to grant
`auth/token/lookup-self` in its own policy, which `check` does not test.

## Moving the gpg refs {#move}

`check` starts where a repository with gpg refs stands: two refs,
encrypted for a key that `check` creates for the run. The move reveals
each ref with that key one last time and pipes the value into `kapitan
refs --write`, with a token of the policy `app-write`:

```sh
for ref in db-password api-key; do
  kapitan refs --reveal --ref-file "refs/app/$ref" |
    VAULT_TOKEN=$writer kapitan refs --write "vaultkv:app/$ref" -t app \
      --vault-path app --vault-key "$ref" -f -
done
```

`--vault-path` and `--vault-key` put both values into one secret,
`secret/app`, with a key each. The write replaces the gpg ref file of
the same name. The tags in the inventory therefore change only their
prefix, from `?{gpg:app/db-password}` to `?{vaultkv:app/db-password}`.
Then `check` deletes the gpg key and its keyring. From the CI run:

```console
gpg refs app/db-password and app/api-key written for app@example.com
EX-35: moved 2 refs to vaultkv in 4s; secret/app in OpenBao holds api-key, db-password, version 2
EX-35: gpg key deleted, 0 secret keys in GNUPGHOME from here on
```

KV version 2 keeps a version per write, and the two writes made version
2. No later step has a gpg key.

## Compiling without OpenBao {#compile}

The compile needs neither a token nor an address. Kapitan reads the
existing ref files and writes their tags into the output:

```console
compiled app without a token or address in 3s
EX-35: compiled/app/app/app-secret.yml holds ?{vaultkv:app/api-key:0819d5ee} ?{vaultkv:app/db-password:5c216fff}
```

The eight characters after the last colon are the start of a SHA-256
over the ref's path and its `data`. `check` fails if a value or its
base64 encoding appears anywhere in `compiled/`. A CI job that only
compiles, such as a pull request check, gets no OpenBao access at all.

## CI with AppRole {#approle}

The CI job logs in with an AppRole, whose role ID and secret ID it keeps
in its secret store:

```sh
bao auth enable approle
bao write auth/approle/role/ci token_policies=app-read token_ttl=10m
```

The job sends both IDs to the login on stdin, so they do not show on a
command line, and hands the token to Kapitan. The deploy pipes the
reveal into `kubectl apply`, so the revealed manifest is not written to
disk:

```sh
VAULT_TOKEN=$(jq -n '{role_id: env.ROLE_ID, secret_id: env.SECRET_ID}' |
  curl -fsS --data @- "$VAULT_ADDR/v1/auth/approle/login" | jq -er .auth.client_token)
export VAULT_TOKEN
kapitan refs --reveal -f compiled/app/app/app-secret.yml | kubectl apply -f -
```

From the CI run:

```console
AppRole token: policies app-read,default, ttl 600s
revealed in 1s
EX-35: the AppRole token revealed both refs, and the Secret app holds the values the gpg refs had
```

The token carries `app-read` and `default` and expires after ten
minutes. `check` compares the
Secret in the cluster with the values the gpg refs had.

The secret ID is now the CI job's secret, as a copied gpg key would
have been. It opens less: one role, whose tokens read one path for ten
minutes, and OpenBao can revoke it without a change to the repository.
Revoking is not tested here. A CI system that issues OIDC tokens, such
as GitHub Actions or GitLab CI, can log in with OpenBao's JWT auth and
keep no secret at all, which is not tested either.

## A pod with OpenBao Kubernetes auth {#kubernetes-auth}

A workload in the cluster needs no stored secret. It logs in with the
ServiceAccount token that Kubernetes mounts into the pod, and OpenBao
asks the API server, with a TokenReview, whom the token belongs to. For
that, OpenBao's own ServiceAccount is bound to the ClusterRole
`system:auth-delegator`. From `inventory/targets/openbao.yml`:

```yaml
  generators:
    kubernetes:
      rbac:
        openbao-tokenreview:
          cluster_role: system:auth-delegator
          cluster_wide: true
          service_accounts: [openbao/openbao]
  components:
    openbao:
      service_account: {create: true}
      automount_service_account_token: true
```

The generator mounts no ServiceAccount token unless a component asks
for it. OpenBao runs in the same cluster and reads the cluster's CA and
its own token from that mount, so its config needs only the API
server's address. The role binds one ServiceAccount in one namespace to
`app-read`:

```sh
bao auth enable kubernetes
bao write auth/kubernetes/config kubernetes_host=https://kubernetes.default.svc
bao write auth/kubernetes/role/deployer bound_service_account_names=deployer \
  bound_service_account_namespaces=deployer token_policies=app-read token_ttl=10m
```

The Job `reveal` stands in for a deployer in the cluster. It runs the
image `kapicorp/kapitan:0.36.3` as the ServiceAccount `deployer`, logs
in, and reveals the compiled Secret from a ConfigMap that holds it and
the two ref files in place of a checkout. Where a deployer would apply
the result, it prints a hash. From `inventory/targets/deployer.yml`:

```yaml
    reveal:
      type: job
      image: docker.io/kapicorp/kapitan:0.36.3@sha256:04b9ca04f5041851631fb1041fbafe37b1ca6c3ad99a81d6ccd40f5ebd20f857
      command: [sh, -ec]
      args:
        - |
          jwt=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
          VAULT_TOKEN=$(printf '{"role": "deployer", "jwt": "%s"}' "$jwt" |
            curl -fsS --max-time 30 --data @- "$VAULT_ADDR/v1/auth/kubernetes/login" |
            python3 -c 'import json, sys; print(json.load(sys.stdin)["auth"]["client_token"])')
          export VAULT_TOKEN
          echo "gpg secret keys: $(gpg --list-secret-keys --with-colons 2>/dev/null | grep -c '^sec' || true)"
          revealed=$(kapitan refs --reveal -f /checkout/compiled/app-secret.yml --refs-path /checkout/refs)
          echo "revealed sha256: $(printf '%s\n' "$revealed" | sha256sum | cut -d' ' -f1)"
      env:
        VAULT_ADDR: http://openbao.openbao.svc:8200
      service_account: {create: true, name: deployer}
      automount_service_account_token: true
```

The Job's log, and what `check` made of it:

```console
Job reveal finished after 14s, image pull included:
  gpg secret keys: 0
  revealed sha256: d45a9a05bf7ee025d183d624b5c64991f4a975ba3f4708717dc77f7c88348c92
EX-35: the Job revealed what CI revealed, sha256 d45a9a05bf7ee025d183d624b5c64991f4a975ba3f4708717dc77f7c88348c92
```

The image ships gpg, with an empty keyring. The hash equals the one of
the manifest that CI revealed, so the pod got the same values. A token
of the ServiceAccount `other` in the same namespace, which the role does
not name, gets no login:

```console
EX-35: ServiceAccount other on role deployer: 403 ["service account name not authorized"]
```

The [Argo CD plugin post](/blog/argocd-config-management-plugin-kapitan/#refs-and-secrets)
runs Kapitan in Argo CD's repo server, where such a reveal usually
happens. Logging in to OpenBao from there is not tested.

## A new value does not show in Git {#rotation}

`check` changes a value in OpenBao and compiles again:

```sh
printf %s "$new" | bao kv patch secret/app db-password=-
```

```console
EX-35: after bao kv patch, compiled/app is unchanged and the reveal holds the new value
```

The ref file names a path and a key, and neither changed, so the tags,
and with them everything in `compiled/`, stay as they were. The next
reveal returns the new value. A secret can be rotated without a commit,
and nothing in the repository records that it was. The new value reaches
the cluster with the next reveal and deploy, and a GitOps tool that
watches `compiled/` finds nothing to sync.

## What the CI run showed {#ci}

[Run 45555219510](https://github.com/kadet-hub/examples/actions/runs/45555219510)
of the examples workflow tested commit `ea7ae4a` of
[kadet-hub/examples#271](https://github.com/kadet-hub/examples/pull/271)
on 25 November 2026, on GitHub's `ubuntu-24.04` runner, with kind
v0.33.0 and the node image `kindest/node:v1.37.0`. The durations are
what `check` printed, in whole seconds, or come from the log's
timestamps.

Verifying index serial 148 and the generator and pulling it took 8
seconds. kind had the cluster ready 41 seconds after it started, and
OpenBao was ready 6 seconds after its manifests were applied. Starting the
port-forward and setting up the policies and both auth methods took
about 2.5 seconds, writing the
two gpg refs with a new key about 1.5, and the move 4. The compile took
3 seconds and the CI reveal 1. The Job finished 14 seconds after it was
applied, including the pull of the Kapitan image. The whole check took
93 seconds.

## What it leaves out {#not-tested}

OpenBao runs as a dev server here: in memory, unsealed, with a root
token that `check` creates. A real one needs storage, unsealing and
backups, and the first table makes the backups what decides whether the
refs survive. Also not tested: TLS between Kapitan and OpenBao, JWT auth
from a CI provider, revoking a secret ID or a token, audit devices, the
`vaulttransit` backend, which keeps the ciphertext in the ref file and
the key in OpenBao, and a reveal in Argo CD.

The [External Secrets post](/blog/external-secrets-operator-vault-kapitan/)
takes the other route for secrets that change at runtime: External
Secrets Operator reads Vault from inside the cluster, and the AppRole's
secret ID stays a gpg ref.
