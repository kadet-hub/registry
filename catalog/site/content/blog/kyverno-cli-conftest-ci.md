---
title: "Kyverno CLI and conftest in CI vs Kyverno at admission"
date: 2026-11-18
topics: [kapitan, ci, security, validation]
tools: [Kyverno, conftest, GitHubActions]
description: "Kyverno CLI and conftest on Kapitan's compiled output in a pull request, next to the compile diff, and the same Kyverno policies at admission on kind."
---

[Kapitan](/glossary/#kapitan) compiles an [inventory](/glossary/#inventory)
into plain YAML under `compiled/`. The registry's compile diff action shows
a reviewer what a pull request changes in that YAML. It does not say
whether the change is allowed. A container that runs privileged or an
image on the tag `latest` is one line in the diff, and Kapitan compiles it
without an error. Kyverno as an admission controller can reject such an
object when it reaches the cluster, after the merge.

This post runs two policy tools on `compiled/` in the pull request: the
Kyverno CLI with policies from
[kyverno/policies](https://github.com/kyverno/policies), and conftest with
Rego rules of your own. It then installs Kyverno into a
[kind](/glossary/#kind) cluster with the same policies and sends it the
same objects.

The project is
[policy-checks](https://github.com/kadet-hub/examples/tree/main/policy-checks)
in kadet-hub/examples. Its `check` script runs the steps below on every
change and once a week, and fails when one of their results changes.

## Two targets

The class `web` renders podinfo as a Deployment with a Service through
the [kubernetes](/generators/kubernetes/) generator. Two
[targets](/glossary/#target) add what the policies look at. `compliant`
does what the policies ask for:

```yaml
parameters:
  namespace: compliant
  generators:
    kubernetes:
      namespaces:
        compliant: {}
    manifest:
      default_config:
        security_profile: restricted
  components:
    web:
      image: ghcr.io/stefanprodan/podinfo:6.17.0@sha256:fa2f27c1a8561097e5144bfc0853eba6054d743b68b03de4cad4675616ddefb0
      security_context: {runAsUser: 65534}
      resources:
        requests: {cpu: 50m, memory: 64Mi}
        limits: {memory: 128Mi}
      pdb_min_available: 1
```

`noncompliant` does not:

```yaml
parameters:
  namespace: noncompliant
  generators:
    kubernetes:
      namespaces:
        noncompliant: {}
  components:
    web:
      image: ghcr.io/stefanprodan/podinfo:latest
      security_context: {privileged: true}
```

Both have two replicas. `security_profile: restricted` makes the generator
fill the fields of the Pod Security Standards' restricted profile that the
inventory leaves unset: `runAsNonRoot`, the `RuntimeDefault` seccomp
profile, `allowPrivilegeEscalation: false` and dropping all capabilities.
`pdb_min_available` adds a PodDisruptionBudget.

`kapitan compile` exits 0 for both targets. For `noncompliant` the
generator logs two warnings:

```text
web: container web image 'ghcr.io/stefanprodan/podinfo:latest' has no pinned tag or digest; imagePullPolicy is IfNotPresent, the generator default, so nodes keep running a stale cached image
web: container web has no resources requests.cpu, requests.memory, limits.memory; requests drive scheduling and a memory limit bounds the impact of a leak
```

Nothing warns about the privileged container, because the target sets no
security profile. The warnings name the component, not the target.

## Kyverno CLI on compiled/

kyverno/policies publishes no releases or tags. It keeps a branch per
Kyverno minor version, and `check` downloads the repository's archive at
a commit of `release-1.19` to match Kyverno 1.19.2. The branch holds each
policy in several forms. `best-practices/` and `pod-security/` hold
ClusterPolicies, for which the CLI 1.19.2 prints a warning per file:

```text
Warning: pol/best-practices/disallow-latest-tag/disallow-latest-tag.yaml: kyverno.io/v1 ClusterPolicy is deprecated and will be removed in a future release; migrate to ValidatingPolicy, MutatingPolicy, GeneratingPolicy or ImageValidatingPolicy (policies.kyverno.io), see https://kyverno.io/docs/guides/migration-to-cel/
```

`check` therefore uses the ValidatingPolicy versions, written in CEL:
`best-practices-vpol/disallow-latest-tag`,
`best-practices-vpol/require-pod-requests-limits`, and every policy under
`pod-security-vpol/baseline` and `pod-security-vpol/restricted`. The
restricted profile includes baseline, so both directories are needed.
That makes 18 files. They match Pods, and Kyverno derives the same rules
for Deployments, ReplicaSets, StatefulSets, DaemonSets, Jobs and
CronJobs, so the CLI judges a Deployment by its pod template.

Given the whole output directory, the CLI checks nothing:

```sh
kyverno apply "${policies[@]}" --resource=compiled
```

```text
Applying 18 policy rule(s) to 0 resource(s)...

pass: 0, fail: 0, warn: 0, error: 0, skip: 0
```

The exit code is 0. `--resource` reads the files in a directory, not
those in its subdirectories, and Kapitan writes a target's objects to
`compiled/<target>/<namespace>/`. Pointed at `compiled/`, the CLI checks
nothing and passes. `check` names every file instead:

```sh
mapfile -t files < <(find compiled/noncompliant -name '*.yml')
kyverno apply "${policies[@]}" "${files[@]/#/--resource=}" --remove-color
```

For `compliant` the CLI reports `pass: 18, fail: 0` and exits 0. For
`noncompliant` it exits 1:

```text
Applying 18 policy rule(s) to 3 resource(s)...
policy disallow-latest-tag -> resource noncompliant/Deployment/web failed:
1 -  Using a mutable image tag e.g. 'latest' is not allowed.
policy require-requests-limits -> resource noncompliant/Deployment/web failed:
1 -  CPU and memory resource requests and memory limits are required for containers.
policy disallow-privileged-containers -> resource noncompliant/Deployment/web failed:
1 -  Privileged mode is disallowed. All containers must set the securityContext.privileged field to `false` or unset the field.
policy disallow-capabilities-strict -> resource noncompliant/Deployment/web failed:
1 -  Containers must drop `ALL` capabilities.
policy disallow-privilege-escalation -> resource noncompliant/Deployment/web failed:
1 -  Privilege escalation is disallowed.  All containers must set the securityContext.allowPrivilegeEscalation field to `false`.
policy require-run-as-nonroot -> resource noncompliant/Deployment/web failed:
1 -  Running as root is not allowed. Either spec.securityContext.runAsNonRoot  must be set to true, or all containers (spec.containers[*], spec.initContainers[*],  spec.ephemeralContainers[*]) must have securityContext.runAsNonRoot set to true.

pass: 12, fail: 6, warn: 0, error: 0, skip: 0
```

Every policy file sets `validationActions: [Audit]`. In a cluster, Audit
admits the object, as the admission section shows. The CLI counts the
violation as a failure anyway, unless `--audit-warn` turns it into a
warning. The same file
blocks a pull request and nothing in a cluster.

One finding is missing. `noncompliant`'s pod sets no seccomp profile, and
the restricted profile of the
[Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/#restricted)
forbids that: "Both the Unconfined profile and the absence of a profile
are prohibited." The ValidatingPolicy `restrict-seccomp-strict` at the
pinned commit reads a missing profile as `RuntimeDefault`
(`seccompProfile.?type.orValue('RuntimeDefault')`) and passes the pod. The
18 files are therefore not quite the restricted profile. `check` fails
once that policy reports the pod, so this paragraph gets updated.

## conftest with your own rules

The Kyverno policies judge one object at a time. Some rules need two.
`policy/compiled.rego` holds two house rules for conftest, which bundles
OPA:

```rego
package main

objects contains [f.path, o] if {
	some f in input
	is_object(f.contents)
	o := f.contents
}

objects contains [f.path, o] if {
	some f in input
	is_array(f.contents)
	some o in f.contents
	is_object(o)
}

deny contains msg if {
	some [path, o] in objects
	walk(o, [p, list])
	p[count(p) - 1] in {"containers", "initContainers", "ephemeralContainers"}
	some c in list
	not contains(c.image, "@sha256:")
	msg := sprintf("%s: %s %s, container %s: image %s is not pinned by digest", [path, o.kind, name(o), c.name, c.image])
}

deny contains msg if {
	some [path, o] in objects
	o.kind == "Deployment"
	o.spec.replicas > 1
	not covered(o)
	msg := sprintf("%s: Deployment %s runs %d replicas and no PodDisruptionBudget selects its pods", [path, name(o), o.spec.replicas])
}

covered(d) if {
	some [_, pdb] in objects
	pdb.kind == "PodDisruptionBudget"
	pdb.metadata.namespace == d.metadata.namespace
	count(pdb.spec.selector.matchLabels) > 0
	every k, v in pdb.spec.selector.matchLabels {
		d.spec.template.metadata.labels[k] == v
	}
}

name(o) := sprintf("%s/%s", [o.metadata.namespace, o.metadata.name])

name(o) := o.metadata.name if not o.metadata.namespace
```

`--combine` hands all files of a target to the rules as one list, so the
second rule can look for a PodDisruptionBudget in another file. The
generator writes the Deployment to `web-deploy.yml` and the
PodDisruptionBudget to `web-scaling.yml`. The first rule finds pod specs
at any depth, so it covers Pods, Deployments, CronJobs and pod templates
inside custom resources alike. Unlike Kyverno's CLI, conftest reads the
subdirectories of the path it is given.

```sh
conftest test --combine --no-color compiled/noncompliant
```

```text
FAIL - Combined - main - compiled/noncompliant/noncompliant/web-deploy.yml: Deployment noncompliant/web runs 2 replicas and no PodDisruptionBudget selects its pods
FAIL - Combined - main - compiled/noncompliant/noncompliant/web-deploy.yml: Deployment noncompliant/web, container web: image ghcr.io/stefanprodan/podinfo:latest is not pinned by digest

2 tests, 0 passed, 0 warnings, 2 failures, 0 exceptions
```

conftest exits 1 here and 0 for `compiled/compliant`.

## In the pull request, next to the compile diff

The registry's compile diff runs as two workflows. `compile-diff.yml`
compiles the base and the merge commit with the
[consumer workflow](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#compile-diff-in-pull-requests)
and uploads the diff. `compile-diff-comment.yml` posts it on the pull
request. kadet-hub/examples runs both on `first-platform`.

The policy checks go into a third workflow, `policy.yml`. The comment
action downloads the diff only when the compile diff run succeeded, and
posts a one-line status otherwise. A policy job inside that run would
replace the diff with "failure" exactly when a reviewer needs to see what
changed.
[`policy.yml`](https://github.com/kadet-hub/examples/blob/main/policy-checks/.github/workflows/policy.yml)
in the example folder is the workflow for a repository of your own:

```yaml
name: policy
on: [pull_request]
permissions: {}

env:
  # renovate: datasource=github-release-attachments depName=kyverno/kyverno
  KYVERNO_VERSION: v1.19.2
  KYVERNO_SHA256: 357eaf1df8bc24ddd5a73979fadeaae6a032e8710f11af264229756e4956bf4a
  # renovate: datasource=github-release-attachments depName=open-policy-agent/conftest
  CONFTEST_VERSION: v0.71.1
  CONFTEST_SHA256: c3f6b2a753bd56e377a1e51a95ae3e057f926f2e9139f7d5b5dfbbaf810f7985
  # The release branch of KYVERNO_VERSION's minor version.
  # renovate: datasource=github-digest depName=kyverno/policies
  KYVERNO_POLICIES_COMMIT: 282e77f6d54e1e1a636190ff2dacc3d02c2d689c # release-1.19

jobs:
  compile:
    permissions:
      contents: read
      packages: read
      attestations: read
    uses: kadet-hub/registry/.github/workflows/consumer.yml@3ce8f3bf31e2bdaf6008b6fb787fd19f1b098470 # main

  policy:
    needs: compile
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333 # v8.0.2
        with:
          name: compiled
          path: ${{ runner.temp }}/out
      - name: Install the Kyverno CLI and conftest, download the policies
        working-directory: ${{ runner.temp }}
        run: |
          curl -fsSLo kyverno.tgz "https://github.com/kyverno/kyverno/releases/download/$KYVERNO_VERSION/kyverno-cli_${KYVERNO_VERSION}_linux_x86_64.tar.gz"
          curl -fsSLo conftest.tgz "https://github.com/open-policy-agent/conftest/releases/download/$CONFTEST_VERSION/conftest_${CONFTEST_VERSION#v}_Linux_x86_64.tar.gz"
          sha256sum -c <<EOF
          $KYVERNO_SHA256  kyverno.tgz
          $CONFTEST_SHA256  conftest.tgz
          EOF
          tar -xzf kyverno.tgz kyverno
          tar -xzf conftest.tgz conftest
          mkdir policies
          curl -fsSL "https://github.com/kyverno/policies/archive/$KYVERNO_POLICIES_COMMIT.tar.gz" |
            tar -xzf - -C policies --strip-components=1 --wildcards '*/best-practices-vpol/*' '*/pod-security-vpol/*'
      # --resource reads the files of a directory, not of its subdirectories,
      # so every file of a target is named.
      - name: Kyverno
        run: |
          p=$RUNNER_TEMP/policies
          policies=("$p"/best-practices-vpol/{disallow-latest-tag,require-pod-requests-limits}/*.yaml
            "$p"/pod-security-vpol/{baseline,restricted}/*/*.yaml)
          status=0
          for target in "$RUNNER_TEMP"/out/compiled/*/; do
            mapfile -t files < <(find "$target" -name '*.yml' -o -name '*.yaml')
            "$RUNNER_TEMP/kyverno" apply "${policies[@]}" "${files[@]/#/--resource=}" --remove-color || status=1
          done
          exit "$status"
      - name: conftest
        run: |
          status=0
          for target in "$RUNNER_TEMP"/out/compiled/*/; do
            "$RUNNER_TEMP/conftest" test --combine --no-color "$target" || status=1
          done
          exit "$status"
```

The `compile` job is the consumer workflow, which compiles in a gVisor
sandbox and uploads `compiled/` as the artifact `compiled`. The policy job
reads that artifact. It runs no Kapitan and nothing from the project but
the Rego files, and needs only `contents: read`. The two last steps
run the commands of the previous sections, one loop over the targets per
tool, and fail when any target fails.

GitHub does not run this copy in kadet-hub/examples, because a workflow
only runs from the repository root. Its commands are the ones `check`
runs, but the workflow itself is not tested. The consumer workflow also
checks the output against rules of its own, and its docs list privileged
containers among them. In such a repository, `noncompliant` would fail in
the `compile` job, and the policy job would not run. That was not tested
either.

## The same policies at admission

`check` creates a kind cluster with the node image `kindest/node:v1.37.0`,
installs Kyverno 1.19.2 from its release manifest `install.yaml`, the
version of the CLI, and applies the same 18 files. 17 of them use
`policies.kyverno.io/v1alpha1`, and kubectl prints the API server's
warning:

```text
Warning: policies.kyverno.io/v1alpha1 ValidatingPolicy is deprecated; use policies.kyverno.io/v1 ValidatingPolicy
```

With every policy patched to `validationActions: [Deny]`, a server-side
dry run of `noncompliant`'s Deployment is rejected:

```text
Error from server: error when creating "compiled/noncompliant/noncompliant/web-deploy.yml": admission webhook "vpol.validate.kyverno.svc-fail" denied the request: Policy disallow-latest-tag failed: Using a mutable image tag e.g. 'latest' is not allowed.;
Policy disallow-capabilities-strict failed: Containers must drop `ALL` capabilities.;
Policy disallow-privilege-escalation failed: Privilege escalation is disallowed. [...]
Policy require-run-as-nonroot failed: Running as root is not allowed. [...]
Policy require-requests-limits failed: CPU and memory resource requests and memory limits are required for containers.;
Policy disallow-privileged-containers failed: Privileged mode is disallowed. [...]
```

These are the six policies the CLI reported, with the same messages. The
dry run sends the Deployment through admission without creating it, so
nothing pulls `podinfo:latest`. `check` then applies the 18 files again as
shipped, which sets them back to Audit, and the same dry run passes:

```text
deployment.apps/web created (server dry run)
```

Copied into a cluster as they are, the policies block nothing. Under
`[Deny]`, `compliant` applies and its Deployment rolls out with two
replicas. The last step does not come from `compiled/` at all:

```sh
kubectl -n noncompliant run debug --image=ghcr.io/stefanprodan/podinfo:latest --privileged
```

Kyverno rejects it, `disallow-privileged-containers` among the failed
policies. No CI job sees that request.

## What each one catches

| | Kyverno CLI and conftest in CI | Kyverno at admission |
|---|---|---|
| When | in the pull request, before the merge | when an object reaches the API server |
| What it sees | every file of a target, conftest all of them at once | one object per request, from any source |
| Objects outside `compiled/` | no | yes, `kubectl run` above |
| Policies in Audit | fail the job | admit the object |
| Who sees the result | the reviewer, next to the compile diff | whoever applied |

CI shows a violation where the change is reviewed, with the diff of the
lines that cause it, and without access to a cluster. It only sees what
went through `compiled/`. Admission sees every request: a `kubectl` from a
laptop, another pipeline, an operator that creates pods. It answers after
the merge, and only once the policies are set to Deny. Running both with
the same files keeps one source for the rules.

## What the CI run showed

[Run 42003985350](https://github.com/kadet-hub/examples/actions/runs/42003985350)
of the examples workflow tested commit `f638f38` of
[kadet-hub/examples#148](https://github.com/kadet-hub/examples/pull/148)
on 5 November 2026, on GitHub's `ubuntu-24.04` runner, with the kind node
image `kindest/node:v1.37.0`. The durations below come from the log's
timestamps or are what `check` printed, in whole seconds.

Verifying the index and the generator, pulling it, compiling both targets
and running both tools on both took 18 seconds. The three `kyverno apply`
runs took 2 seconds of that, the two conftest runs less than one. kind had
the cluster ready 40 seconds later, and Kyverno's Deployments were
available 21 seconds after the apply of `install.yaml`. The first denied
dry run came 14 seconds after the policies were applied, a time that
includes waiting for them to report ready and patching all 18. The whole
check took 101 seconds.

## Pins

The workflow installs the Kyverno CLI and conftest by version and sha256,
and `check` downloads Kyverno's `install.yaml` the same way. `check`
compares the CLI's version with `install.yaml`'s and fails when they
differ. The policies are pinned by the commit of their branch. Renovate
moves that commit along the branch with its `github-digest` datasource, and
never to another branch. When Renovate moves Kyverno to 1.20, `check` fails
until someone moves the pin to `release-1.20`.

## What is not tested

- The workflow `policy.yml` and the consumer workflow's own output rules,
  as said above.
- Kyverno's policy reports.
- Kubernetes' built-in Pod Security Admission, which enforces the
  restricted profile per namespace without Kyverno.
- conftest's other parsers, and output that is not Kubernetes YAML.
