---
title: "Timoni vs Kapitan: CUE schemas and bundles pinned by digest"
date: 2026-11-13
topics: [kapitan, comparison, validation, supply chain]
tools: [Timoni, CUE]
description: "A Timoni bundle with its module and a Kapitan inventory render one app to identical manifests. Also tested: a misspelled value and a module tag that moved."
---

[Timoni](https://timoni.sh/) builds Kubernetes objects from modules
written in [CUE](https://cuelang.org/). A module declares a schema for its
values, and Timoni rejects values that do not fit it. Modules are published as OCI
artifacts, and a bundle lists the instances to build, each with its module
by registry URL, version and digest. [Kapitan](/glossary/#kapitan) reads
YAML from an [inventory](/glossary/#inventory) and passes it to a
[generator](/glossary/#generator), here the kadet-hub
[kubernetes](/generators/kubernetes/) generator, pinned by
[digest](/glossary/#digest).

The
[example](https://github.com/kadet-hub/examples/tree/main/timoni-vs-kapitan)
renders the app of the [Helm vs Kustomize vs Kapitan guide](/guides/same-app/)
with both tools. Its `check` fails unless the manifests match for each
environment. It also tests two differences: a misspelled value, and a
module tag that moves after the bundle pinned it. CI runs `check` on every
change and once a week.

## The app and the check

Namespace `shop`, apps `web` and `api` with a Deployment, a Service and a
ConfigMap each, the restricted Pod Security profile, environments dev and
prod, PodDisruptionBudgets in prod only. The api's ConfigMap carries
`web_url`, built from the web Service's port.

- Timoni 0.37.0, which embeds CUE 0.17.1, with the Kubernetes 1.37 API
  schemas that `timoni mod vendor k8s -v 1.37` wrote into the module.
- Kapitan 0.36.3 with the kubernetes generator 1.14.0 and the inventory of
  the [cdk8s vs Tanka vs Kapitan guide](/guides/config-tools/).

`check` sorts the objects and their keys and drops one label,
`app.kubernetes.io/managed-by`, which only the generator sets. Nothing
else is dropped:

```console
$ ./check
dev: timoni = kapitan (6 objects)
prod: timoni = kapitan (8 objects)
timoni: replica rejected (replica: field not allowed)
kapitan: replica compiled, web gets replicas: 1
timoni: pinned bundle rejected after the tag moved (digest doesn't match)
timoni: unpinned bundle built the new push
```

## Module and bundle

The Timoni side has two parts. The module `timoni/app` holds the schema of
the values and one template per kind. The schema is `#Config` in
`templates/config.cue`:

```cue
#Config: {
	metadata: {
		name:      string
		namespace: string
	}

	image!:   string
	replicas: *1 | int & >0
	port: {
		container!: int & >0 & <=65535
		service:    *80 | int & >0 & <=65535
	}
	readinessPath!: string
	resources!:     corev1.#ResourceRequirements
	config: {
		mount!: string
		data: [string]: string
	}
	// A PodDisruptionBudget is rendered only when this is set.
	pdbMinAvailable?: int & >0
}
```

A `!` marks a field that has to be set, `*1` a default, `?` an optional
field. `resources` takes its type from the vendored Kubernetes schema, and
each template unifies its object with the Kubernetes type, such as
`appsv1.#Deployment`.

The bundle `timoni/shop.cue` names the module and holds the values both
environments share. `dev.cue` and `prod.cue` add the rest, and Timoni
unifies the files passed with `-f`:

```cue
bundle: {
	apiVersion: "v1alpha1"
	name:       "shop"
	instances: [string]: {
		module: {url: "oci://localhost:5001/modules/app", version: "1.0.0"}
		namespace: "shop"
	}
	instances: {
		web: values: {
			port: {container: 8080, service: 80}
			readinessPath: "/ready"
			config: mount: "/etc/web"
		}
		api: values: {
			port: {container: 9090, service: 80}
			readinessPath: "/healthz"
			config: {
				mount: "/etc/api"
				data: web_url: "http://web.\(instances.web.namespace).svc:\(instances.web.values.port.service)"
			}
		}
	}
}
```

The bundle is CUE, so `web_url` follows the web instance's port, as the
[interpolation](/glossary/#interpolation)
`${components:web:ports:http:service_port}` does in the inventory. A
value can refer only to what the bundle sets. The module's default port
of 80 is not visible in the bundle, so the bundle sets `service: 80` for
both apps, as the inventory does.

Hand-written files, without the vendored schemas and the generator:

| | files | lines |
|---|---|---|
| Timoni module | 8 | 206 |
| Timoni bundle | 3 | 66 |
| Kapitan inventory and `.kapitan` | 6 | 99 |

The module is code the project owns: templates that spell out the fields
the generator writes, such as the probe thresholds and `defaultMode: 420`.
On the Kapitan side that code is the generator, 4529 lines of Python
without its tests, maintained in kadet-hub and pinned by digest. The
vendored Kubernetes schemas add 104 files and 27,431 lines of generated
CUE to the module.

## A misspelled value

`check` replaces `replicas: 3` with `replica: 3` for web in prod, on both
sides. Timoni refuses the bundle:

```text
build failed for web:
timoni.instance.objects.deploy.#config.replica: field not allowed:
    ./values.cue:9:2
```

`#Config` is a CUE definition, and a definition is closed: a field it
does not declare is an error. The position is in the values file that
Timoni assembles in memory from the module's defaults and the bundle, not
in `prod.cue`.

Kapitan compiles the same change and exits 0. The generator does not know
`replica`, ignores it and renders web with `replicas: 1`. It logs one
warning, because the PodDisruptionBudget of 2 then allows no eviction:

```text
web: pdb_min_available 2 >= 1 replicas allows no eviction, which blocks node drains
```

The warning comes from the generator's rule for the budget, not from a
check of the key. Kapitan 0.36.3 and the generator 1.14.0 accept a key they
do not know.

## Where the module comes from

Timoni publishes a module as an OCI artifact. `check` acts as the module's
author: it starts a registry on localhost:5001, pushes the module and pins
the bundle to the digest of that push with one more bundle file:

```sh
digest=$(timoni mod push timoni/app oci://localhost:5001/modules/app -v 1.0.0 -o json | jq -er .digest)
echo "bundle: instances: [string]: module: digest: \"$digest\"" >"$out/pin.cue"
timoni bundle build -f timoni/shop.cue -f timoni/prod.cue -f "$out/pin.cue"
```

The digest is not committed. `timoni mod push` annotates the artifact with
the Git commit and its time, so each commit of the example yields another
digest.

A version tag can move. `check` pushes a second build of the module as
1.0.0, one that sets `imagePullPolicy: Always`. The pinned bundle then
fails:

```text
the upstream digest sha256:… of version 1.0.0 doesn't match the specified digest sha256:…
```

Without the digest, the same bundle builds the second push, and the
Deployments pull `Always`.

On the Kapitan side, `inventory/classes/common.yml` pins the generator by
version and digest:

```yaml
source: ghcr.io/kadet-hub/kubernetes:1.14.0@sha256:787129e1eaed6b9bc868fe4c4aec58d40de6a89fc3cc08424a4cb5822b855080
```

Kapitan 0.36.3 checks neither the digest nor a signature when it fetches
dependencies. `check` does both outside Kapitan: `gh attestation verify`
shows that the kadet-hub release workflow built the artifact, `oras pull`
fetches it by digest, and Kapitan compiles without `--fetch`. Timoni
compares the digest itself. `timoni mod push --sign=cosign` signs a module
and `timoni mod pull --verify=cosign` checks the signature, while `timoni
bundle build` in 0.37.0 has no flag to verify one. The example signs
nothing.

## What the example leaves out

The images are placeholders, so nothing is deployed. `timoni bundle
apply`, which applies the instances to a cluster and keeps a record of
their objects there, is not tested, and neither is applying Kapitan's
output with kubectl, Argo CD or Flux. Timoni's runtime values, which a
bundle reads from the environment or the cluster, are not used. The
example renders Kubernetes objects only, so Kapitan's other outputs from
the same inventory, such as Terraform, are not compared.

## Running it

You need timoni, docker, curl, jq and uv, plus oras and a logged-in gh for
the generator:

```console
$ git clone https://github.com/kadet-hub/examples
$ cd examples/timoni-vs-kapitan
$ ./check
```
