---
title: "Helmfile vs Kapitan: environments, secrets and release order"
date: 2026-11-12
topics: [helmfile, kapitan, helm, comparison]
description: "Helmfile environments, secrets and needs next to a Kapitan inventory: podinfo and Valkey from their charts render the same manifests for dev and prod."
---

A cluster that runs several upstream Helm charts, each with values per
environment, is the setup Helmfile is usually picked for. This post puts
the same setup into a [Kapitan](/glossary/#kapitan)
[inventory](/glossary/#inventory) and compares the two where they differ:
how environments are written, where the password goes, the order of
installs, and what a reviewer gets to see. The project is
[helmfile-vs-kapitan](https://github.com/kadet-hub/examples/tree/main/helmfile-vs-kapitan)
in kadet-hub/examples. Its `check` script fails unless both tools render
the same manifests for each environment. CI runs it on every change and
once a week, and every result below comes from it. Helm on its own against
Helmfile is covered in
[Helm alternatives for Kubernetes](/guides/helm-alternatives-for-kubernetes/#helmfile).

## The setup

podinfo, a small web app, uses Valkey as its cache. Both come from their
projects' charts: podinfo 6.17.0 from `ghcr.io/stefanprodan/charts` and
Valkey 0.12.1 from valkey-io's chart, which runs Valkey 9.1.3. Both
releases go into the namespace `podinfo`. The environments differ in these
values:

| | dev | prod |
|---|---|---|
| podinfo replicas | 1 | 2 |
| podinfo log level | debug | info |
| podinfo UI message | dev | prod |
| podinfo PodDisruptionBudget | none | `minAvailable: 1` |
| Valkey data | emptyDir | 8Gi PersistentVolumeClaim |
| Valkey resources | none set | 100m CPU and 128Mi requested, 512Mi limit |

podinfo logs in to Valkey as the user `default`. The password sits in the
Secret `valkey-auth`. podinfo's chart has no value for a cache password,
so `extraEnvs` reads it from the Secret, and the kubelet expands it into
the cache URL:

```yaml
extraEnvs:
  - name: VALKEY_PASSWORD
    valueFrom:
      secretKeyRef:
        name: valkey-auth
        key: default-password
  - name: PODINFO_CACHE_SERVER
    value: tcp://default:$(VALKEY_PASSWORD)@valkey:6379
```

Both sides pin each chart by version and OCI [digest](/glossary/#digest).
Both call the same helm binary, v4.3.1 in CI. Helmfile is v1.8.2, Kapitan
0.36.3.

## The Helmfile side {#helmfile}

`helmfile/helmfile.yaml`, complete:

```yaml
environments:
  dev:
    values: [environments/dev.yaml]
  prod:
    values: [environments/prod.yaml]
---
releases:
  - name: valkey
    namespace: podinfo
    chart: oci://ghcr.io/valkey-io/valkey-helm/valkey@sha256:b230e4a64fdeb9a3b554052d17026caae9c99427b3f5b50fc88bfd80b235176a
    version: 0.12.1
    values: [values/valkey.yaml.gotmpl]
  - name: podinfo
    namespace: podinfo
    chart: oci://ghcr.io/stefanprodan/charts/podinfo@sha256:258d0da545724b4eea8de5d5e724cd9a75aab3de79a87ba8d82ec402745cea58
    version: 6.17.0
    needs: [valkey]
    values: [values/podinfo.yaml.gotmpl]
```

The environment file holds what differs, `environments/prod.yaml`:

```yaml
podinfo:
  replicas: 2
  logLevel: info
  pdb:
    minAvailable: 1
valkey:
  dataStorage:
    enabled: true
    requestedSize: 8Gi
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      memory: 512Mi
```

The values files are Go templates that read it. podinfo's starts like this,
followed by the `extraEnvs` above:

```yaml
replicaCount: {{ .Values.podinfo.replicas }}
logLevel: {{ .Values.podinfo.logLevel }}
ui:
  message: {{ .Environment.Name }}
podDisruptionBudget: {{ toYaml .Values.podinfo.pdb | nindent 2 }}
```

`helmfile -e prod template` renders one environment.

## The Kapitan side {#kapitan}

A [target](/glossary/#target) per environment holds the same values as
parameters, `inventory/targets/prod.yml`:

```yaml
classes: [common, valkey, podinfo]
parameters:
  podinfo:
    replicas: 2
    logLevel: info
    pdb:
      minAvailable: 1
  valkey:
    dataStorage:
      enabled: true
      requestedSize: 8Gi
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        memory: 512Mi
```

A [class](/glossary/#class) per chart pins it and renders it with
Kapitan's `helm` input. `inventory/classes/podinfo.yml`, without the
`extraEnvs`:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: helm
        source: oci://ghcr.io/stefanprodan/charts/podinfo@sha256:258d0da545724b4eea8de5d5e724cd9a75aab3de79a87ba8d82ec402745cea58
        chart_name: podinfo
        version: 6.17.0
        output_path: charts/podinfo
    compile:
      - input_type: helm
        input_paths: [charts/podinfo]
        output_path: podinfo
        helm_params:
          name: podinfo
          namespace: ${namespace}
        helm_values:
          replicaCount: ${podinfo:replicas}
          logLevel: ${podinfo:logLevel}
          ui:
            message: ${kapitan:vars:target}
          podDisruptionBudget: ${podinfo:pdb}
```

One `kapitan compile` renders both targets, into `compiled/dev` and
`compiled/prod`.

## The same manifests {#check}

`check` renders both environments on both sides, writes one document per
object, sorts objects and keys, and diffs. It sets the namespace `podinfo`
on objects that have none, since both sides hand that namespace to Helm.
It compares the Secret `valkey-auth` by name, namespace, type and decoded
data, because on the Kapitan side it does not come from the chart, as
[Secrets](#secrets) explains. Nothing else is normalized.

```console
dev: helmfile = kapitan (8 objects)
prod: helmfile = kapitan (10 objects)
```

In a local run with prod's replicas set to 3 in the Kapitan target alone,
`check` failed:

```diff
@@ -72,7 +72,7 @@
   name: podinfo
   namespace: podinfo
 spec:
-  replicas: 3
+  replicas: 2
```

Counted without the fetched charts and generator, the two sides are not the
same size:

| | files | lines |
|---|---|---|
| Helmfile | 5 | 65 |
| Kapitan | 6 | 111 |

Most of Kapitan's extra lines are structure. A chart takes a dependency
block of five lines where Helmfile writes `chart` and `version`, and the
`helm` input names its input path, output path and Helm parameters. 16
lines in the class `valkey` replace the chart's Secret. Kapitan also needs
a Python toolchain and the generator, where Helmfile needs one more binary
next to helm.

## Environments {#environments}

The environment files are almost the same on both sides. A Kapitan target
adds `classes` and the `parameters` key, and otherwise holds the same YAML.
The difference is how the values reach the chart.

Helmfile renders values files as Go templates. A scalar goes in with
`{{ .Values.podinfo.replicas }}`. A map such as the PodDisruptionBudget
needs `toYaml` and `nindent 2` so that it lands at the right indentation.
The environment's name is `.Environment.Name`. `helmfile` renders one
environment per run, chosen with `-e`.

Kapitan writes the chart values as YAML that refers to parameters through
[interpolation](/glossary/#interpolation). `${podinfo:pdb}` inserts the
map as a map, with no indentation to manage. The target's name is
`${kapitan:vars:target}`. One compile renders every target.

## Secrets {#secrets}

`check` creates a random password per run, so neither side has one in the
repository.

Helmfile reads it through [vals](https://github.com/helmfile/vals), which
resolves `ref+` values before Helm sees them. Here the value is
`ref+envsubst://$VALKEY_PASSWORD`, which reads an environment variable.
Helmfile's documentation shows backends such as Vault and AWS SSM instead,
which the example does not test. The chart writes the password
into `valkey-auth`, base64-encoded, and `check` finds it in the output of
`helmfile template`.

Kapitan reads it from the [ref](/glossary/#ref)
`?{base64:valkey/password}`. Without `--reveal`, the compiled Secret holds
a token in its place:

```console
password: base64 in helmfile's output, ref token ?{base64:valkey/password:249a3869} in kapitan's without --reveal
```

The ref cannot go to the chart as its password value. Kapitan passes
`helm_values` to Helm as written and reveals refs only in what it writes
itself. `check` compiles prod once that way. The chart base64-encodes the
ref tag, and `--reveal` leaves it there:

```console
chart's Secret after --reveal, without the remove entry: ?{base64:valkey/password}
```

Valkey would have taken that string as its password. The class `valkey`
therefore drops the chart's `secret.yaml` with Kapitan's `remove` input
and writes `valkey-auth` with the [kubernetes](/generators/kubernetes/)
generator from kadet-hub:

```yaml
      - input_type: remove
        input_paths:
          - compiled/${kapitan:vars:target}/valkey/valkey/templates/secret.yaml
        output_path: .
      - input_type: kadet
        input_paths: [lib/kubernetes]
        output_path: manifests
  generators:
    kubernetes:
      secrets:
        valkey-auth:
          string_data:
            default-password:
              value: ?{base64:valkey/password}
```

The chart's Deployment mounts `valkey-auth` by name and stays as it is.
The [valkey recipe](/recipes/valkey/) takes the same route for all of
Valkey: it renders the chart's objects with the generator and takes the
password as a ref.

Helmfile runs into the same limit with vals turned off.
`HELMFILE_DISABLE_VALS=true` passes `ref+` values through unresolved, so
the chart gets the `ref+` string and encodes it:

```console
chart's Secret from helmfile with HELMFILE_DISABLE_VALS=true: ref+envsubst://$VALKEY_PASSWORD
```

A reference survives only where the tool writes the value itself. On the
Kapitan side that is the generator. On the Helmfile side, as set up here,
nothing but the chart writes the Secret.

The base64 backend encodes and does not encrypt, so its ref file is as
secret as the password. Kapitan's GPG, Vault and cloud KMS backends
encrypt it, and the example does not test them.

## Release order {#needs}

`podinfo` `needs` `valkey`, and `helmfile sync` installs the releases in
two groups. Helmfile logs the order at the log level `debug`:

```console
processing 2 groups of releases in this order:
GROUP RELEASES
1     podinfo/valkey
2     podinfo/podinfo
```

When `sync` returned, Valkey's Deployment was still rolling out. `needs`
ordered the two installs, not their readiness. Helmfile's `wait` setting
waits for each release, and the example does not set it.

Kapitan has no order. Its output is files, and the tool that applies them
decides. `check` applies all of prod's files with one `kubectl apply`.
podinfo starts while Valkey is still down and connects once it is up, so
this app needs no order. An app that exits without its database would
need one from the deploy tool, such as sync waves in Argo CD or
`dependsOn` in Flux.

## Reviewing a change {#review}

Kapitan writes each target's output as files. Without `--reveal` they hold
the ref token and not the password, so the compiled directory can go into
Git. A change to `targets/prod.yml` then shows up in the same pull request
as a diff of `compiled/prod/podinfo/podinfo/templates/deployment.yaml`.

With vals on, `helmfile template` prints the Valkey password,
base64-encoded, so its output is not something to commit. A reviewer sees the change to the
environment file and works out the effect, or CI renders before and after.
`helmfile diff` compares against the releases in the cluster and needs the
helm-diff plugin. The example does not run it.

## Deployed both ways {#deploy}

`check` deploys prod to a new [kind](/glossary/#kind) cluster twice. First
`helmfile sync`, then `helmfile destroy`, then `kubectl apply` of
Kapitan's revealed output. Each time podinfo has to store a key in Valkey
and read it back, and `valkey-cli` without the password has to get
`NOAUTH`. Both passed.

After `helmfile sync`, Helm keeps a record of each release:

```console
NAME   	NAMESPACE	REVISION	UPDATED                                	STATUS  	CHART         	APP VERSION
podinfo	podinfo  	1       	2026-11-05 04:21:36.848191974 +0000 UTC	deployed	podinfo-6.17.0	6.17.0
valkey 	podinfo  	1       	2026-11-05 04:21:36.079265168 +0000 UTC	deployed	valkey-0.12.1 	9.1.3
```

After the Kapitan deploy, `helm list` is empty. Kapitan wrote files, and
kubectl applied them.

## Where each one does more

In this example Helmfile does these things that Kapitan does not:

- It installs and removes releases, with Helm's release records.
- It orders installs through `needs`.
- It resolves the password at render time, without a second step.
- It needs fewer lines and no Python.

Kapitan does these things that Helmfile does not:

- It renders every environment in one run, as files.
- It writes the Secret with a ref token, which `--reveal` fills in.
- It post-processes chart output. Here it removed the chart's Secret and
  added the generator's.
- It passes values into charts by interpolation instead of a template
  language.

## Running it

You need helm, helmfile, kind, kubectl, oras, uv, jq, openssl, Docker, and
`gh` logged in:

```console
$ git clone https://github.com/kadet-hub/examples
$ cd examples/helmfile-vs-kapitan
$ ./check
```

`check` verifies the kubernetes generator against kadet-hub's signed
[index](/glossary/#index) and its [attestation](/glossary/#attestation)
before it pulls it by digest, and does not use `kapitan compile --fetch`.
The [supply-chain guide](/guides/supply-chain-security-for-kapitan-generators/)
explains why.
