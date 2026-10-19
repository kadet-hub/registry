---
title: Kapitan and Kubernetes glossary
layout: glossary
description: "Kapitan and Kubernetes terms on kadet-hub: inventory, class, target, interpolation, refs, kadet generators, CRDs, OCI artifact, SBOM and provenance."
# CAT-13a: the list and its DefinedTermSet JSON-LD. A url starting with docs/ points into this repository's docs.
terms:
  - id: kapitan
    name: Kapitan
    text: >-
      A configuration management tool that compiles an inventory into Kubernetes manifests, Terraform, documentation
      and other files. kadet-hub is a community catalog and is not run by the Kapitan project.
    url: https://kapitan.dev/
    label: kapitan.dev
  - id: inventory
    name: Inventory
    text: >-
      The YAML hierarchy of classes and targets that holds a project's parameters; a generator reads its settings
      from it.
    url: https://kapitan.dev/latest/pages/inventory/introduction/
    label: Inventory in the Kapitan docs
  - id: class
    name: Class
    text: >-
      A YAML file under `inventory/classes/` with parameters and a list of other classes it includes. Targets
      include classes, and Kapitan merges their parameters in the order they are listed. A recipe and the pins of
      its generators are classes.
    url: https://kapitan.dev/latest/pages/inventory/classes/
    label: Classes in the Kapitan docs
  - id: target
    name: Target
    text: >-
      A file under `inventory/targets/` that lists the classes it includes and sets its own parameters, such as a
      cluster or an environment. `kapitan compile` writes one output directory per target.
    url: https://kapitan.dev/latest/pages/inventory/targets/
    label: Targets in the Kapitan docs
  - id: interpolation
    name: Interpolation
    text: >-
      A `${...}` reference to another inventory parameter, such as `${namespace}`, which the inventory backend
      replaces with that parameter's value before compiling.
    url: https://kapitan.dev/latest/pages/inventory/parameters_interpolation/
    label: Parameter interpolation in the Kapitan docs
  - id: ref
    name: Ref
    text: >-
      A `?{backend:path}` tag, such as `?{gpg:...}`, that stands for a secret held encrypted in the repository or in
      a backend like Vault; compiled output keeps the tag unless the compile runs with `--reveal`. The consumer
      workflow compiles without `--reveal` and without backend credentials, and the gate does not let a generator
      create secrets.
    url: https://kapitan.dev/latest/references/
    label: References in the Kapitan docs
  - id: kadet
    name: kadet
    text: >-
      Kapitan's Python input type: a Python module that returns objects, which Kapitan writes as files.
    url: https://kapitan.dev/latest/pages/input_types/kadet/
    label: kadet in the Kapitan docs
  - id: generator
    name: Generator
    text: >-
      A reusable kadet module that turns a block of inventory parameters into many output files, for example every
      resource of an operator. Each listed generator ships a manifest, `kapitan-generator.yaml`, and a fixture
      project the gate compiles.
  - id: recipe
    name: Recipe
    text: >-
      An inventory class that replaces one or more Bitnami charts with kadet-hub generators. The examples CI
      deploys each recipe to a new kind cluster and checks it, and its page shows the class, the generator pins and
      what the CI asserts.
    url: /recipes/
    label: Recipes
  - id: kind
    name: Kind
    text: >-
      The type of a Kubernetes resource, such as Deployment or HTTPRoute, named by `kind` and the API group of its
      `apiVersion`. The kinds page lists every kind the latest version of each generator renders. kind, the tool
      that runs a Kubernetes cluster in containers, is a different thing.
    url: /kinds/
    label: Kubernetes kinds
  - id: crd
    name: Custom resource and CRD
    text: >-
      A custom resource is an object of a kind Kubernetes does not build in, such as a cert-manager Certificate; a
      CustomResourceDefinition (CRD) adds that kind to the API server with its schema and served versions. A
      generator can ship the CRDs of the custom resources it renders, and the gate checks those resources against
      them.
    url: https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/
    label: Custom resources in the Kubernetes docs
  - id: gate
    name: Gate
    text: >-
      The checks every version passes before review: secret, malware and code scans, Python errors, and a compile
      of the fixture project in a gVisor sandbox without network, with decoy credentials and a trace of the
      programs it starts.
    url: docs/authors.md
    label: What the gate checks
  - id: server-side-dry-run
    name: Server-side dry run
    text: >-
      A create request with `dryRun=All`, which the API server validates and admits like a real one but does not
      store. The gate sends the built-in resources of the compiled output to a pinned kube-apiserver this way, and
      the custom resources whose CRDs the generator ships, because JSON Schemas miss checks only the server runs,
      such as CEL rules.
    url: /guides/checking-custom-resources-against-crds/
    label: Validate Kubernetes custom resources against their CRDs
  - id: output-capability
    name: Output capability
    text: >-
      A risky kind of output a generator declares, such as privileged pods, host paths or Terraform provisioners.
      Undeclared ones fail the gate, and consumers decide which ones they accept.
  - id: output-diff
    name: Output diff
    text: >-
      The diff of a version's fixture output against that of the newest listed version of the same generator that
      is not yanked. The release attests it, and the generator page shows it for each version with a download, so
      an upgrade's effect on the rendered files is visible before pinning it.
  - id: krab
    name: krab
    text: >-
      An alternative Kapitan implementation. The gate also compiles each fixture with krab and records whether the
      output is the same; that is information, not a requirement.
  - id: oci-artifact
    name: OCI artifact
    text: >-
      Content stored in an OCI registry in the image manifest format without being a container image. Each
      generator version is one, at `ghcr.io/kadet-hub/<name>`, its files in one tar layer, which Kapitan's `oci` dependency type pulls
      into `output_path`.
  - id: digest
    name: Digest
    text: >-
      The sha256 of a published artifact. Pinning by digest means the inventory gets exactly the reviewed content,
      even if a tag moves.
  - id: sbom
    name: SBOM
    text: >-
      A software bill of materials, the list of what an artifact contains. The release attests an SPDX 2.3 SBOM for
      every version with each file and its SHA-256; generators have no dependencies, so it is the reviewed file
      list, and the version page offers it for download.
  - id: provenance
    name: Provenance
    text: >-
      A signed record of how an artifact was built. Every version carries SLSA provenance as a GitHub artifact
      attestation; verifying it against the certificate identity of the registry's release workflow on `main`
      shows that this workflow built the artifact.
    url: https://slsa.dev/spec/v1.0/provenance
    label: SLSA provenance
  - id: attestation
    name: Attestation
    text: >-
      A signed statement, stored by GitHub and logged in Sigstore's transparency log, that the marketplace's release
      workflow built and published an artifact with this digest. It says where the artifact came from, not that it
      is free of flaws.
    url: docs/consumers.md#verifying-by-hand
    label: Verifying by hand
  - id: index
    name: Index and index serial
    text: >-
      The attested list of every published version. Its serial grows with each change; a consumer who sets
      `index_serial` refuses any older index, so a rolled-back index cannot bring back a yanked version.
  - id: yanked
    name: Yanked
    text: >-
      A version withdrawn by its owners or the maintainers. The catalog shows the reason instead of the inventory
      entry, and the consumer workflow refuses its digest.
---
