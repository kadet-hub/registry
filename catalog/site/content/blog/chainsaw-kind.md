---
title: "Kyverno Chainsaw: Kubernetes e2e testing on kind in CI"
date: 2026-12-01
topics: [ci, testing, kapitan, verification]
description: "Kubernetes end-to-end testing with Kyverno Chainsaw on kind in GitHub Actions: six Kapitan recipes, a fail-fast pod watcher, webhook races, measured timeouts."
---

The kadet-hub examples repository deploys six [recipes](/glossary/#recipe)
to a new kind cluster on every pull request and checks them with
[Chainsaw](https://kyverno.github.io/chainsaw/0.2.15/) 0.2.15. A bash
script creates the cluster and installs the operators; a Chainsaw test per
recipe asserts the status of the deployed resources and then uses the
software. Two things had to be added around Chainsaw: a pod watcher that
stops a broken run within seconds instead of at the assert timeout, and a
wait for admission webhooks before every apply. This post shows both, the
failures that led to them, and what the timeouts are based on.

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
so the watch lives in `check`, next to the Chainsaw process. Every 10
seconds it lists the pods of all namespaces, which includes the operators:

```bash
watch_pods() { # chainsaw-pid
  local bad
  while sleep 10; do
    bad=$(kubectl get pods -A -o json | jq -r '.items[]
      | select([.status.initContainerStatuses[]?, .status.containerStatuses[]?] | any(
          .restartCount > 3 or (.state.waiting.reason | IN("CrashLoopBackOff", "ImagePullBackOff",
            "CreateContainerConfigError", "InvalidImageName"))))
      | "\(.metadata.namespace) \(.metadata.name)"') || continue
    [[ -n $bad ]] || continue
    echo "EX-6: broken pods, stopping the check" >&2
    # ... kubectl describe pod and the logs of the previous container
    kill "$1"
    return
  done
}
chainsaw test --test-dir "tests/$recipe" --no-color &
pid=$!
watch_pods "$pid" &
```

The watcher prints `kubectl describe pod` and the container logs itself
because of how Chainsaw 0.2.15 handles signals. `kill` sends SIGTERM, which
stops Chainsaw at once, and its `catch` block does not run. SIGINT would
let `catch` run, but it does not interrupt an assert: Chainsaw keeps
polling until the assert timeout and only then fails.

`ErrImagePull` alone does not count as broken. A registry hiccup causes it
once, and a pull that keeps failing turns into `ImagePullBackOff` seconds
later, which the watcher does catch.

Two runs with a deliberate fault, reverted before the commit, show the
effect. Valkey with an image tag that does not exist failed about 10
seconds after Chainsaw started, with the registry's "not found" event in
the output. Keycloak without `startOptimized: false` failed about 4 seconds
after the first `CrashLoopBackOff`, with the `--optimized` message from
above.

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

The operator's readiness probe in its 2.23.1 release manifest is `/readyz`
on port 8081; the webhook serves on port 9443. A ready pod says nothing
about the webhook. Locally the same apply failed in 2 of 3 runs.

The fix in examples#10 waited only before the final apply of the compiled
output. A later pull request that did not touch the recipes then failed in
the step before: cert-manager's webhook reported rolled out at
12:26:37.8, and 0.7 seconds later the Certificates in the RabbitMQ
operator's manifest were rejected with `failed calling webhook
"webhook.cert-manager.io"`.
[examples#13](https://github.com/kadet-hub/examples/pull/13) routes every
apply through one helper that waits for a [server-side dry
run](/glossary/#server-side-dry-run) of the same files:

```bash
apply() { # kubectl apply arguments
  for _ in $(seq 30); do
    kubectl apply --dry-run=server "$@" >/dev/null 2>&1 && break
    sleep 2
  done
  kubectl apply "$@"
}
```

A dry run goes through the admission webhooks like a real request, so it
fails while a webhook refuses connections. In the seven CI runs since, the
race has not come back.

The helper has a cost the logs show. A release manifest that creates its
own Namespace cannot pass a dry run on a fresh cluster: nothing is stored,
so every namespaced object in it fails with `namespaces "..." not found`
(11 objects for cert-manager v1.21.2). The loop then runs out after about
90 seconds and the real apply succeeds. In the Keycloak job the time from
creating the recipe's namespace until `check` waits for cert-manager's
rollout grew from 2 seconds before examples#13 to 94 seconds after, and the
whole job from 212 to 388 seconds. For the operator manifests the webhooks
get their time from the loop running out, not from a dry run that saw them
ready; only the final apply of the compiled output, whose namespaces exist
by then, waits the way the helper intends.

## Timeouts from measured durations

Each test sets `spec.timeouts.assert` once, to about three times the
recipe's measured Chainsaw duration in whole minutes and at least 3
minutes. The durations were
measured locally; Chainsaw in CI turned out faster for every recipe. The
CI column is the range over four runs, the job column the latest run on
`main`:

| Recipe | Chainsaw, local | Chainsaw, CI | `timeouts.assert` | Job, CI |
|---|---|---|---|---|
| valkey | 14 s | 7 to 8 s | 3m | 105 s |
| external-dns-powerdns | 46 s | 14 to 27 s | 3m | 101 s |
| rabbitmq | 79 s | 58 to 59 s | 4m | 345 s |
| kafka | 106 s | 71 to 74 s | 5m | 197 s |
| postgresql | 126 s | 69 to 74 s | 6m | 269 s |
| keycloak | 160 s | 63 to 89 s | 8m | 390 s |

The job's `timeout-minutes` went from 45 to 15. The longest job, Keycloak at
about 6.5 minutes, spends most of it outside Chainsaw: the kind cluster,
three operators and the dry-run waits above. A test that hangs now fails
at its assert timeout, at most 8 minutes, and a broken pod within the next
10-second poll.

## What it does not cover

The watcher starts together with Chainsaw. A pod that breaks while an
operator installs is only noticed when `kubectl rollout status` or
`kubectl wait` gives up after 300 seconds, and the timeout prints only
Deployment names.
The sibling check for [Argo CD and Flux](/guides/argocd-vs-flux/), which
uses the same watcher, shows how little that is: an Argo CD install on
`main` timed out after five minutes with three lines naming
`argocd-redis`, `argocd-repo-server` and `argocd-server`, while the same
check had passed in 143 seconds on its pull request.

Each run starts from an empty cluster. Upgrades of an operator or of a
recipe's pinned image are not tested, and neither is anything that needs
more than one kind node.

To run one recipe yourself, clone the examples repository and call
`recipes/check valkey`. It needs gh (authenticated), jq, oras, uv,
kubeconform, kind, kubectl, chainsaw and Docker; Valkey needs no operator
and is the fastest to try.
