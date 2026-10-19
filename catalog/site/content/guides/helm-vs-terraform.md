---
title: Helm vs Terraform for Kubernetes, and Kapitan for both
layout: prose
description: "Helm vs Terraform for Kubernetes manifests: what the helm and kubernetes providers plan without a cluster, and one Kapitan inventory feeding both."
---

Helm and Terraform can both put objects into a Kubernetes cluster; Helm
stops there, Terraform also manages the cloud resources around it. This guide compares them on a
concrete case: an S3 bucket and the app that writes to it, where the
bucket name and region have to match in the Terraform resource and in the
app's ConfigMap. The example is
[`helm-vs-terraform`](https://github.com/kadet-hub/examples/tree/main/helm-vs-terraform)
in kadet-hub/examples; its `check` runs in CI weekly and fails when a
result quoted below no longer holds. It runs OpenTofu 1.13.1 with
hashicorp/aws 6.69.1, hashicorp/kubernetes 3.3.0 and hashicorp/helm 3.3.0,
with dummy AWS keys and no kubeconfig.

## What each tool covers

| | Helm | Terraform |
|---|---|---|
| Describes | Kubernetes resources, from Go templates and values | any resource a provider offers: cloud, SaaS, Kubernetes |
| Cloud resources such as a bucket | only as [custom resources](/glossary/#crd) for a controller in the cluster, for example Crossplane | directly, through the cloud's provider |
| State | release history, stored as [Secrets in the cluster](https://helm.sh/docs/topics/advanced/#storage-backends) by default | a state file with every managed resource |
| A value from one resource in another | no: templates read the release's values; `lookup` reads objects already in the cluster | yes, references such as `aws_s3_bucket.uploads.bucket` |
| Preview | `helm template`, `helm install --dry-run` | `plan` |

A chart is ["a collection of files that describe a related set of Kubernetes
resources"](https://helm.sh/docs/topics/charts/). With Helm and Terraform as
separate tools, the bucket name lives twice: once in the Terraform
configuration and once in the chart's values, and neither tool checks that the
two agree.

## Terraform alone: the kubernetes and helm providers

Terraform can write the ConfigMap itself, so the bucket name is set once
and reaches Kubernetes through a reference. The example's
[`terraform-only`](https://github.com/kadet-hub/examples/tree/main/helm-vs-terraform/terraform-only)
module does this three ways. Planned against an empty state, without a
cluster:

| Resource | `tofu plan` without a cluster | What the plan shows |
|---|---|---|
| `kubernetes_config_map_v1` | succeeds | the ConfigMap's `data` with bucket and region |
| `helm_release` | succeeds | the `set` values; `manifest` is `null`, so the rendered objects are not in the plan |
| `helm_release` with `experiments = { manifest = true }` | fails: "Kubernetes cluster unreachable" | |
| `kubernetes_manifest` | fails: "cannot create REST client: no client config" | |

The `kubernetes_manifest` failure is
[documented](https://registry.terraform.io/providers/hashicorp/kubernetes/3.3.0/docs/resources/manifest):
the resource "requires API access during planning time", so the cluster
cannot be created in the same apply. The helm provider's `manifest`
[experiment](https://registry.terraform.io/providers/hashicorp/helm/3.3.0/docs#experiments)
stores the rendered manifest so that the plan shows the full diff; in the
example it then fails to plan without the cluster, like
`kubernetes_manifest`.

The kubernetes provider's
[documentation](https://registry.terraform.io/providers/hashicorp/kubernetes/3.3.0/docs)
also warns against configuring it from resources created in the same
module, such as the cluster itself, and recommends separate applies for
the cluster and the resources in it. Every Kubernetes object Terraform
manages is also recorded in its [state](https://opentofu.org/docs/language/state/),
next to the bucket.

What Terraform alone does better: a reference carries values known only
after apply, such as the bucket's ARN or a database endpoint, into the
ConfigMap. The approach below resolves values before anything is applied
and cannot do that.

## One inventory for both

[Kapitan](/glossary/#kapitan) renders files from an
[inventory](/glossary/#inventory) through [generators](/glossary/#generator).
In the example one [target](/glossary/#target) sets the two values:

```yaml
parameters:
  bucket: example-shop-uploads-prod
  region: eu-central-1
```

A [class](/glossary/#class) hands them to two kadet-hub generators through
`${...}` [interpolation](/glossary/#interpolation): the
[terraform-aws](/generators/terraform-aws/) generator, which writes an
OpenTofu root module in JSON syntax with the bucket, its public access
block, encryption, versioning and a TLS-only policy, and the
[kubernetes](/generators/kubernetes/) generator, which writes the app's
Deployment, Service and ConfigMap:

```yaml
parameters:
  generators:
    terraform-aws:
      region: ${region}
      s3_bucket:
        uploads:
          bucket: ${bucket}
  components:
    web:
      env:
        S3_BUCKET:
          configMapKeyRef: {key: bucket}
      config_maps:
        config:
          data:
            bucket: {value: "${bucket}"}
            region: {value: "${region}"}
```

The check compiles the target, validates the manifests with kubeconform,
and runs `tofu validate` and `tofu plan` on the compiled module. It fails
unless the planned `aws_s3_bucket` and the ConfigMap hold the same bucket
and region. It then changes both values in the target file only,
compiles again and requires the new values in both outputs:

```text
tofu plan aws_s3_bucket.uploads: example-shop-uploads-prod eu-central-1
ConfigMap shop/web data:         example-shop-uploads-prod eu-central-1
tofu plan aws_s3_bucket.uploads: example-shop-uploads-staging eu-west-1
ConfigMap shop/web data:         example-shop-uploads-staging eu-west-1
```

Compiling needs no cluster and no cloud account, and the example plans
with dummy AWS keys. The manifests are files for
`kubectl`, Argo CD or Flux, reviewed as a diff in Git and kept out of
Terraform state; the root module is applied with `tofu apply` as usual. The
two applies stay separate, which is what the kubernetes provider's
documentation recommends anyway. Both generators are pulled by
[digest](/glossary/#digest) after `gh attestation verify` checks their
[attestations](/glossary/#attestation), and the providers are pinned by
hash in `.terraform.lock.hcl`.

The trade-off is the one above: the inventory knows values before
anything is applied. A value only the cloud knows afterwards still has to
come from a Terraform output, a data source or an operator in the cluster.

## Which one

- Helm, for third-party software whose vendor maintains a chart, and when
  release history and `helm rollback` matter more than shared values.
- Terraform alone, when values only known after apply must reach
  Kubernetes, and you accept Kubernetes objects in Terraform state and a
  reachable cluster for `kubernetes_manifest`.
- One Kapitan inventory, when the shared values are configuration you
  choose, such as names, regions and sizes, and you want reviewed files
  for both Terraform and Kubernetes from one source.

[Helm alternatives for Kubernetes](/guides/helm-alternatives-for-kubernetes/)
compares Helm with Kustomize, Pulumi, cdk8s, Tanka and Kapitan on one app,
and [a first platform from four generators](/blog/first-platform/) shows a
complete Kapitan project with kadet-hub generators.
