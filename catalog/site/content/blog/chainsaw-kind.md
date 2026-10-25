---
title: "Kyverno Chainsaw: Kubernetes e2e testing on kind in CI"
date: 2026-10-21
topics: [ci, testing, kapitan, verification]
description: "Kubernetes end-to-end testing with Kyverno Chainsaw on kind in GitHub Actions: six Kapitan recipes, a fail-fast pod watcher, webhook races, measured timeouts."
---

The kadet-hub examples repository deploys six [recipes](/glossary/#recipe)
to a new kind cluster on every pull request and checks them with
[Chainsaw](https://kyverno.github.io/chainsaw/0.2.15/) 0.2.15. A bash
script creates the cluster and installs the operators; a Chainsaw test per
recipe asserts the status of the deployed resources and then uses the
software. Two things had to be added around Chainsaw: a pod watcher that
stops a broken run within seconds instead of at a timeout, and a retry of
every apply until the admission webhooks accept it. This post shows both,
the CI failures that shaped them, and what the timeouts are based on.

A recipe is a [Kapitan](/glossary/#kapitan) [class](/glossary/#class) that
replaces a Bitnami chart with kadet-hub [generators](/glossary/#generator),
for example PostgreSQL on CloudNativePG or Keycloak with the Keycloak
Operator. The [recipe pages](/recipes/) show each class and what the CI
asserts; the code is in
[kadet-hub/examples](https://github.com/kadet-hub/examples/tree/main/recipes).

## Who owns what

`recipes/check <recipe>` owns everything before the test: it verifies the
signed [index](/glossary/#index) and each generator's
[attestation](/glossary/#attestation), compiles the recipe's
[target](/glossary/#target), runs kubeconform with the generators' schemas,
creates the kind cluster from a node image pinned by
[digest](/glossary/#digest), installs the operators from release manifests
pinned by URL and sha256, and applies the compiled output. Only then does it
call `chainsaw test --test-dir tests/<recipe>`.

The Chainsaw test owns what "works" means. For PostgreSQL that is the
CloudNativePG Cluster reporting `Ready`, the pooler Deployment having a
ready replica, and `select 1` returning `1` for the app user through the
pooler:

```yaml
spec:
  timeouts:
    assert: 6m
  namespace: databases
  steps:
    - try:
        - assert:
            resource:
              apiVersion: postgresql.cnpg.io/v1
              kind: Cluster
              metadata: {name: app-db}
              status:
                (conditions[?type == 'Ready']):
                  - status: "True"
        # ... the pooler Deployment has readyReplicas: 1
        - script:
            timeout: 1m
            content: |
              pass=$(kubectl -n databases get secret app-db-app -o jsonpath='{.data.password}' | base64 -d)
              kubectl -n databases exec app-db-1 -c postgres -- \
                env PGPASSWORD="$pass" psql -h app-db-pooler-rw -U app -d app -tAc 'select 1'
            check:
              ($error): ~
              (trim_space($stdout)): "1"
      catch:
        - events: {}
        - podLogs: {}
        - describe: {apiVersion: postgresql.cnpg.io/v1, kind: Cluster}
```

The parenthesised key is a JMESPath expression over the object's status,
which Chainsaw
[evaluates until the result is true or the operation timeout expires](https://kyverno.github.io/chainsaw/0.2.15/quick-start/assertion-trees/).
That is why the test needs no `kubectl wait`. The `catch` block
[runs only when the step fails](https://kyverno.github.io/chainsaw/0.2.15/quick-start/try-catch/)
and prints the namespace's events, the pod logs and the resource the test
waited for. A timed-out `kubectl wait` prints none of that.

The other five tests follow the same shape: Kafka produces and consumes a
message over mutual TLS with the KafkaUser's certificate, Keycloak answers
200 on `/realms/master` over TLS, Valkey answers `PONG` to `valkey-cli ping`
with its password, RabbitMQ passes `rabbitmq-diagnostics check_running`, and
PowerDNS answers an A record that external-dns wrote for an annotated
Service.

## The CI job

The workflow runs one job per recipe. Chainsaw, kind and kubectl are
downloaded at pinned versions and checked against sha256 sums from the
workflow's `env`:

```yaml
recipe:
  runs-on: ubuntu-24.04
  timeout-minutes: 15
  strategy:
    fail-fast: false
    matrix:
      recipe: [postgresql, keycloak, valkey, kafka, rabbitmq, external-dns-powerdns]
  steps:
    # ... checkout, then download oras, kubeconform, uv, kubectl, kind and
    # chainsaw and check them with sha256sum -c
    - name: recipes/check ${{ matrix.recipe }}
      env:
        GH_TOKEN: ${{ github.token }}
        RECIPE: ${{ matrix.recipe }}
      run: recipes/check "$RECIPE"
```

The CI job only calls the script, so `recipes/check keycloak` runs the same
steps on a laptop. `KEEP=1` keeps the cluster for inspection.

## Two Keycloak settings a test made visible

The Keycloak class pins the upstream image `quay.io/keycloak/keycloak:26.8.1`
and carries two settings with a comment each:

```yaml
            commonName: sso.example.com  # Keycloak rejects a certificate with an empty issuer DN
# ...
          image: quay.io/keycloak/keycloak:26.8.1
          spec:
            startOptimized: false  # the operator assumes a prebuilt image when image is set
```

With `image` set, the Keycloak Operator assumes a prebuilt, optimized image
and starts the server with `--optimized`. On the stock image the container
exits with "The '--optimized' flag was used for first ever
server start" and the pod goes into `CrashLoopBackOff`. The certificate
comes from a self-signed cert-manager Issuer, so its issuer DN is its
subject DN; with only `dnsNames` that DN is empty, which Keycloak rejects.

Neither shows up in a compile or a schema check. Both are valid manifests.

## Failing fast on a broken pod

An assert that cannot succeed waits for its full timeout. Before
[examples#10](https://github.com/kadet-hub/examples/pull/10) the timeouts
were 5 to 15 minutes per assert, so a pod in `CrashLoopBackOff` held the job
for up to 15 minutes and then reported a timeout on a status condition.

Chainsaw runs the operations of a test one after another and has none that
runs beside an assert
([API reference](https://kyverno.github.io/chainsaw/0.2.15/reference/apis/chainsaw.v1alpha1/)),
so the watch lives in `check`. It starts right after the kind cluster is
created and runs until Chainsaw ends, so it covers the operator installs
as well as the test. Every 10 seconds it lists the pods of all namespaces:

```bash
watch_pods() {
  local bad now seen=''
  while sleep 10; do
    bad=$(kubectl get pods -A -o json | jq -r '.items[]
      | select([.status.initContainerStatuses[]?, .status.containerStatuses[]?] | any(
          .restartCount > 3 or (.state.waiting.reason | IN("CrashLoopBackOff", "ImagePullBackOff",
            "CreateContainerConfigError", "InvalidImageName"))))
      | "\(.metadata.namespace) \(.metadata.name)"') || continue
    # EX-6: broken on two polls in a row; Argo CD's server briefly waits for a Secret.
    now=$bad
    bad=$(comm -12 <(sort <<<"$seen") <(sort <<<"$now"))
    seen=$now
    [[ -n $bad ]] || continue
    echo "EX-6: broken pods, stopping the check" >&2
    # ... kubectl describe pod and the container logs of each broken pod
    pkill -P $$  # check's children: the command it waits for and this watch
    return
  done
}
```

The watcher prints `kubectl describe pod` and the container logs itself
because of how Chainsaw 0.2.15 handles signals. `pkill` sends SIGTERM,
which stops Chainsaw at once, and its `catch` block does not run. SIGINT
would let `catch` run, but it does not interrupt an assert: Chainsaw keeps
polling until the assert timeout and only then fails.

`ErrImagePull` alone does not count as broken. A registry hiccup causes it
once, and a pull that keeps failing turns into `ImagePullBackOff` seconds
later, which the watcher does catch.

Two runs with a deliberate fault in examples#10, reverted before the
commit, show the effect. Valkey with an image tag that does not exist
failed about 10 seconds after Chainsaw started, with the registry's "not
found" event in the output. Keycloak without `startOptimized: false` failed
about 4 seconds after the first `CrashLoopBackOff`, with the `--optimized`
message from above.

## What the watcher found during installs

Until [examples#16](https://github.com/kadet-hub/examples/pull/16) the
watcher ran only beside Chainsaw, and an operator install that never
became ready ended at the 300-second timeout of `kubectl rollout status` or
`kubectl wait`, which prints only Deployment names. The sibling check for
[Argo CD and Flux](/guides/argocd-vs-flux/), which shares the watcher, timed
out that way in 3 of 4 CI runs, `main` included, with nothing but:

```text
timed out waiting for the condition on deployments/argocd-redis
timed out waiting for the condition on deployments/argocd-repo-server
timed out waiting for the condition on deployments/argocd-server
```

examples#16 starts the watcher at cluster creation and wraps every install
wait in `install_wait`, which on a timeout prints the namespace's events by
time, `kubectl get pods -o wide`, and the description and logs of every pod
that is not ready. A failing run on a pull request then stopped about a
minute after the cluster was up, on the redis pod in `ImagePullBackOff`,
and its events named the cause:

```text
Failed to pull image "public.ecr.aws/docker/library/redis:8.2.3-alpine": ...
unexpected status from GET request to
https://public.ecr.aws/v2/docker/library/redis/manifests/sha256:08ad0b1d...: 429 Too Many Requests
```

ECR Public throttles anonymous pulls, and the runners share IP addresses;
the pull had never failed locally.
[examples#18](https://github.com/kadet-hub/examples/pull/18) rewrites that
one image in the verified release manifest to
`mirror.gcr.io/library/redis:8.2.3-alpine` with the same digest, so the
content stays pinned. Pulling it before the install would not have helped,
because the manifest sets `imagePullPolicy: Always`.

The watcher in its new place also stopped two healthy Argo CD installs.
Argo CD's server and application controller wait with `CreateContainerConfigError`
until the `argocd-redis` Secret exists, which the redis pod's init
container creates; the watcher saw pods 13 seconds old with `secret
"argocd-redis" not found` and stopped the check. Since examples#18 a pod
counts as broken only when it is on the list in two polls in a row, which
moves the fail-fast bound from 10 to 20 seconds.

## Webhooks that are not ready when their rollout is

The first push to `main` after the recipes were merged failed the RabbitMQ
job. `kubectl rollout status` reported the RabbitMQ Cluster Operator rolled
out at 07:15:11.94, and 0.16 seconds later the apply of the
RabbitmqCluster failed:

```text
failed calling webhook "mrabbitmqcluster-v1beta1.kb.io": failed to call webhook:
Post "https://cluster-operator-webhook-service.rabbitmq-system.svc:443/mutate-rabbitmq-com-v1beta1-rabbitmqcluster?timeout=10s":
dial tcp 10.96.6.231:443: connect: connection refused
```

The Deployment has a readiness probe, but on another port: `/readyz` on
8081, while the webhook listens on 9443. A ready pod says nothing about the
webhook. Locally the same apply failed in 2 of 3 runs. cert-manager showed
the same gap in a later run: its webhook reported rolled out at
12:26:37.8, and 0.7 seconds later the Certificates in the RabbitMQ
operator's manifest were rejected with `failed calling webhook
"webhook.cert-manager.io"`.

The first fix, [examples#13](https://github.com/kadet-hub/examples/pull/13),
waited before every apply for a [server-side dry
run](/glossary/#server-side-dry-run) of the same files to pass. That cannot
work for a release manifest that creates its own Namespace: a dry run
stores nothing, so every namespaced object in it fails with `namespaces
"..." not found` (11 objects for cert-manager v1.21.2), and the loop always
ran out before the real apply. The race went away only through that delay,
about 90 seconds per operator; the Keycloak job grew from 212 to 388
seconds.

[examples#17](https://github.com/kadet-hub/examples/pull/17) repeats the
real apply instead. `kubectl apply` is idempotent, so a repeat changes
nothing that already exists:

```bash
apply() { # kubectl apply arguments
  local i
  for i in $(seq 30); do
    kubectl apply "$@" && return
    ((i < 30)) && sleep 2
  done
  return 1
}
```

The first CI run on `main` with it hit the cert-manager race again, 0.6
seconds after the rollout, and the repeat absorbed it within about 2
seconds. The Keycloak job went back to 226 seconds.

## Timeouts from measured durations

Each test sets `spec.timeouts.assert` once, to about three times the
recipe's measured Chainsaw duration in whole minutes and at least 3
minutes. The durations were measured locally; Chainsaw in CI turned out
faster for every recipe. The CI column is the range over six runs, the job
column the run on `main` after examples#17 and #18:

| Recipe | Chainsaw, local | Chainsaw, CI | `timeouts.assert` | Job, CI |
|---|---|---|---|---|
| valkey | 14 s | 6 to 8 s | 3m | 87 s |
| external-dns-powerdns | 46 s | 14 to 27 s | 3m | 95 s |
| rabbitmq | 79 s | 58 to 59 s | 4m | 175 s |
| kafka | 106 s | 71 to 77 s | 5m | 206 s |
| postgresql | 126 s | 69 to 74 s | 6m | 165 s |
| keycloak | 160 s | 63 to 89 s | 8m | 226 s |

The job's `timeout-minutes` went from 45 to 15. The longest jobs, Keycloak
and Kafka at under 4 minutes, spend most of it outside Chainsaw: the kind
cluster and the operators. A test that hangs fails at its assert timeout,
at most 8 minutes, and a broken pod within about 20 seconds.

## What it does not cover

Each run starts from an empty cluster. Upgrades of an operator or of a
recipe's pinned image are not tested, and neither is anything that needs
more than one kind node.

To run one recipe yourself, clone the examples repository and call
`recipes/check external-dns-powerdns`. It needs gh (authenticated), jq, oras, uv,
kubeconform, kind, kubectl, chainsaw and Docker; external-dns with PowerDNS
needs no operator.

Since [examples#66](https://github.com/kadet-hub/examples/pull/66) the
Valkey recipe lives in [kadet-hub/recipes](https://github.com/kadet-hub/recipes/tree/main/valkey),
where `check valkey --level deploys` compares it with the upstream chart on
kind and runs a smoke test script instead of a Chainsaw test.
