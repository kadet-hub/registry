---
title: "Converting the oauth2-proxy Helm chart to a Kapitan inventory"
date: 2026-11-22
topics: [helm, kapitan, generators, verification]
description: "kadet-convert turns the oauth2-proxy Helm chart and your values into a Kapitan inventory, proves on kind that it renders the same objects, and lists the gaps."
---

A Helm user who looks at [Kapitan](/glossary/#kapitan) usually asks first
whether it can produce what their chart produces, with their values.
`kadet-convert` answers that with one command. It renders a chart with
your values file, writes a Kapitan project for the
[kubernetes](/generators/kubernetes/) generator, and proves on two
[kind](/glossary/#kind) clusters that the project renders the same objects
as `helm template`. The proof is the comparison that kadet-hub's
[recipes](/glossary/#recipe) pass. The converter is part of `check` in
kadet-hub/recipes and first shipped in check 0.16.0, tag `check-v0.16.0`.

This post converts the Helm chart of oauth2-proxy, an authentication
proxy, in version 10.7.2 from its Helm repository. Every command below ran
as printed. The outputs come from that run, two of them in part, as the
text says.

## What you need {#prerequisites}

The converter needs helm, kubectl, kind, Docker, oras, gh and uv on
`PATH`, and gh logged in with `gh auth login`. gh verifies the generator's
[attestation](/glossary/#attestation) before the generator runs. The run
below used helm 4.3.1, kind 0.33.0, kubectl 1.37.2, oras 1.3.6, gh 2.103.3
and uv 0.13.5. One command reads the value map with jq, and the compile
step uses Kapitan 0.36.3.

## Run the conversion {#run}

Start in an empty directory with a values file. The client ID and both
secrets are placeholders:

```sh
mkdir oauth2-proxy-kapitan && cd oauth2-proxy-kapitan
cat > values.yaml <<'EOF'
config:
  clientID: my-client-id
  clientSecret: my-client-secret
  cookieSecret: 0123456789abcdef0123456789abcdef
extraArgs:
  provider: github
  upstream: http://my-app.my-app:8080
EOF
```

Then convert. `uvx` builds the converter from the tag:

```sh
uvx --from 'git+https://github.com/kadet-hub/recipes@check-v0.16.0#subdirectory=check' \
  kadet-convert oauth2-proxy --repo https://oauth2-proxy.github.io/manifests --version 10.7.2 \
  --name oauth2-proxy --namespace oauth2-proxy -f values.yaml --out converted
```

The run took 71 seconds here, including both kind clusters, which the
converter deletes afterwards. It exits 0 when every object is mapped and
equal, 1 when something is not, and 2 when a command fails. This one
exited 0. It writes `converted/report.md`, `converted/value-map.json`,
`converted/render.yaml` with the chart's render, and the Kapitan project in
`converted/project/`.

## The report {#report}

The command prints the report. The line before it, on stderr, names the
generator it verified:

```text
generator: kubernetes 1.14.0 (sha256:787129e1eaed, index serial 115), attestation and index verified
# kadet-convert report: oauth2-proxy

## Source

Chart `oauth2-proxy` 10.7.2, archive SHA-256 `bcdd083c2301efee4fb404a188b1ff5728de1638c64502525ba44abf772313a1`; release `oauth2-proxy`, namespace `oauth2-proxy`.

## Objects

4 exact, 1 equal up to accepted classes.

| Object | Class | Details |
|---|---|---|
| `ServiceAccount/oauth2-proxy/oauth2-proxy` | exact | generators.kubernetes.service_accounts.oauth2-proxy |
| `Secret/oauth2-proxy/oauth2-proxy` | exact | generators.kubernetes.secrets.oauth2-proxy |
| `ConfigMap/oauth2-proxy/oauth2-proxy` | exact | generators.kubernetes.configs.oauth2-proxy |
| `Service/oauth2-proxy/oauth2-proxy` | exact | generators.kubernetes.services.oauth2-proxy |
| `Deployment/oauth2-proxy/oauth2-proxy` | equal up to accepted classes | Selector scheme |

The converted workloads select their pods by the generator's `name` label. A selector is immutable, so `kubectl apply` over a running Helm release fails on these workloads: delete them with `--cascade=orphan` first (CNV-17).

## Permissions

No subject is bound. Equal for users bound to view, edit and admin.

## Secrets

The data of 1 Secret(s) is in `inventory/classes/converted/oauth2-proxy/secrets.yml`, listed in `.gitignore`. Keep it out of git and replace each value with a ref that holds the same base64 value.
```

Each side goes to its own cluster with a server-side dry run. "Exact"
means the API server stored the same object for both. "Equal up to
accepted classes" means the only differences are ones that `check` also
accepts for recipes, and the report names them. For the Deployment that is
the selector. The chart selects pods by `app.kubernetes.io/name` and
`app.kubernetes.io/instance`. The generator selects them by its own label
`name: oauth2-proxy`. The converted pods still carry the chart's labels, so
the chart's Service finds them.

The permission check runs `kubectl auth can-i` for every subject on both
clusters. oauth2-proxy binds no role, so only the users bound to the
built-in view, edit and admin roles are compared.

## Where your values went {#values}

The report ends with the values that reached the inventory. The first rows:

```text
## Values

358 values: 267 no effect, below a switch that is off, 32 no effect, 30 reached, 22 switch, 5 derived, 2 render error. The full map is `value-map.json`. These values reached inventory fields:

| Value | Inventory fields |
|---|---|
| `config.clientID` | `components.oauth2-proxy.pod_annotations.checksum/secret`, `generators.kubernetes.secrets.oauth2-proxy.data.client-id.value` |
| `config.clientSecret` | `components.oauth2-proxy.pod_annotations.checksum/secret`, `generators.kubernetes.secrets.oauth2-proxy.data.client-secret.value` |
| `config.cookieSecret` | `components.oauth2-proxy.pod_annotations.checksum/secret`, `generators.kubernetes.secrets.oauth2-proxy.data.cookie-secret.value` |
```

27 more rows follow, among them `replicaCount` in
`components.oauth2-proxy.replicas`. The converter finds these by rendering
the chart once per scalar value with that value changed and comparing the
two inventories. `value-map.json` holds the class of every value:

```sh
jq -c '.[] | select(.value | IN("replicaCount", "image.tag", "ingress.enabled", "ingress.path", "podDisruptionBudget.enabled"))' converted/value-map.json
```

```text
{"value":"image.tag","class":"derived","fields":["components.oauth2-proxy.image"]}
{"value":"ingress.enabled","class":"switch"}
{"value":"ingress.path","class":"no effect, below a switch that is off"}
{"value":"replicaCount","class":"reached","fields":["components.oauth2-proxy.replicas"]}
{"value":"podDisruptionBudget.enabled","class":"no effect"}
```

A switch adds or removes objects or fields, so no single inventory field
stands for it. `ingress.path` changes nothing while `ingress.enabled` is
false. A derived value changes a field without appearing in it, as
`image.tag` does in the image reference. `podDisruptionBudget.enabled`
has no effect with one replica, because the chart renders the budget only
for more than one.

## Secrets stay out of git {#secrets}

The converted class holds no Secret data. It interpolates each value from
a second class, and the project's `.gitignore` lists that class:

```sh
cat converted/project/inventory/classes/converted/oauth2-proxy/secrets.yml
cat converted/project/.gitignore
```

```text
# Secret data of the chart's render. Keep this file out of git and replace each value with a ref
# that holds the same base64 value, such as ?{gpg:...} (docs/specs/converter.md CNV-10).
parameters:
  applications:
    oauth2-proxy:
      secrets:
        oauth2_proxy__cookie_secret: MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=
        oauth2_proxy__client_secret: bXktY2xpZW50LXNlY3JldA==
        oauth2_proxy__client_id: bXktY2xpZW50LWlk
inventory/classes/converted/oauth2-proxy/secrets.yml
```

The values are the base64 of the placeholders in `values.yaml`. In the
converted class, the Secret reads them with `b64_encode: false`:

```yaml
          data:
            cookie-secret:
              value: ${applications.oauth2-proxy.secrets.oauth2_proxy__cookie_secret}
              b64_encode: false
```

Before the project goes into git, replace each value in `secrets.yml` with
a [ref](/glossary/#ref) that holds the same base64 value, or move the three
keys into a class of your own that does.

## Compile it {#compile}

The project compiles without fetching anything. The generator is already
in `lib/kubernetes`, pinned by version and digest. With Kapitan 0.36.3
installed as in the [quickstart](/quickstart/):

```sh
cd converted/project && kapitan compile
```

```text
Rendered inventory (2.61s): discovered 1 targets.
Compiling 1/1 targets using 1 concurrent processes: (24 CPU available)
oauth2-proxy: container oauth2-proxy has no resources requests.cpu, requests.memory, limits.memory; requests drive scheduling and a memory limit bounds the impact of a leak
Compiled oauth2-proxy (0.02s)
Compiled 1 targets in 0.79s
```

The generator prints the warning because the chart sets no resources by
default.
`compiled/oauth2-proxy/manifests/oauth2-proxy/` now holds five files, one
each for the ConfigMap, the Deployment, the ServiceAccount, the Secret and
the Service.

## Limits {#limits}

A conversion is a one-off migration. The project is yours to edit, and a
later conversion writes a new project instead of merging with your edits.

The values are frozen. The inventory holds what `helm template` rendered
as literals, and the converter writes no parameters. In this run, 30 of
358 values reached an inventory field. To flip a switch such
as `ingress.enabled`, convert again with the new value.

The pod annotations `checksum/config` and `checksum/secret` are literals
too. Under Helm they changed with the ConfigMap and the Secret and so
rolled the pods. In the converted project, a changed Secret does not
change them.

A kind the converter does not map yet is reported as not mapped. With
`replicaCount: 2`, the chart adds a PodDisruptionBudget, which check
0.16.0 does not map:

```sh
cd ../..
printf 'replicaCount: 2\n' > replicas.yaml
uvx --from 'git+https://github.com/kadet-hub/recipes@check-v0.16.0#subdirectory=check' \
  kadet-convert oauth2-proxy --repo https://oauth2-proxy.github.io/manifests --version 10.7.2 \
  --name oauth2-proxy --namespace oauth2-proxy -f values.yaml -f replicas.yaml --out converted-2
```

It exits with status 1. The Objects section of its report:

```text
4 exact, 1 equal up to accepted classes, 1 not mapped.

| Object | Class | Details |
|---|---|---|
| `ServiceAccount/oauth2-proxy/oauth2-proxy` | exact | generators.kubernetes.service_accounts.oauth2-proxy |
| `Secret/oauth2-proxy/oauth2-proxy` | exact | generators.kubernetes.secrets.oauth2-proxy |
| `ConfigMap/oauth2-proxy/oauth2-proxy` | exact | generators.kubernetes.configs.oauth2-proxy |
| `Service/oauth2-proxy/oauth2-proxy` | exact | generators.kubernetes.services.oauth2-proxy |
| `Deployment/oauth2-proxy/oauth2-proxy` | equal up to accepted classes | Selector scheme |
| `PodDisruptionBudget/oauth2-proxy/oauth2-proxy` | not mapped | the converter does not map PodDisruptionBudget |
```

The generator itself renders PodDisruptionBudgets, NetworkPolicies and
APIServices. The converter reports them as not mapped until it maps them.
Apart from CRDs, which it copies unchanged, it passes no object through.
The report lists the fields it cannot map under "Not mappable fields".
With check 0.16.0 and the kubernetes generator 1.14.0, which this post
runs, they include a StatefulSet's `serviceName` that differs from its own
name and a container's `workingDir`. check 0.20.0 pins the generator
1.15.0 and maps that `serviceName` to the generator's
`statefulset_service_name`. 1.15.0 has a key for `workingDir` as well,
but check 0.20.0 does not map it yet and still lists it. A StatefulSet's
`podManagementPolicy` has no key in 1.15.0. Objects with a `helm.sh/hook`
annotation are left out and listed, such as the three test pods of
podinfo's chart.

`--out` must not be named like a chart that comes from a repository. The
converter creates the directory first and then takes the chart name for a
local chart directory. With `--out oauth2-proxy`, the command above stops
with exit status 2:

```text
Error: helm show chart oauth2-proxy exited 1:
Error: Chart.yaml file is missing
```

The new selectors are what make a running release hard to replace. A
selector is immutable, so `kubectl apply` of the converted Deployment over
the Helm release fails. The converter's documentation lists the steps.
Delete the Deployment with `--cascade=orphan`, so its pods keep running.
Delete the release's `sh.helm.release.v1.oauth2-proxy.*` Secrets, so Helm
forgets the release. Apply the compiled manifests with
`kubectl apply --server-side --force-conflicts`. Delete the orphaned
ReplicaSet once the new pods are ready. These steps are not tested, so try
them on a test cluster first.

## When Kapitan's helm input is the better choice {#helm-input}

Kapitan can render a chart itself, with `input_type: helm` in the
[inventory](/glossary/#inventory). The chart stays as it is, Helm runs at
every compile, and a new chart version is a version bump with your values
kept. That is the better choice if you want to keep following upstream
releases of the chart. The converter is for the other case. You want the
objects in your inventory, rendered by a generator you can read, and you
accept that later chart releases do not reach you on their own.
[Helmfile vs Kapitan](/blog/helmfile-vs-kapitan/) shows the helm input on
podinfo and Valkey, and
[Kapitan inputs](/guides/generator-helm-or-jinja2/) compares it with kadet
generators, Jinja2 and Kustomize.

The converter's usage and design are in
[docs/convert.md](https://github.com/kadet-hub/recipes/blob/check-v0.16.0/docs/convert.md)
and
[docs/specs/converter.md](https://github.com/kadet-hub/recipes/blob/check-v0.16.0/docs/specs/converter.md)
in kadet-hub/recipes.
