---
title: "Talos homelab: node configs and apps from one Kapitan inventory"
date: 2026-11-20
topics: [kapitan, generators, security, verification]
description: "Talos machine configs and the app on the cluster from one Kapitan inventory, with an egress policy from the same networks, booted as Talos in Docker in CI."
stack:
  recipes: [blackbox-exporter]
  generators: [talos, kubernetes]
  example: talos-apps
---

A Talos cluster and the apps on it share values. The machine configs give
the nodes their addresses and Kubernetes its pod and Service networks.
Manifests that name those networks, such as a NetworkPolicy, only work
while they match. Kept in two places, one of them falls behind the day a
network changes.

This post renders both layers from one [Kapitan](/glossary/#kapitan)
[inventory](/glossary/#inventory). The [talos](/generators/talos/)
generator writes the machine configs of a control plane node and a worker.
The [recipe](/glossary/#recipe)
[blackbox-exporter](/recipes/blackbox-exporter/) and the
[kubernetes](/generators/kubernetes/) generator render the app, a
Prometheus blackbox exporter with an egress policy. The project is
[talos-apps](https://github.com/kadet-hub/examples/tree/main/talos-apps)
in kadet-hub/examples. Its `check` script runs in CI on every change and
once a week. It validates the configs, shows that one changed value
changes both layers, boots the configs as Talos containers in Docker and
tests the policy on that cluster.

The generator itself, `talosctl gen config` and config patches are the
subject of the guide
[Talos machine config from a Kapitan inventory](/guides/talos-machine-config/).

## The values both layers read

A [target](/glossary/#target) lists [classes](/glossary/#class), and
Kapitan merges their parameters before a generator renders them. The
project has two targets, `talos` and `blackbox-exporter`, and both include
the class `cluster`:

```yaml
# inventory/classes/cluster.yml
parameters:
  cluster:
    nodes_cidr: 192.0.2.0/24
    pod_cidr: 10.244.0.0/16
    service_cidr: 10.96.0.0/12
```

The pod and Service networks are Talos' defaults. 192.0.2.0/24 is a range
reserved for documentation and stands for the home network. The class
`talos.cluster` hands two of the values to Talos with
[interpolation](/glossary/#interpolation):

```yaml
cluster:
  clusterName: homelab
  controlPlane:
    endpoint: https://192.0.2.11:6443
  network:
    podSubnets: ["${cluster.pod_cidr}"]
    serviceSubnets: ["${cluster.service_cidr}"]
    cni:
      name: flannel
      flannel:
        kubeNetworkPoliciesEnabled: true
```

The class `talos.nodes` gives `cp-1` the address 192.0.2.11 and `worker-1`
the address 192.0.2.21, both in `nodes_cidr`. `kapitan compile` writes
`compiled/talos/talos/cp-1.yaml` and `worker-1.yaml`. Both carry the
networks in a `KubeNetworkConfig` document:

```yaml
apiVersion: v1alpha1
dnsDomain: cluster.local
kind: KubeNetworkConfig
podSubnets:
  - 10.244.0.0/16
serviceSubnets:
  - 10.96.0.0/12
```

## The app and its egress policy

A blackbox exporter probes the target that a request names:
`/probe?module=tcp_connect&target=192.0.2.11:6443` makes it open a TCP
connection to the Kubernetes API. That is its job for the sites it should
watch. Anyone who can reach its port can also point it at the API server,
at Talos' API on the nodes or at any pod. The target therefore adds an
egress policy to the recipe's component:

```yaml
components:
  blackbox-exporter-prometheus-blackbox-exporter:
    network_policies:
      egress:
        egress:
          - to:
              - namespaceSelector:
                  matchLabels:
                    kubernetes.io/metadata.name: kube-system
                podSelector:
                  matchLabels:
                    k8s-app: kube-dns
            ports:
              - {protocol: UDP, port: 53}
              - {protocol: TCP, port: 53}
          - to:
              - ipBlock:
                  cidr: 0.0.0.0/0
                  except:
                    - ${cluster.nodes_cidr}
                    - ${cluster.pod_cidr}
                    - ${cluster.service_cidr}
```

The exporter may ask the cluster's DNS and reach every address outside the
three networks. The target also adds the module `tcp_connect` to the
recipe's configuration, puts the exporter into a namespace with the Pod
Security level `restricted` and sets the seccomp profile that level needs.
The node network is the home network here, so the exporter cannot reach
the other machines in it either. To watch one of them, add an `ipBlock`
rule with its address.

## Talos network policy

Talos installs flannel as its CNI by default. Flannel routes pod traffic
and enforces no NetworkPolicy, so on a default Talos cluster the policy
above is accepted and has no effect. Talos 1.14 can run
[kube-network-policies](https://github.com/kubernetes-sigs/kube-network-policies),
the NetworkPolicy implementation of Kubernetes SIG Network, next to
flannel. `kubeNetworkPoliciesEnabled: true` in the cluster's flannel
section turns it on, and the generator writes it into the
`KubeFlannelCNIConfig` document of the control plane:

```yaml
apiVersion: v1alpha1
backendPort: 4789
backendType: vxlan
kind: KubeFlannelCNIConfig
kubeNetworkPoliciesEnabled: true
```

On the running cluster, Talos 1.14.5 deploys it as a second container,
`registry.k8s.io/networking/kube-network-policies:v1.1.2`, in the
DaemonSet `kube-flannel`. Cilium and Calico enforce NetworkPolicies on
their own and do not need it.

## One change, both layers

`check` compiles a copy of the inventory with another pod CIDR in
`cluster.yml` and fails unless exactly the two machine configs and the
NetworkPolicy change. Both compiles run without `--reveal`, so the files
hold ref tokens instead of secrets. The CI run printed:

```diff
--- a/compiled/blackbox-exporter/manifests/blackbox-exporter/blackbox-exporter-prometheus-blackbox-exporter-security.yml
+++ b/compiled/blackbox-exporter/manifests/blackbox-exporter/blackbox-exporter-prometheus-blackbox-exporter-security.yml
@@ -24,7 +24,7 @@
             cidr: 0.0.0.0/0
             except:
               - 192.0.2.0/24
-              - 10.244.0.0/16
+              - 10.42.0.0/16
               - 10.96.0.0/12
   podSelector:
     matchLabels:
--- a/compiled/talos/talos/cp-1.yaml
+++ b/compiled/talos/talos/cp-1.yaml
@@ -54,7 +54,7 @@
 dnsDomain: cluster.local
 kind: KubeNetworkConfig
 podSubnets:
-  - 10.244.0.0/16
+  - 10.42.0.0/16
 serviceSubnets:
   - 10.96.0.0/12
 ---
--- a/compiled/talos/talos/worker-1.yaml
+++ b/compiled/talos/talos/worker-1.yaml
@@ -49,7 +49,7 @@
 dnsDomain: cluster.local
 kind: KubeNetworkConfig
 podSubnets:
-  - 10.244.0.0/16
+  - 10.42.0.0/16
 serviceSubnets:
   - 10.96.0.0/12
 ---
```

## Secrets

The generator sets no token, CA or key. The class `talos.secrets` sets
each of them to a Kapitan [ref](/glossary/#ref), such as
`?{base64:talos/machine-ca-crt}`. On every run `check` creates a new
bundle with `talosctl gen secrets`, writes each value into its ref and
compiles with `--reveal`, which `talosctl validate` needs. The bundle
stays in a temporary directory, and `refs/` and `compiled/` are in
`.gitignore`. The base64 backend only encodes. A real repository keeps
these refs in an encrypting backend, such as gpg or Vault, and reveals
them only where the configs are applied.

## Talos in Docker

`talosctl validate --mode metal` checks a config without a machine.
Booting it shows more. Talos' documentation on
[Docker](https://docs.siderolabs.com/talos/v1.14/platform-specific-installations/local-platforms/docker)
names CI pipelines and local tests as what Talos in Docker is for, and
describes both `talosctl cluster create docker` and running the image by
hand.

`talosctl cluster create docker` 1.14.5 generates its own configs and
takes only patches to them. `check` therefore starts one container per
node itself, with the options of talosctl's docker provisioner
(`pkg/provision/providers/docker/node.go` at v1.14.5) and the compiled
config:

```sh
docker network create --subnet 192.0.2.0/24 --gateway 192.0.2.1 talosapps-talos-apps
docker run -d --name talosapps-talos-apps-cp-1 --hostname cp-1 \
  --network talosapps-talos-apps --ip 192.0.2.11 \
  --privileged --security-opt seccomp=unconfined --read-only --cpus 2 --memory 2g \
  --mount type=tmpfs,destination=/run --mount type=tmpfs,destination=/system \
  --mount type=tmpfs,destination=/tmp --mount type=volume,destination=/var \
  --mount type=volume,destination=/system/state --mount type=volume,destination=/opt \
  -e PLATFORM=container -e USERDATA="$(base64 -w0 compiled/talos/talos/cp-1.yaml)" \
  ghcr.io/siderolabs/talos:v1.14.5@sha256:2bd72b810f540a75d5b1c8c3739ada000fff9beec18c941790c34b9592f1a8ff
```

The Docker network gets the node network and gateway from the inventory,
and each container its node's address, so the endpoint
`https://192.0.2.11:6443` in the configs works unchanged. `worker-1`
starts the same way. `check` writes a talosconfig from the same secrets
bundle with `talosctl gen config --with-secrets --output-types
talosconfig`, runs `talosctl bootstrap` against cp-1 and fetches the
kubeconfig with `talosctl kubeconfig`.

Three details matter in a container:

- `talosctl validate --mode container` requires `hostDNS` with
  `forwardKubeDNSToHost`, which `talosctl gen config` also writes. The
  class `talos.cluster` sets it, and the configs pass both modes.
- The configs set no nameserver. In a container Talos takes the one from
  the container's `resolv.conf`, and a nameserver in the config would
  replace it. On hardware, add `nameservers` to `talos.cluster`.
- Flannel's bridge needs the kernel module `br_netfilter` on the Docker
  host. Without it, a pod gets no answer from a Service whose pods run on
  the same node. In a local run without the module, both CoreDNS pods ran
  on the exporter's node, and its DNS lookups through the Service
  `kube-dns` timed out. GitHub's runner image does not load it, so the job
  runs `sudo modprobe br_netfilter` first, as Talos' guide for GitHub
  Actions does.

Container mode skips the install. Talos runs an install sequence without
phases, so the install disk and the installer image are never used. It
does take `eth0`'s address and default route from the config's
`LinkConfig`, but Docker gives the container the same address, so the
boot does not show that the link config alone would bring a machine up.

## What the CI run showed

[Run 42006042988](https://github.com/kadet-hub/examples/actions/runs/42006042988)
of the examples workflow tested commit `1805dd0` of
[kadet-hub/examples#149](https://github.com/kadet-hub/examples/pull/149)
on 5 November 2026, on GitHub's `ubuntu-24.04` runner. The durations
below come from the log's timestamps or are what `check` printed, in
whole seconds.

Verifying the index, the recipe and both generators and pulling them took
18 seconds. Creating the secrets bundle, writing it to 14 refs, the
compile and `talosctl validate` of both configs in both modes took 14
more, and the two compiles for the diff 4. Pulling the Talos image took 4
seconds. Both nodes were Ready 61 seconds after the containers started.
The configs set no Kubernetes version, so Talos 1.14.5 runs its default,
1.37.1. CoreDNS was available 6 seconds later and the exporter 2 seconds
after its apply, image pulls included. The probes took 63 seconds, most of
it waiting for probes that cannot connect. The whole check took 168
seconds, the job 3 minutes and 7 seconds.

For comparison, `talosctl cluster create docker` with one worker took 150
seconds on a workstation with the Talos image already pulled, until it had
checked the cluster's health. That run used the generated configs, not the
inventory's, and was not repeated in CI.

## What check tests

Once the cluster is up, `check` reads the nodes and the Service
`kubernetes` and fails unless the node addresses lie in `nodes_cidr`, the
node pod CIDRs in `pod_cidr` and the Service's address in
`service_cidr`. It then deploys the exporter without its policy and
probes four targets through the API server's service proxy, the control
plane endpoint, the Service `kubernetes`, a CoreDNS pod's metrics port
and `https://github.com/`:

```text
probe tcp_connect 192.0.2.11:6443: probe_success 1, 2s
probe tcp_connect 10.96.0.1:443: probe_success 1, 3s
probe tcp_connect 10.244.0.2:9153: probe_success 1, 2s
probe http_2xx https://github.com/: probe_success 1, 2s
probe tcp_connect 192.0.2.11:6443: probe_success 0, 12s
probe tcp_connect 10.96.0.1:443: probe_success 0, 12s
probe tcp_connect 10.244.0.2:9153: probe_success 0, 12s
probe http_2xx https://github.com/: probe_success 1, 3s
```

`probe_success 1` means the exporter connected, `0` that it did not. The
first three targets are the API server on the node network, the same API
server behind its Service address and a pod. After the policy only
github.com answers. A result counts once two probes in a row return it.
The first probe after the apply already failed. The 12 seconds are two
probes that each wait for the module's 5-second timeout, and the pause
between them.

Last, `check` applies the NetworkPolicy from the compile with
`10.42.0.0/16` as pod CIDR, which no longer covers the cluster's pods:

```text
probe tcp_connect 10.244.0.2:9153: probe_success 1, 2s
probe tcp_connect 192.0.2.11:6443: probe_success 0, 12s
```

The CoreDNS pod answers again. This is the failure the shared class
prevents: a policy written for another pod network looks right and
leaves the pods open.

## What it leaves out

The configs are validated for metal but booted in containers, so the
install to a disk, the installer image and a physical link are not
tested. The cluster has one control plane node and no VIP. cp-1 keeps its
control plane taint, so the exporter runs on worker-1, and traffic from
the exporter to its own node's address is not tested. The policy is
tested with flannel and kube-network-policies only. The exporter is not
scraped by a Prometheus, and the cluster name and endpoint are values of
the talos classes alone, because nothing in this app reads them.
