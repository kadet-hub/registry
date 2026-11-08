---
title: kubectl wait for condition fails on null conditions
date: 2026-11-02
topics: [ci, crds, validation]
tools: [kubectl, kind]
description: "kubectl wait --for condition exits at once with an accessor error when status.conditions is null. A kind reproduction and a wait loop that holds."
---

`kubectl wait --for condition=Established crd/<name>` is the usual way to
wait for a new [CRD](/glossary/#crd) before applying resources of its kind.
It waits while the object has no `status.conditions`. It does not wait when
`status.conditions` is present and `null`: it exits at once with an error.
The kadet-hub/recipes CI hit that on 26 October 2026, with kubectl 1.37.1
against a kind node on Kubernetes 1.37.0:

    error: kubectl --kubeconfig ... wait --for condition=Established --timeout 60s crd/rabbitmqclusters.rabbitmq.com exited 1
    error: .status.conditions accessor error: <nil> is of the type <nil>, expected []interface{}

A rerun of the same job passed. The 60 second timeout never came into play.

## Why kubectl gives up

kubectl reads the conditions with `unstructured.NestedSlice` in
`checkCondition` (`staging/src/k8s.io/kubectl/pkg/cmd/wait/condition.go`,
[v1.37.2](https://github.com/kubernetes/kubernetes/blob/v1.37.2/staging/src/k8s.io/kubectl/pkg/cmd/wait/condition.go)).
`NestedSlice` has three outcomes. A missing field returns "not found", and
`checkCondition` keeps waiting. A list is compared with the condition. Any
other value, `null` included, is an error, and `kubectl wait` returns it
without retrying:

    conditions, found, err := unstructured.NestedSlice(obj.Object, "status", "conditions")
    if err != nil {
        return false, err
    }
    if !found {
        return false, nil
    }

The message is the one `NestedSlice` builds in
[apimachinery's helpers.go](https://github.com/kubernetes/kubernetes/blob/v1.37.2/staging/src/k8s.io/apimachinery/pkg/apis/meta/v1/unstructured/helpers.go):
`%v accessor error: %v is of the type %T, expected []interface{}`.

## Reproducing it on kind

The CI failure is a race that we could not trigger on purpose. 200 rounds
of `kubectl create` of a new CRD followed at once by `kubectl wait --for
condition=Established` all passed, with kubectl 1.37.2 on a kind 0.33.0
cluster running Kubernetes 1.37.0. We have not found which write leaves a
new CRD's conditions `null` for a moment.

The code path itself is easy to reach with any object whose
`status.conditions` is `null`. A CRD that keeps unknown fields lets you
create one:

    apiVersion: apiextensions.k8s.io/v1
    kind: CustomResourceDefinition
    metadata:
      name: gadgets.example.com
    spec:
      group: example.com
      names: {kind: Gadget, plural: gadgets}
      scope: Namespaced
      versions:
      - name: v1
        served: true
        storage: true
        schema:
          openAPIV3Schema:
            type: object
            x-kubernetes-preserve-unknown-fields: true

Create the object with `kubectl create`. `kubectl apply` drops the `null`,
because in a merge patch `null` means "delete this field", and the stored
status ends up as `{}`.

    $ printf 'apiVersion: example.com/v1\nkind: Gadget\nmetadata: {name: with-null}\nstatus: {conditions: null}\n' | kubectl create -f -
    gadget.example.com/with-null created
    $ kubectl get gadget with-null -o jsonpath='{.status}'
    {"conditions":null}
    $ kubectl wait --for condition=Ready --timeout=10s gadget/with-null
    error: .status.conditions accessor error: <nil> is of the type <nil>, expected []interface{}

That returned after 0 seconds with exit code 1. A second Gadget without a
`status` waited the full 10 seconds and then reported `timed out waiting
for the condition`, which is the behaviour the CI job relied on.

The JSONPath form does not help:

    $ kubectl wait --for=jsonpath='{.status.conditions[?(@.type=="Ready")].status}'=True --timeout=10s gadget/with-null
    error: <nil> is not array or slice and cannot be filtered

It also exits after 0 seconds.

## A wait that holds

Polling with `kubectl get` and retrying on any answer that is not `True`
treats `null`, a missing field and a transient API error alike:

    timeout 60 bash -c 'until kubectl get crd/rabbitmqclusters.rabbitmq.com \
        -o jsonpath="{.status.conditions[?(@.type==\"Established\")].status}" 2>/dev/null \
        | grep -qx True; do sleep 1; done'

Against the Gadget above, created with `null` conditions and patched to
`Ready=True` three seconds later, the same loop with `gadget/with-null` and
`Ready` returned 0 after 3 seconds. `timeout` turns a CRD that never becomes
Established into exit code 124, so the job still fails on a real problem.

The recipe check of kadet-hub does the same in Python since
[kadet-hub/recipes#49](https://github.com/kadet-hub/recipes/pull/49): it
reads every new CRD with `kubectl get -o json` once a second and accepts it
when an `Established` condition has status `True`, for up to 60 seconds.
That replaced its three `kubectl wait --for condition=Established` calls.
