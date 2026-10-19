---
title: Talos machine config for Kubernetes from a Kapitan inventory
layout: prose
description: Talos machine configs for every node from one Kapitan inventory, checked with talosctl validate in CI, compared with talosctl gen config and config patches.
---

A Talos machine config is a YAML file per node that can hold several
documents. The `v1alpha1` document is "the only mandatory document"; as of
Talos 1.14 most of its fields are deprecated but still supported, replaced
by documents such as `HostnameConfig`, `LinkConfig` and
`UnattendedInstallConfig`
([configuration overview](https://docs.siderolabs.com/talos/v1.14/reference/configuration/overview)).

Talos' own tool writes these files with `talosctl gen config` and adapts
them with config patches. This guide shows the other way: a
[Kapitan](/glossary/#kapitan) [inventory](/glossary/#inventory) that
describes the cluster once and renders one config per node with the
[talos generator](/generators/talos/). The example is
[`talos-machine-config`](https://github.com/kadet-hub/examples/tree/main/talos-machine-config)
in kadet-hub/examples. A CI job runs its `check` on every change and
weekly, and fails unless every rendered config passes
`talosctl validate --mode metal`, a value set once reaches every node, a
patch for one node changes only that node's file, and an invalid value is
rejected. It does not boot machines: validation proves that Talos accepts
the config, not that the cluster comes up.

## talosctl gen config and config patches

`talosctl gen config <cluster name> <cluster endpoint>` writes
`controlplane.yaml`, `worker.yaml` and `talosconfig`
([getting started](https://docs.siderolabs.com/talos/v1.14/getting-started/getting-started)).
There is one file per node type, not per node. `--with-secrets` takes a
bundle from `talosctl gen secrets` for the cluster's tokens and CAs
([CLI reference](https://docs.siderolabs.com/talos/v1.14/reference/cli#talosctl-gen-config)).

Everything that differs between nodes, or from the defaults, is a patch.
A strategic merge patch is a partial machine config. Talos merges it into
the config with the patch's values winning, appends list values except
for a few fields it names, and removes parts marked `$patch: delete`. It
detects JSON patches and strategic merge patches by their format. Patches
apply in several places
([configuration patches](https://docs.siderolabs.com/talos/v1.14/configure-your-talos-cluster/system-configuration/patching)):

- at generation: `--config-patch` for all nodes, `--config-patch-control-plane`
  and `--config-patch-worker` per type, in the order given;
- to a generated file: `talosctl machineconfig patch worker.yaml --patch patch.yaml -o worker1.yaml`;
- when applying: `talosctl apply-config --config-patch`;
- on a running node: `talosctl patch mc --nodes <ip> --patch patch.yaml`.

This needs nothing but `talosctl`, and it is the path the Talos
documentation describes. A node's final config exists only once its
patches are applied; `talosctl machineconfig patch` writes it out when
someone needs to read it.

## The same cluster as a Kapitan inventory

The example cluster has one control plane node and two workers on a static
network. Its inventory splits the config into
[classes](/glossary/#class) that one [target](/glossary/#target), `lab`,
combines:

| Class | Holds |
|---|---|
| `generators` | the talos generator, pinned by version and [digest](/glossary/#digest), and the compile entry |
| `talos.secrets` | tokens, CAs and keys as Kapitan [refs](/glossary/#ref) |
| `talos.cluster` | what every node shares: cluster name, endpoint, network, DNS, NTP, install disk |
| `talos.nodes` | one entry per node: role, hostname, address |
| `talos.patches.worker-1-nvme` | one change for one node |

The talos generator, a [kadet](/glossary/#kadet)
[generator](/glossary/#generator), reads
`parameters.generators.talos`: a `base` merged under every node and one
entry per node under `nodes`. The shared class sets `base`:

```yaml
parameters:
  generators:
    talos:
      base:
        machine:
          install:
            disk: /dev/sda
          network:
            nameservers: [192.0.2.53]
            interfaces:
              eth0:
                dhcp: false
                routes:
                  0.0.0.0/0:
                    gateway: 192.0.2.1
          time:
            servers: [time.example.com]
        cluster:
          clusterName: lab
          controlPlane:
            endpoint: https://192.0.2.11:6443
```

and the node class sets what differs per node, with the generator's
`hostname` and `ip` shorthands:

```yaml
parameters:
  generators:
    talos:
      nodes:
        cp-1:
          type: controlplane
          hostname: cp-1
          ip: 192.0.2.11/24
        worker-1:
          type: worker
          hostname: worker-1
          ip: 192.0.2.21/24
        worker-2:
          type: worker
          hostname: worker-2
          ip: 192.0.2.22/24
```

`kapitan compile` writes `compiled/lab/talos/cp-1.yaml`, `worker-1.yaml`
and `worker-2.yaml`, each a complete config for `talosctl apply-config
--file`. The keys stay in the `v1alpha1` shape; the generator writes the
`v1alpha1` document reduced to the fields Talos 1.14 has not deprecated,
followed by the documents that replace the rest, the way
`talosctl gen config` does
([generator README](https://github.com/kadet-hub/generators/blob/main/talos/README.md)).
Worker configs leave out the control plane documents and never carry the
CA private keys.

## Network settings

The interface in `base` and each node's `ip` end up in one `LinkConfig`,
the nameservers in a `ResolverConfig`. From `worker-1.yaml`:

```yaml
apiVersion: v1alpha1
kind: ResolverConfig
nameservers:
  - address: 192.0.2.53
---
addresses:
  - address: 192.0.2.21/24
apiVersion: v1alpha1
kind: LinkConfig
name: eth0
routes:
  - gateway: 192.0.2.1
```

`ip` fills the addresses of the only interface and fails the compile when
there are none or several. A route to `0.0.0.0/0` becomes a route without
destination, which `LinkConfig` treats as the default route. Once a link
document exists, Talos stops running DHCP on the other physical links, so
list every link the node should configure. VLANs, bonds, bridges and VIPs
map to their own documents; the README has the full table.

The check reads the nameserver and NTP server from `talos.cluster` and
fails unless each node config's `ResolverConfig` and `TimeSyncConfig`
carry exactly those values. Changing the nameserver is one line in one
file.

## A patch for one node

The counterpart of a per-node config patch is a class that sets keys of
one node only:

```yaml
# inventory/classes/talos/patches/worker-1-nvme.yml
parameters:
  generators:
    talos:
      nodes:
        worker-1:
          machine:
            install:
              disk: /dev/nvme0n1
```

The check compiles the inventory a second time without this class and
compares the output. Only `worker-1.yaml` changes, in one line of its
`UnattendedInstallConfig`:

```diff
<     match: disk.dev_path == "/dev/sda"
---
>     match: disk.dev_path == "/dev/nvme0n1"
```

Where a Talos patch is merged when the config is generated or applied,
the class is merged when Kapitan compiles, and the result is a file per
node. If `compiled/` is committed with refs unrevealed, a pull request
that changes a class shows the change in every affected node's file next
to it. The merge rules differ from a strategic
merge patch: the generator applies its defaults, then `base`, then the
node's `machine` and `cluster`, then the shorthands; `base` and node merge
recursively, and lists replace instead of appending. For `interfaces`,
`routes`, `vlans` and other keyed lists the generator accepts a map keyed
by the item's natural key, which merges per key. The generator also passes
`patches.<name>` through as files, for patches you still want to hand to
`talosctl`.

## Secrets

The generator sets no tokens, CAs or keys. The example keeps them as refs
in `talos.secrets`:

```yaml
machine:
  token: ?{base64:talos/machine-token}
  ca:
    crt: ?{base64:talos/machine-ca-crt}
    key: ?{base64:talos/machine-ca-key}
```

`check` creates a new bundle with `talosctl gen secrets` on every run and
writes each value into its ref with `kapitan refs --write`. Two encodings
apply: `cluster.ca`, `aggregatorCA` and `serviceAccount` are PEM in the
Talos 1.14 documents, and the generator cannot decode a ref, so those refs
hold PEM text; `machine.ca` and `cluster.etcd.ca` stay base64 as in the
bundle. The base64 backend encrypts nothing and only keeps the example
self-contained; a real repository uses `gpg`, Vault or a cloud KMS
backend. Kapitan writes refs unrevealed unless `kapitan compile` runs with
`--reveal`, which `check` does because `talosctl validate` rejects
placeholder certificates. Revealed output contains the secrets; the
example's `.gitignore` keeps `compiled/` and `refs/` out of Git.

## Validation and the schema

`talosctl validate --config <file> --mode metal` checks a config for a
platform: `metal`, `cloud` or `container`; `--strict` turns warnings into
errors. The check runs it on every node config with the `talosctl`
version pinned in the examples workflow.

Kapitan knows nothing about Talos. The check sets the control plane
endpoint to `192.0.2.11:6443`, without `https://`. Kapitan compiles it,
and validation fails:

```text
error decoding document v1alpha1/KubeClusterConfig/ (line 53): error decoding KubeClusterConfig to *k8s.KubeClusterConfigV1Alpha1: yaml: construct errors: line 55: parse "192.0.2.11:6443": first path segment in URL cannot contain colon
```

Talos publishes the JSON schema of its config documents as
[`config.schema.json`](https://github.com/siderolabs/talos/blob/v1.14.3/pkg/machinery/config/schemas/config.schema.json).
The talos generator ships it split per kind, and kadet-hub's
[gate](/glossary/#gate) validates the documents the generator renders from
its test fixtures against it before a version is listed. The `v1alpha1`
document has no `apiVersion` and `kind`, so the per-kind check skips it,
and `talosctl validate` stays the check that covers the whole file.

## Which one to use

`talosctl gen config` with patches needs one binary and follows the Talos
documentation step by step. It fits a cluster whose nodes differ in a
hostname and an address, and an operator who applies configs by hand.

The inventory fits when the per-node differences grow, when the configs
should be reviewed as files in Git, or when the same values already live
in a Kapitan inventory for the workloads on the cluster. It costs Kapitan
and a generator that has to follow Talos' deprecations: release 1.1.0 is
built for Talos 1.14.3. Renovate bumps the `talosctl` pin in the
examples workflow, and the check runs weekly, so a Talos release that
rejects the generator's output shows up as a failed run.
