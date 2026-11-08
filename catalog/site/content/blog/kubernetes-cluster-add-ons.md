---
title: "Kubernetes cluster add-ons with one set of shared values"
date: 2026-11-08
topics: [kapitan, generators, verification]
tools: [CertManager, Prometheus, ArgoCD]
description: "cert-manager, Kyverno, Prometheus, Grafana, External Secrets, Velero and Argo CD from one Kapitan inventory with shared values, tested through one app on kind."
stack:
  recipes: [cert-manager]
  generators: [kubernetes, certmanager, kyverno, prometheus-operator, grafana, external-secrets, velero, argocd]
  example: platform-baseline
---

Before a cluster runs its first app, a small team usually adds the same
things: certificates, an admission policy, metrics and dashboards, a way to
get secrets in, backups, and a tool that deploys from Git. Each of them is
an operator that reads custom resources. Those resources name each other.
A Certificate names a ClusterIssuer, an ExternalSecret names a
ClusterSecretStore, and a Kyverno policy selects namespaces by their
labels. Kept in separate charts and manifests, each of these names is
typed again in every file that uses it.

This post keeps those resources in one [Kapitan](/glossary/#kapitan)
[inventory](/glossary/#inventory), where each shared name is set once. The
project is
[platform-baseline](https://github.com/kadet-hub/examples/tree/main/platform-baseline)
in kadet-hub/examples. Its `check` script deploys it to a new
[kind](/glossary/#kind) cluster on every change and once a week, and fails
when one of the steps below stops working. podinfo, a small demo web
server, runs on top and uses every part, so the checks go through an app
and not through the operators' own status.

## What the inventory renders

kadet-hub's [generators](/glossary/#generator) render the custom resources
an [operator](/glossary/#operator) reads. They do not install the
operator. kadet-hub publishes a [recipe](/glossary/#recipe) for
cert-manager, which renders the controller, webhook and cainjector with
the [kubernetes](/generators/kubernetes/) generator. For the other
operators there is no recipe, so `check` applies the release manifest of
each project, pinned by version and sha256.

| Component | Operator, installed from | The inventory renders |
|---|---|---|
| cert-manager 1.21.2 | recipe [cert-manager](/recipes/cert-manager/) 1.0.3 | a self-signed root CA and a CA ClusterIssuer, with [certmanager](/generators/certmanager/) 1.0.4 |
| Kyverno 1.19.2 | `install.yaml` | one ValidatingPolicy, with [kyverno](/generators/kyverno/) 1.1.4 |
| Prometheus Operator 0.94.2 | `bundle.yaml` | a Prometheus and its RBAC, with [prometheus-operator](/generators/prometheus-operator/) 1.1.6 |
| Grafana Operator 5.25.0 | `kustomize-cluster_scoped.yaml` | a Grafana and its Prometheus data source, with [grafana](/generators/grafana/) 1.0.3 |
| External Secrets 2.14.0 | `external-secrets.yaml` | a ClusterSecretStore, with [external-secrets](/generators/external-secrets/) 1.0.6, and the namespace and RBAC it reads |
| Velero 1.18.4 | `velero install` | a BackupStorageLocation and a Schedule, with [velero](/generators/velero/) 1.0.2 |
| Argo CD 3.5.6 | `install.yaml` | an AppProject and one Application per app, with [argocd](/generators/argocd/) 1.0.4 |

The release manifests of the Prometheus Operator and of External Secrets
install into the namespace `default`. Moving them takes an edited copy of
the manifest or a Helm chart rendered for another namespace, for example
through Kapitan's `helm` input. This project does neither and leaves them
in `default`.

## Kapitan in brief

A Kapitan inventory holds [classes](/glossary/#class) and
[targets](/glossary/#target), both YAML. A target lists the classes it
includes, and Kapitan merges their parameters in that order, the target's
own last. `${platform.domain}` is an
[interpolation](/glossary/#interpolation): it takes the value of that key
from the merged parameters of the target. `kapitan compile` writes each
target into `compiled/<target>/`. A generator is a Python library that
reads one section of the parameters, such as `generators.certmanager`, and
writes manifests. The
[first platform guide](/guides/first-platform/) shows the setup from an empty
directory.

This project has one target per component, `cert-manager`, `kyverno`,
`monitoring`, `external-secrets`, `velero` and `argocd`, and the target
`podinfo` for the app. All of them include two classes. `generators` pins
the generators by version and [digest](/glossary/#digest). `platform`
holds the values that resources in more than one target read. The recipe
is written for the omegaconf inventory backend, which `.kapitan` selects:

```yaml
global:
  inventory-backend: omegaconf
```

## Fetch and verify

Kapitan 0.36.3 reads the inventory before it fetches dependencies, so the
cert-manager recipe is pinned in a separate fetch inventory,
`fetch/targets/recipes.yml`:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/recipes/cert-manager:1.0.3@sha256:99d27b9b0ed0afa330d48e1b12cc0bee25f37c5a4b5129ba07a68dfe5063bbef
        output_path: inventory/classes/recipes/cert-manager
```

`check` does not compile it with `--fetch`, which checks neither digests
nor [attestations](/glossary/#attestation). It runs the steps of the
registry's
[consumer docs](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#verifying-a-recipe-by-hand)
instead. For the recipe:

```sh
id=https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
gh release download --repo kadet-hub/registry --pattern 'index.json*'
gh attestation verify index.json --bundle index.json.sigstore.json --owner kadet-hub --cert-identity "$id"
d=sha256:99d27b9b0ed0afa330d48e1b12cc0bee25f37c5a4b5129ba07a68dfe5063bbef
jq --arg d "$d" '.recipes["cert-manager"] | to_entries[] | select(.value.digest == $d) | {version: .key, yanked: .value.yanked}' index.json
gh attestation verify "oci://ghcr.io/kadet-hub/recipes/cert-manager@$d" --owner kadet-hub --cert-identity "$id"
tmp=$(mktemp -d)
oras pull -o "$tmp" "ghcr.io/kadet-hub/recipes/cert-manager@$d"
mkdir -p inventory/classes/recipes/cert-manager
tar -xf "$tmp/cert-manager.tar" -C inventory/classes/recipes/cert-manager --no-same-owner
```

The first attestation check proves that the registry's release workflow
signed the [index](/glossary/#index). The `jq` line must print version
`1.0.3` and `yanked: null`. The second attestation check proves the
release workflow published the recipe at that digest. The generators go
through the same steps against `.generators` in the index and unpack into
`lib/<name>`. `inventory/classes/generators.yml` pins seven of them:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/certmanager:1.0.4@sha256:99bfa0edf76fd7f564c101ce7dedbd2e0a790825db0173f1a64faed51bc0fd1f
        output_path: lib/certmanager
      - type: oci
        source: ghcr.io/kadet-hub/kyverno:1.1.4@sha256:af3f1376bdc69e261bb75d23c01014a24926e14f52780c86d8e941c524525de6
        output_path: lib/kyverno
      - type: oci
        source: ghcr.io/kadet-hub/prometheus-operator:1.1.6@sha256:99faa008d1335edc787f164685a04e855012b6b48364e67737fb764bb98c449b
        output_path: lib/prometheus-operator
      - type: oci
        source: ghcr.io/kadet-hub/external-secrets:1.0.6@sha256:184e8a60f92c0c09eae32973ceaf909b2da53457e88233161ffb90c4b9a63e60
        output_path: lib/external-secrets
      - type: oci
        source: ghcr.io/kadet-hub/velero:1.0.2@sha256:95c56a6cf87a55863b987e58fd2d21cea24c67b91ff9bac2fec2d796c8c8f46b
        output_path: lib/velero
      - type: oci
        source: ghcr.io/kadet-hub/argocd:1.0.4@sha256:8b41817b189cdc043bb1a726f0e42a827672a1eda80e8d8406b512262182feea
        output_path: lib/argocd
      - type: oci
        source: ghcr.io/kadet-hub/grafana:1.0.3@sha256:a31a55e6eb06eeb6c28ed61e12b8971b0c23ab446eb3f8d7e43bd1b290cbf836
        output_path: lib/grafana
```

The eighth, kubernetes 1.14.0, comes from the recipe's own classes. A
second pin of it would unpack into the same `lib/kubernetes`, so `check`
fails when one generator is pinned at two digests. The targets
`monitoring`, `external-secrets` and `podinfo` use the kubernetes
generator too, and get the version the recipe pins.

## The shared class

`inventory/classes/platform.yml`:

```yaml
parameters:
  platform:
    # App hostnames are <app>.<domain>.
    domain: apps.example.com
    # The ClusterIssuer that signs the apps' certificates, and its CA.
    issuer: platform-ca
    # The ClusterSecretStore that apps read their secrets from.
    secret_store: platform
    namespaces:
      cert_manager: cert-manager
      monitoring: monitoring
      # Holds the secrets the store serves; Velero backs it up.
      secrets: platform-secrets
    # The repository Argo CD deploys the apps from.
    git_repo: http://gitea.git.svc.cluster.local:3000/kadet/apps.git
    # Argo CD labels every app namespace it creates with these, and the
    # Kyverno policy applies to the namespaces that carry them.
    tenant_labels:
      platform.example.com/tenant: "true"
      pod-security.kubernetes.io/enforce: restricted
```

| Value | Read by |
|---|---|
| `domain` | the root CA's common name in `cert-manager`, podinfo's DNS name in `podinfo` |
| `issuer` | the CA ClusterIssuer and its CA Certificate in `cert-manager`, the `issuerRef` of podinfo's Certificate |
| `secret_store` | the ClusterSecretStore in `external-secrets`, the store of podinfo's ExternalSecret |
| `namespaces.cert_manager` | the recipe's namespace and the CA Certificate in `cert-manager` |
| `namespaces.monitoring` | Prometheus, Grafana and the data source URL in `monitoring` |
| `namespaces.secrets` | the store's namespace, ServiceAccount and Role in `external-secrets`, the Schedule in `velero` |
| `git_repo` | the AppProject and the Applications in `argocd` |
| `tenant_labels` | the namespace labels in `argocd`, the namespace selector in `kyverno` |

The label `pod-security.kubernetes.io/enforce: restricted` makes the API
server enforce the restricted Pod Security profile in every app namespace.
The other label exists for the Kyverno selector. Both live in one map, so
the selector matches exactly the namespaces Argo CD creates.

## The platform targets

### cert-manager

`inventory/targets/cert-manager.yml`:

```yaml
classes:
  - generators
  - platform
  - recipes.cert-manager
  - recipes.cert-manager.crds
parameters:
  namespace: ${platform.namespaces.cert_manager}
  kapitan:
    vars:
      target: cert-manager
    compile:
      - {input_type: kadet, output_type: yml, input_paths: [lib/certmanager], output_path: issuers}
  generators:
    kubernetes:
      namespaces:
        cert-manager:
          name: ${platform.namespaces.cert_manager}
    certmanager:
      # A self-signed root CA and the ClusterIssuer that signs with it.
      ca_issuers:
        platform:
          name: ${platform.issuer}
          namespace: ${platform.namespaces.cert_manager}
          common_name: ${platform.domain} root CA
```

The two recipe classes add the operator and its CRDs, compiled into
`compiled/cert-manager/manifests`. The recipe renders no Namespace, so the
target adds one through the kubernetes generator. The `compile` entry adds the
certmanager generator, whose output goes to
`compiled/cert-manager/issuers`. `check` applies the second directory
only once cert-manager's webhook runs. One `ca_issuers` entry renders three
objects. The ClusterIssuer `platform-ca-selfsigned` signs the CA
Certificate `platform-ca`, an ECDSA P-256 key and certificate that
cert-manager stores in the Secret `platform-ca`. The ClusterIssuer
`platform-ca` signs app certificates with that CA. A ClusterIssuer reads
its CA Secret from cert-manager's own namespace, which is why the entry
sets `namespace`.

### Kyverno

`inventory/targets/kyverno.yml`:

```yaml
classes:
  - generators
  - platform
parameters:
  kapitan:
    vars:
      target: kyverno
    compile:
      - {input_type: kadet, output_type: yml, input_paths: [lib/kyverno], output_path: .}
  generators:
    kyverno:
      validating_policies:
        require-image-digest:
          match_kinds: [Pod]
          match_constraints:
            namespaceSelector:
              matchLabels: ${platform.tenant_labels}
          validation_actions: [Deny]
          validations:
            - expression: >-
                object.spec.containers.all(c, c.image.contains('@sha256:')) &&
                (!has(object.spec.initContainers) ||
                object.spec.initContainers.all(c, c.image.contains('@sha256:')))
              message: Images in app namespaces must be pinned by digest.
```

A ValidatingPolicy is Kyverno's policy kind with rules in CEL, the
expression language of Kubernetes' own admission policies. `Deny` rejects a
violating request, which is Kyverno's enforce mode. The policy requires
every container image in an app namespace to carry a digest, because a tag
can be moved to other content and a digest cannot. `match_kinds: [Pod]` is
a generator shorthand for the rule on `pods` with the operations `CREATE`
and `UPDATE`. Kyverno derives the same rule for Deployments, StatefulSets,
DaemonSets, ReplicaSets, Jobs and CronJobs, as the policy's status lists.
`check` tests the rule on pods only. Namespaces without the tenant labels
are not checked, so the operators' own images, which their manifests name
by tag, still run.

### Prometheus and Grafana

`inventory/targets/monitoring.yml`:

```yaml
classes:
  - generators
  - platform
parameters:
  namespace: ${platform.namespaces.monitoring}
  kapitan:
    vars:
      target: monitoring
    compile:
      - {input_type: kadet, output_type: yml, input_paths: [lib/kubernetes], output_path: .}
      - {input_type: kadet, output_type: yml, input_paths: [lib/prometheus-operator], output_path: .}
      - {input_type: kadet, output_type: yml, input_paths: [lib/grafana], output_path: .}
  generators:
    kubernetes:
      namespaces:
        monitoring:
          name: ${platform.namespaces.monitoring}
    prometheus_operator:
      prometheuses:
        platform:
          rbac: true
          retention: 2d
          service_monitor_selector: {}
          service_monitor_namespace_selector: {}
          resources:
            requests: {cpu: 100m, memory: 256Mi}
            limits: {memory: 1Gi}
    grafana:
      instance_selector:
        grafana: platform
      instances:
        platform:
          labels:
            grafana: platform
      datasources:
        prometheus:
          uid: prometheus
          datasource:
            name: Prometheus
            type: prometheus
            access: proxy
            url: http://prometheus-operated.${platform.namespaces.monitoring}.svc:9090
            isDefault: true
```

`rbac: true` adds the ServiceAccount, ClusterRole and ClusterRoleBinding
that the Prometheus Operator's RBAC guide lists. `retention: 2d` keeps
two days of samples. The two empty selectors
pick every ServiceMonitor in every namespace. An unset selector would pick
none. The Grafana Operator imports a GrafanaDatasource into every Grafana
instance whose labels match `instance_selector`. `prometheus-operated` is
the headless Service the Prometheus Operator creates in each namespace
that has a Prometheus.

### External Secrets with the Kubernetes provider

`inventory/targets/external-secrets.yml`:

```yaml
classes:
  - generators
  - platform
parameters:
  namespace: ${platform.namespaces.secrets}
  kapitan:
    vars:
      target: external-secrets
    compile:
      - {input_type: kadet, output_type: yml, input_paths: [lib/kubernetes], output_path: .}
      - {input_type: kadet, output_type: yml, input_paths: [lib/external-secrets], output_path: .}
  generators:
    kubernetes:
      namespaces:
        secrets:
          name: ${platform.namespaces.secrets}
      service_accounts:
        store-reader: {}
      rbac:
        store-reader:
          namespace: ${platform.namespaces.secrets}
          service_accounts: [store-reader]
          rules:
            - {apiGroups: [""], resources: [secrets], verbs: [get, list, watch]}
    external_secrets:
      clustersecretstores:
        platform:
          name: ${platform.secret_store}
          spec:
            provider:
              kubernetes:
                remoteNamespace: ${platform.namespaces.secrets}
                server:
                  caProvider:
                    type: ConfigMap
                    name: kube-root-ca.crt
                    key: ca.crt
                    namespace: ${platform.namespaces.secrets}
                auth:
                  serviceAccount:
                    name: store-reader
                    namespace: ${platform.namespaces.secrets}
```

The store uses External Secrets' Kubernetes provider. Through it,
External Secrets reads Secrets from the namespace `platform-secrets` with
a token of the ServiceAccount `store-reader`, which may read Secrets there
and nowhere else.
`kube-root-ca.crt` is the ConfigMap with the API server's CA that
Kubernetes puts into every namespace. The provider was picked because CI
can run it without an outside service. For Vault or a cloud secret
manager, the ClusterSecretStore gets another `provider` block. The
ExternalSecret below keeps its store reference, and its `remoteRef` keys
follow the new provider's layout. The fake provider would also run in CI,
but it serves values written into the store itself, so no sync from
another place would be tested.

### Velero with S3-compatible storage

`inventory/targets/velero.yml`:

```yaml
classes:
  - generators
  - platform
parameters:
  kapitan:
    vars:
      target: velero
    compile:
      - {input_type: kadet, output_type: yml, input_paths: [lib/velero], output_path: .}
  generators:
    velero:
      backup_storage_locations:
        default:
          provider: aws
          bucket: velero
          config:
            region: us-east-1
            s3ForcePathStyle: "true"
            s3Url: http://s3.s3.svc:7070
          credential:
            name: velero-s3
            key: cloud
      schedules:
        secrets:
          schedule: CRON_TZ=UTC 0 3 * * *
          skip_immediately: true
          template:
            included_namespaces: ["${platform.namespaces.secrets}"]
            ttl: 168h0m0s
```

Velero writes backups to S3-compatible storage through its AWS plugin.
`s3ForcePathStyle` puts the bucket into the URL path, which servers
without per-bucket host names need. The generator marks the only location
as the default. The Schedule backs up the secrets namespace daily at 03:00
UTC and keeps each backup for seven days (`168h0m0s`). `skip_immediately`
stops Velero from running a backup the moment the Schedule is created.
The Secret `velero-s3` with the keys is not in the inventory. `check`
creates it at run time, as the keys of a real bucket would come from
outside the repository.

The S3 server is
[Versity's S3 gateway](https://github.com/versity/versitygw) 1.10.0
(Apache-2.0), in `s3-server.yaml` next to the inventory. Its posix backend
stores a bucket as a directory, so `mkdir` creates Velero's bucket. MinIO
was the first candidate. On 4 November 2026 neither `quay.io/minio/minio`
nor `docker.io/minio/minio` listed its tags to an anonymous client, so
there was no image to pin by digest.

### Argo CD

`inventory/targets/argocd.yml`:

```yaml
classes:
  - generators
  - platform
parameters:
  kapitan:
    vars:
      target: argocd
    topics:
      argocd:
        consume: true
    compile:
      - {input_type: kadet, output_type: yml, input_paths: [lib/argocd], output_path: .}
  generators:
    argocd:
      projects:
        apps:
          source_repos: ["${platform.git_repo}"]
          destinations:
            - {namespace: "*", server: https://kubernetes.default.svc}
          # The namespace that CreateNamespace=true creates; no other
          # cluster-scoped kind.
          cluster_resource_whitelist:
            - {group: "", kind: Namespace}
      topics:
        argocd:
          project: apps
          source:
            repoURL: ${platform.git_repo}
            targetRevision: main
            directory:
              recurse: true
          sync_policy:
            automated: {prune: true, selfHeal: true}
            syncOptions: [CreateNamespace=true]
            managedNamespaceMetadata:
              labels: ${platform.tenant_labels}
```

A Kapitan topic lets one target read parameters that other targets
publish. Every target that publishes `argocd` gets one Application, with
the values under `topics.argocd` as defaults. An app team then adds a
target, and the target `argocd` stays unchanged. Each Application syncs
automatically, prunes what Git no longer holds and undoes manual changes.
`CreateNamespace=true` creates the app's namespace with the tenant labels
from `managedNamespaceMetadata`. Argo CD refused that namespace until
`Namespace` was in the project's `cluster_resource_whitelist`. Without
`directory.recurse` it read only the top level of the app's path. The
generators write one directory per namespace below it, so Argo CD found no
manifest and still reported the Application `Synced` and `Healthy`.

## The app

`inventory/targets/podinfo.yml`:

```yaml
classes:
  - generators
  - platform
parameters:
  namespace: podinfo
  kapitan:
    vars:
      target: podinfo
    topics:
      argocd:
        parameters:
          source:
            path: podinfo
          destination: ${namespace}
    compile:
      - {input_type: kadet, output_type: yml, input_paths: [lib/kubernetes], output_path: .}
      - {input_type: kadet, output_type: yml, input_paths: [lib/certmanager], output_path: .}
      - {input_type: kadet, output_type: yml, input_paths: [lib/external-secrets], output_path: .}
      - {input_type: kadet, output_type: yml, input_paths: [lib/prometheus-operator], output_path: .}
  generators:
    manifest:
      default_config:
        recommended_labels: true
        security_profile: restricted
    certmanager:
      certs:
        # No sync wave: the generator renders no annotations, and a missing
        # Secret volume only holds the pod in ContainerCreating.
        podinfo-tls:
          spec:
            secretName: podinfo-tls
            issuerRef: {name: "${platform.issuer}", kind: ClusterIssuer}
            dnsNames: ["podinfo.${platform.domain}"]
    external_secrets:
      externalsecrets:
        # Before the Deployment, whose env reads the Secret.
        podinfo-message:
          annotations:
            argocd.argoproj.io/sync-wave: "-1"
          cluster_store: ${platform.secret_store}
          refresh_interval: 10s
          spec:
            data:
              - secretKey: message
                remoteRef: {key: podinfo, property: message}
    prometheus_operator:
      service_monitors:
        podinfo:
          selector: {name: podinfo}
          endpoints: http
  components:
    podinfo:
      image: ghcr.io/stefanprodan/podinfo:6.15.0@sha256:ec73780a8425f59ea49f5bc8cdff0d598805a224fbaa1f86c67a244f250fa9da
      command: [./podinfo, --port=8080, --secure-port=8443, --cert-path=/data/cert]
      security_context: {runAsUser: 65534}
      ports:
        http: {container_port: 8080, service_port: 80}
        https: {container_port: 8443, service_port: 443}
      env:
        PODINFO_UI_MESSAGE:
          secretKeyRef: {name: podinfo-message, key: message}
      volumes:
        tls:
          secret: {secretName: podinfo-tls}
      volume_mounts:
        tls: {mount_path: /data/cert, read_only: true}
      healthcheck:
        readiness: {type: http, port: http, path: /readyz}
      resources:
        requests: {cpu: 50m, memory: 64Mi}
        limits: {memory: 128Mi}
      service: {type: ClusterIP}
```

The target uses four generators and renders five resources. The
kubernetes generator writes the Deployment and the Service, the other
three the Certificate, the ExternalSecret and the ServiceMonitor. podinfo serves HTTPS on 8443 with the certificate that
cert-manager writes into the Secret `podinfo-tls`. It puts the
environment variable `PODINFO_UI_MESSAGE` into the `message` field of its
JSON response, and that variable comes from the Secret the ExternalSecret
creates. `security_profile: restricted` sets the pod and container fields
that the restricted Pod Security profile requires, and `runAsUser: 65534`
gives the image's user a number the kubelet can check.

The ExternalSecret has the Argo CD sync wave `-1`. Argo CD applies it
first and creates the Deployment only once the ExternalSecret reports its
Secret synced. A pod that starts before its env Secret exists waits with
`CreateContainerConfigError`. The certmanager generator 1.0.4 renders no
`annotations` and drops the key without a warning, so the Certificate has
no wave. Until cert-manager writes `podinfo-tls`, the pod waits in
`ContainerCreating` for its volume and then starts.

## One value, two targets

`check` compiles a copy of the inventory with `domain: apps.example.org`
and fails unless exactly two files change. In the CI run:

```diff
--- a/compiled/cert-manager/issuers/cert-manager/platform-ca-cert.yml
+++ b/compiled/cert-manager/issuers/cert-manager/platform-ca-cert.yml
@@ -6,7 +6,7 @@
   name: platform-ca
   namespace: cert-manager
 spec:
-  commonName: apps.example.com root CA
+  commonName: apps.example.org root CA
   isCA: true
   issuerRef:
     group: cert-manager.io
--- a/compiled/podinfo/podinfo/podinfo-tls-cert.yml
+++ b/compiled/podinfo/podinfo/podinfo-tls-cert.yml
@@ -7,7 +7,7 @@
   namespace: podinfo
 spec:
   dnsNames:
-    - podinfo.apps.example.com
+    - podinfo.apps.example.org
   issuerRef:
     kind: ClusterIssuer
     name: platform-ca
```

Both changes come from the one line in `platform.yml`. The root CA and
podinfo's certificate are in different targets, and different steps
apply them: `check` applies the CA, Argo CD the certificate.

## Install order

`check` creates the cluster and applies all operators at once, so that
their images pull side by side. cert-manager comes from
`compiled/cert-manager/manifests`. The four release manifests go in with
`kubectl apply --server-side`, because some of their CRDs are larger than
the annotation of a client-side apply may be. Argo CD goes in two steps.
Its redis comes first, until redis' init container has created the Secret
that the other Argo CD pods need. Velero comes from `velero install`.
That command names the plugin's init container
`velero-velero-plugin-for-aws:v1-14-4` when the plugin image is given as
tag and digest, and the API server rejects the name. `check` renders the
install with `--dry-run -o json`, sets the name the CLI gives the same
image without a digest, and applies the result.

Once every Deployment is available, `check` applies the platform targets.
Each apply is repeated for up to a minute, because a webhook can refuse
connections for a few seconds after its Deployment is available. `check`
then waits for the ClusterIssuer, the ClusterSecretStore and the backup
location to report ready, for the policy, the Prometheus, the Grafana and
its data source. External Secrets defines a kind `Grafana` too, in
`generators.external-secrets.io`, so `kubectl get grafana` finds that one,
and `check` uses the full name `grafanas.grafana.integreatly.org`.

Last, `check` pushes `compiled/podinfo` as one commit to an in-cluster
Gitea and applies the target `argocd`.

## What check tests

Argo CD must report the Application `Synced` at the pushed commit and
`Healthy`, with five resources, one per compiled file. Argo CD's built-in
health checks cover the Certificate and the ExternalSecret, so `Healthy`
also means the certificate was issued and the Secret synced.

The certificate test fetches podinfo's root URL over a port-forward, with
the CA certificate from the Secret `platform-ca` as the only trusted root:

```sh
curl --cacert ca.crt --resolve podinfo.apps.example.com:18443:127.0.0.1 https://podinfo.apps.example.com:18443/
```

`--resolve` sends the request to the port-forward under the certificate's
name, so curl checks the name without DNS. The `message` in the response
must be the random value that `check` wrote into the secrets namespace.

The policy test creates the same pod twice in the namespace `podinfo`,
once with `ghcr.io/stefanprodan/podinfo:6.15.0` and once with that tag and
its digest. The first must be denied with the policy's message, and the
second must become ready. A server-side dry run of the tag-only pod in
`default` must pass, which shows that the labels decide.

The metrics test asks Prometheus, through the API server's service proxy,
for `up{namespace="podinfo"}`. `up` is 1 for each target Prometheus
scraped at its last attempt and 0 for each one it could not. Every series
must be 1, and there must be at least one. Grafana must return the same
through its data source `prometheus`.

The sync test changes the message in the secrets namespace and waits until
podinfo's Secret holds the new value. The refresh interval is ten seconds.

The backup test runs a backup from the Schedule, deletes the namespace
`platform-secrets`, restores the backup and compares the restored message
with the changed one. It backs up the secrets namespace because Git does
not hold its content. A backup of podinfo's namespace would prove nothing,
because Argo CD recreates it from Git after a delete.

## What the CI run showed

[Run 41932257899](https://github.com/kadet-hub/examples/actions/runs/41932257899)
of the examples workflow tested commit `2176ba4` of
[kadet-hub/examples#135](https://github.com/kadet-hub/examples/pull/135)
on 4 November 2026, on GitHub's `ubuntu-24.04` runner. The durations below
are what `check` printed, in whole seconds, or come from the log's
timestamps.

Verifying the index, the recipe and eight generators and pulling them took
45 seconds. Installing Kapitan with uv and compiling took 7 more, for 65
files: 43 in `cert-manager`, 7 in `monitoring`, 5 each in
`external-secrets` and `podinfo`, 2 each in `argocd` and `velero`, and 1 in
`kyverno`. kind had the cluster ready 42 seconds after it started creating
it.

From the first apply until every operator's Deployment was available took
93 seconds, image pulls included. The platform targets took 86 seconds
until the ClusterIssuer, the ClusterSecretStore, the backup location, the
policy, the Prometheus, the Grafana and its data source were ready. Argo
CD reported podinfo `Synced` at the pushed commit and `Healthy` 10 seconds
after the Application was applied.

podinfo's certificate was issued by `CN = apps.example.com root CA` for
`DNS:podinfo.apps.example.com`, valid from 4 November 2026 23:37:22 UTC to
2 February 2027. That is cert-manager's default lifetime of 90 days. The
response carried the message `check` had written into the secrets
namespace. Kyverno denied the tag-only pod with:

```text
Error from server: error when creating "STDIN": admission webhook "vpol.validate.kyverno.svc-fail" denied the request: Policy require-image-digest failed: Images in app namespaces must be pinned by digest.
```

The pod with the digest became ready, and the dry run in `default` passed.
Prometheus returned one `up` series for podinfo, with the value 1, 27
seconds after Argo CD reported `Healthy`. Its labels name the job and the
Service `podinfo`, the port `http` and podinfo's pod. Grafana 13.1.3
returned the same series through its data source. A changed
message reached podinfo's Secret after 6 seconds. The Velero backup of
`platform-secrets` completed in 1 second with 7 items, and so did the
restore after the namespace was deleted.

After the checks, the cluster ran 34 pods from 28 images. Their memory
working set, read from the kubelet's summary API, was 2924 MiB in total:

| Namespace | MiB |
|---|---|
| `kube-system` | 1755 |
| `argocd` | 387 |
| `monitoring` | 191 |
| `kyverno` | 179 |
| `default` (Prometheus Operator, External Secrets) | 138 |
| `cert-manager` | 105 |
| `git` (Gitea) | 95 |
| `velero` | 24 |
| `grafana` (Grafana Operator) | 19 |
| `podinfo` | 14 |
| `s3` (S3 gateway) | 10 |
| `local-path-storage` | 7 |

`kube-system` holds the API server, etcd, the controller manager, the
scheduler, CoreDNS, kube-proxy and kindnet. `check` took 335 seconds in all,
and the job took 5 minutes and 56 seconds.

That run used grafana 1.0.2. The pin above is 1.0.3, which adds the
LICENSE to the artifact and renders the same output.
[kadet-hub/examples#139](https://github.com/kadet-hub/examples/pull/139)
moved the project to it, and
[run 41956633556](https://github.com/kadet-hub/examples/actions/runs/41956633556)
passed with it.

## What it leaves out

Ingress and TLS from outside. All Services are `ClusterIP`, and the
certificates come from a private CA. A public hostname needs an ingress or
Gateway API controller and an ACME issuer, which the certmanager generator
renders from `letsencrypt` and `http01_ingress_class` in a
`clusterissuers` entry.

The operators in the inventory. Only cert-manager is compiled from it.
The others come from release manifests that `check` applies, and two of
them sit in `default`.

NetworkPolicies. The cluster keeps kind's own CNI, kindnet. The
[cilium](/generators/cilium/) generator renders Cilium network policies,
not Cilium itself, so using it would mean installing Cilium as the CNI
first. Nothing here limits which pods reach podinfo, Prometheus or the S3
gateway over the network.

The AppProject's reach. `apps` lets an Application deploy into any
namespace, a platform namespace included. A project shared with other
teams lists the namespaces it allows.

High availability and storage. Every operator runs one replica, as its
manifest ships it. Prometheus
and Grafana keep their data in `emptyDir` volumes, so a restarted pod
starts empty. Velero backs up Kubernetes objects only. It runs without its
node agent and without volume snapshots, so data in volumes is not backed
up. It also writes Secrets to the bucket as they are, readable for anyone
with the bucket's keys.

Alerting, rules and dashboards. There is no Alertmanager, no
PrometheusRule and no Grafana dashboard. Grafana's admin password is the
random one the Grafana Operator creates in the Secret
`platform-admin-credentials`.

Logs and traces. Loki and the OpenTelemetry Operator have generators in
the catalog, and neither is in this baseline.
