---
title: "n8n queue mode on Kubernetes: the webhook waits for a worker"
date: 2026-11-28
topics: [kapitan, helm, verification]
tools: [n8n, Valkey, PostgreSQL]
description: "n8n queue mode from a Kapitan recipe rebuilt from n8n's Helm chart, tested on kind: workers run every webhook execution, and with none the caller waits."
---

With both n8n workers scaled to zero, a call to an active production
webhook got no answer for 200 seconds. n8n-main had stored the execution
in PostgreSQL with the status `new` and put its ID on the queue in Valkey.
The execution ran 3 minutes and 53 seconds later, 10 seconds after a new
worker pod was created and half a minute before Kubernetes marked that pod
Ready.

That is queue mode as n8n documents it. The main instance "handles timers
and webhook calls, generating (but not running) a workflow execution", and
a worker picks the execution ID up from Redis and runs it
([Enable queue mode](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode)).
This post shows it on [kind](/glossary/#kind) with the
[recipe](/glossary/#recipe) [n8n](/recipes/n8n/) that kadet-hub publishes
for [Kapitan](/glossary/#kapitan). The tests below ran on 12 November
2026, with kind v0.33.0, the node image `kindest/node:v1.37.0` and Helm
v4.3.1.

## The recipe

n8n 1.0.1 runs n8n 2.45.5 and is rebuilt from n8n's Helm chart 1.18.0, the
chart of [n8n-io/n8n-hosting](https://github.com/n8n-io/n8n-hosting). It
renders with the [kubernetes](/generators/kubernetes/) generator 1.14.0.
The Deployment `n8n-main` has one replica and the Deployment `n8n-worker`
two. Both start the same image, the workers with `worker
--concurrency=10`. The flag sets how many jobs a worker runs in parallel,
and 10 is n8n's default. Only `n8n-main` has a Service.

The recipe includes two others. [postgresql](/recipes/postgresql/) renders
a CloudNativePG `Cluster` with PostgreSQL 18.6 for n8n's database, and
[valkey](/recipes/valkey/) runs Valkey 9.1.2 as the queue. postgresql
needs the CloudNativePG operator, which the recipe [cnpg](/recipes/cnpg/)
installs in a target of its own.

The queue settings come from the chart's values. Both Deployments read
them from the ConfigMap `n8n`:

```sh
grep -E 'EXECUTIONS_MODE|QUEUE_BULL_REDIS_(HOST|PORT)' compiled/n8n/manifests/n8n/n8n-config.yml
```

```text
  EXECUTIONS_MODE: queue
  QUEUE_BULL_REDIS_HOST: valkey
  QUEUE_BULL_REDIS_PORT: '6379'
```

`valkey` is the Service of the valkey recipe. It takes the place that
n8n's docs give to Redis.

## The target

The [target](/glossary/#target) below is the recipe's `tests/target.yml`,
the one the proof compiles:

```yaml
classes:
  - recipes.n8n
parameters:
  namespace: n8n
  kapitan:
    vars:
      target: n8n
  applications:
    # The key tests/values.yaml gives the chart.
    n8n:
      encryption_key: smoke-encryption-key
    valkey:
      password: smoke-password
    # One instance is enough for the proof.
    postgresql:
      instances: 1
```

`encryption_key` becomes `N8N_ENCRYPTION_KEY`. n8n encrypts the stored
credentials of workflows with it, and the docs page above asks for the
same key on the main instance and every worker. Both Deployments here read
it from the Secret `n8n`. Outside a test, set both values as a
[ref](/glossary/#ref) of an encrypting backend. The compile writes 17
files: 8 for n8n, 2 for postgresql and 7 for valkey.

The fetch inventory pins only n8n, at the version and digest of the signed
[index](/glossary/#index), release `index-142` of 12 November 2026:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/recipes/n8n:1.0.1@sha256:ea7c4597bf89cb94981a952aadc0c4f4d08066853d54b02bbcde477e87e05bf4
        output_path: inventory/classes/recipes/n8n
```

The index record of n8n 1.0.1 lists postgresql 1.1.1 and valkey 1.0.3
under `includes`. The consumer workflow in the registry's
[consumer docs](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md)
adds both at those digests.

The proof ran the recipes at commit `04879f4` of kadet-hub/recipes. There,
n8n and valkey match the tags of 1.0.1 and 1.0.3. postgresql is one
Renovate update past 1.1.1 and pins the
[cloudnative-pg](/generators/cloudnative-pg/) generator 1.1.2 instead of
1.1.0.

## What check compared with the chart

`check` in kadet-hub/recipes proves a recipe that replaces a chart on two
kind clusters. It renders the chart with the values of `tests/values.yaml`
on one and compiles the recipe with Kapitan 0.36.3 for the other. Both
outputs go through a server-side dry run, and check compares the objects
the API servers return. The local run of `check n8n --level deploys`
reported 6 objects outside RBAC on each side and 15 differences of two
kinds.

Twelve are the selector scheme. The chart selects pods by
`app.kubernetes.io/name`, `instance` and `component`, the recipe by
`name`:

```text
difference: Selector scheme: Deployment.apps/n8n/n8n-main spec.selector.matchLabels.app.kubernetes.io/component: chart "main", recipe <unset>
difference: Selector scheme: Deployment.apps/n8n/n8n-main spec.selector.matchLabels.name: chart <unset>, recipe "n8n-main"
```

The other three are `automountServiceAccountToken: true`, which the recipe
writes and the chart leaves to the API default of true. check then
reported `selectors: 3 select the same objects on both sides` and equal
permissions for the ServiceAccount `n8n` and for users bound to `view`,
`edit` and `admin`. The chart's Helm test, `Pod/n8n-test-connection`, is
not rendered.

## Who runs the execution

At the level `deploys`, check installs cnpg, deploys the recipe on its
cluster and runs `tests/smoke`. The script sets up the owner account,
activates a workflow with one Webhook node at the path `smoke` and calls
the webhook. It restarts `n8n-main` and calls the webhook again, so the
owner and the workflow have to come back from PostgreSQL. It passed:

```text
smoke: healthz and readiness of n8n-main and n8n-worker-76f9b5bf7c-4jcw4, n8n-worker-76f9b5bf7c-gzn6f, owner setup and login, webhook run by a worker, login and webhook after a restart of n8n-main
deploys: passed
```

The run took 405 seconds, both clusters and the image pulls included.
check was started with `--keep`, so the cluster stayed for the tests
below. The logs show which pod did what. `n8n-main` only queued:

```text
Enqueued execution 2 (job 2)
Execution 2 (job 2) finished
```

Each worker ran one of the two calls. `n8n-worker-76f9b5bf7c-4jcw4` logged
`Worker started execution 1 (job 1)`, and
`n8n-worker-76f9b5bf7c-gzn6f` logged
`Worker started execution 2 (job 2)` after the restart of `n8n-main`.

Before the first execution, both workers had restarted twice. The log of
the last exit ends in `connect ECONNREFUSED 10.96.197.81:5432`, the
address of the Service `postgresql-cluster-rw`, thrown from
`Worker.init`. Those exits were at 18:22:38 and 18:22:39, and the Cluster
turned Ready at 18:22:39. check waits for every rollout, so the restarts
cost time and did not fail the run.

## Zero workers

With the cluster kept, the workers went to zero:

```sh
kubectl scale deployment n8n-worker --replicas=0
kubectl wait --for=delete pod -l name=n8n-worker --timeout=120s
kubectl port-forward service/n8n-main 15678:5678 >/dev/null 2>&1 &
curl -sS --max-time 200 -w '\nHTTP %{http_code} in %{time_total}s\n' 'http://localhost:15678/webhook/smoke?probe=5'
```

```text
curl: (28) Operation timed out after 200000 milliseconds with 0 bytes received

HTTP 000 in 200.001101s
```

`n8n-main` logged `Enqueued execution 5 (job 5)`. The execution was in
PostgreSQL with the status `new` and no start time:

```sh
kubectl exec postgresql-cluster-1 -c postgres -- psql -U postgres -d app -c 'select id, status, "createdAt", "startedAt", "stoppedAt" from execution_entity where id >= 5 order by id'
```

```text
 id | status |         createdAt          | startedAt | stoppedAt 
----+--------+----------------------------+-----------+-----------
  5 | new    | 2026-11-12 18:29:14.398+00 |           | 
(1 row)
```

The queue in Valkey held the job, and the job held IDs only, as the docs
describe:

```sh
pw=$(kubectl get secret valkey-auth -o jsonpath='{.data.default-password}' | base64 -d)
kubectl exec deploy/valkey -c valkey -- valkey-cli -a "$pw" --no-auth-warning LRANGE bull:jobs:wait 0 -1
kubectl exec deploy/valkey -c valkey -- valkey-cli -a "$pw" --no-auth-warning HGET bull:jobs:5 data
```

```text
5
{"workflowId":"u1WBH1PohKF5XNxI","executionId":"5","loadStaticData":true,"callerAwaitsOutcome":"response","projectId":"LCYJynKM4DDujlCS","projectName":"Smoke Owner <owner@example.com>"}
```

`kubectl scale deployment n8n-worker --replicas=2` created two worker pods
at 18:32:57. One of them logged `Worker started execution 5 (job 5)`, and
PostgreSQL recorded the start at 18:33:07.369 and the end 93 milliseconds
later. The status changed to `success`. The caller had given up at
18:32:34, so the execution ran without anyone waiting for its answer. A
first round with a 60 second `curl` limit ended the same way: no answer,
and the execution started 10 seconds after the new worker pod was created.

## Readiness does not gate the queue

Both new workers turned Ready at 18:33:37, 30 seconds after one of them
had finished execution 5. The worker's readiness probe gets
`/healthz/readiness` with `initialDelaySeconds: 30`, so it had not run yet
when the worker took the job from Valkey. No Service sends traffic to a
worker, and readiness decides only when `kubectl rollout status` returns.

Between the two rounds, with one worker running, the same call answered
in 0.106 seconds through the port forward, with the probe value in the
response:

```text
{"headers":{"host":"localhost:15678","user-agent":"curl/8.23.0","accept":"*/*"},"params":{},"query":{"probe":"4242"},"body":{},"webhookUrl":"http://n8n.example.com:5678/webhook/smoke","executionMode":"production"}
HTTP 200 in 0.105743s
```

## The CI runs

The weekly run of the recipes workflow,
[run 42622189328](https://github.com/kadet-hub/recipes/actions/runs/42622189328),
tested the same commit `04879f4` on 9 November 2026, once per Kubernetes
minor. `check n8n --level deploys` passed on
[1.37](https://github.com/kadet-hub/recipes/actions/runs/42622189328/job/130378855760),
[1.36](https://github.com/kadet-hub/recipes/actions/runs/42622189328/job/130378857036)
and
[1.35](https://github.com/kadet-hub/recipes/actions/runs/42622189328/job/130378856422),
with the same 15 differences on 1.37.

## What it leaves out

The recipe's README lists the chart's options that are off by default and
not part of the recipe: webhook processors, multi-main, task runners, the
Ingress, the HPA, KEDA, S3 storage and the NetworkPolicy. Without webhook
processors, `n8n-main` receives every webhook call, so it stays a single
point for incoming traffic even with more workers. The worker count is a fixed
`replicas: 2`. Scaling workers on the length of `bull:jobs:wait` needs an
autoscaler such as KEDA, and the recipe renders none.

Moving an existing Helm release of the chart to the recipe is not tested.
The README lists the steps, and the encryption key of the release has to
come along, or n8n cannot read the credentials it stored.
