---
title: "Pi-hole on Kubernetes with PowerDNS and external-dns"
date: 2026-11-11
topics: [kapitan, dns, verification]
description: "Home and office DNS on Kubernetes from three Kapitan recipes: PowerDNS holds the zone, external-dns fills it from Services, Pi-hole blocks ads. Tested on kind."
---

A home or office network needs two things from its DNS. Devices should
find the services that run in the network by name, such as
`pihole.home.example`. Ads and trackers should not resolve at all. Pi-hole
does the second part. It answers with `0.0.0.0` for every domain on its
deny list and blocklists, and forwards the rest. The names of the local
services belong in a zone that a server holds with authority. PowerDNS
Authoritative Server holds that zone here, and external-dns writes a
record into it for every Kubernetes Service that asks for a name.

This post puts the three together from three
[recipes](/glossary/#recipe) that kadet-hub publishes for
[Kapitan](/glossary/#kapitan). The project is
[pihole-powerdns](https://github.com/kadet-hub/examples/tree/main/pihole-powerdns)
in kadet-hub/examples. Its `check` script deploys it to a new
[kind](/glossary/#kind) cluster on every change and once a week, and fails
when a step below stops working. All names are under `.example`, which
RFC 2606 reserves, so none of them belongs to a real domain.

## What each recipe brings

A recipe is a directory of Kapitan classes, published as a signed OCI
artifact. All three render with the [kubernetes](/generators/kubernetes/)
generator 1.14.0.

- [pihole](/recipes/pihole/) 1.0.0 runs Pi-hole 2026.10.1, rebuilt from
  the Docker Compose example of docker-pi-hole. It renders a StatefulSet
  with a 1Gi claim for `/etc/pihole` and a Service with DNS on port 53
  over UDP and TCP and the web interface on ports 80 and 443.
- [powerdns](/recipes/powerdns/) 1.0.0 runs PowerDNS Authoritative Server
  5.1.5 with its zones in SQLite on a 1Gi claim. An init container creates
  the zone that `applications.powerdns.zone` names. The HTTP API listens
  on port 8081 and takes the key from a Secret.
- [external-dns-powerdns](/recipes/external-dns-powerdns/) 1.0.0 runs
  external-dns 0.23.0, rebuilt from the external-dns project's Helm chart
  1.23.0. It includes powerdns and writes into its zone through the API.
  It reads Services only.

## The fetch inventory

Kapitan 0.36.3 reads the [inventory](/glossary/#inventory) before it
fetches dependencies, so a recipe cannot be fetched by the inventory that
uses it. The recipes are pinned in a separate fetch inventory,
`fetch/targets/recipes.yml`:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/recipes/pihole:1.0.0@sha256:09ded1b7816cc669ecc45b539fc349c9cace2a53b1c23962561c7b3c3589746c
        output_path: inventory/classes/recipes/pihole
      - type: oci
        source: ghcr.io/kadet-hub/recipes/external-dns-powerdns:1.0.0@sha256:5e497b87ee50d7027666310355f5e12bb850c0d67f7e6a1d5ec2249843219fb3
        output_path: inventory/classes/recipes/external-dns-powerdns
      - type: oci
        source: ghcr.io/kadet-hub/recipes/powerdns:1.0.0@sha256:5330189e01e87845dd0dbaae1270929b566f1e62f0591502b07d69ed68e92fda
        output_path: inventory/classes/recipes/powerdns
```

Version and [digest](/glossary/#digest) come from the signed
[index](/glossary/#index), downloaded and verified as in the next
section. A recipe's index record also lists the recipes it includes:

```sh
jq -c '.recipes["external-dns-powerdns"]["1.0.0"].includes[] | [.name, .version]' index.json
```

```text
["powerdns","1.0.0"]
```

Every recipe unpacks into `inventory/classes/recipes/<name>`, so the
project can hold one version of powerdns. It has to be the one that
external-dns-powerdns includes. The index also lists powerdns 1.0.1,
whose readiness probe connects to the API port instead of the DNS port.
That version fits this project once an external-dns-powerdns version that
includes it is published.

## Verify, then pull by digest

The registry's
[consumer docs](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#verifying-a-recipe-by-hand)
give the steps, and `check` runs them for all three recipes. For pihole:

```sh
id=https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
gh release download --repo kadet-hub/registry --pattern 'index.json*'
gh attestation verify index.json --bundle index.json.sigstore.json --owner kadet-hub --cert-identity "$id"
d=sha256:09ded1b7816cc669ecc45b539fc349c9cace2a53b1c23962561c7b3c3589746c
tmp=$(mktemp -d)
gh attestation verify "oci://ghcr.io/kadet-hub/recipes/pihole@$d" --owner kadet-hub --cert-identity "$id"
oras pull -o "$tmp" "ghcr.io/kadet-hub/recipes/pihole@$d"
mkdir -p inventory/classes/recipes/pihole
tar -xf "$tmp/pihole.tar" -C inventory/classes/recipes/pihole --no-same-owner
```

The first [attestation](/glossary/#attestation) check proves that the
registry's release workflow signed the index. The second proves the same
for the recipe. `check` also requires the index to list `1.0.0` under
`pihole` with that digest and `yanked: null`. The recipes pin the
kubernetes generator by digest, and `check` verifies and pulls it into
`lib/kubernetes` the same way. Kapitan then compiles without `--fetch`,
which checks neither digests nor attestations.

## One zone, two targets

The zone is set once, in the class `inventory/classes/home.yml`:

```yaml
parameters:
  home:
    zone: home.example
```

The [target](/glossary/#target) `dns` renders PowerDNS and external-dns
into the namespace `dns`. `inventory/targets/dns.yml`:

```yaml
classes:
  - home
  - recipes.external-dns-powerdns
parameters:
  namespace: dns
  kapitan:
    vars:
      target: dns
  applications:
    powerdns:
      api_key: ?{base64:dns/powerdns-api-key||random:str:40}
      zone: ${home.zone}
```

`applications.powerdns.zone` names the zone that PowerDNS creates at its
first start. external-dns-powerdns uses the same value as its
`--domain-filter`, so external-dns writes only names in that zone. The
API key is a [ref](/glossary/#ref). The first compile creates a random
value of 40 characters and stores it under `refs/dns/powerdns-api-key`.
The base64 backend only encodes, so use one that encrypts, such as gpg or
Vault, for an install that matters.

The target `pihole` renders Pi-hole into the namespace `pihole`.
`inventory/targets/pihole.yml`:

```yaml
classes:
  - home
  - recipes.pihole
parameters:
  namespace: pihole
  kapitan:
    vars:
      target: pihole
  applications:
    pihole:
      password: ?{base64:pihole/password||random:str:32}
  components:
    pihole:
      env:
        # kind's cluster DNS. On a LAN this is the resolver Pi-hole forwards to.
        FTLCONF_dns_upstreams: kube-dns.kube-system.svc.cluster.local
        # The home zone goes to PowerDNS. FTL's dnsmasq resolves the name of
        # the Service once, when FTL starts.
        FTLCONF_misc_dnsmasq_lines: server=/${home.zone}/powerdns.dns.svc.cluster.local
      service:
        annotations:
          # external-dns writes this name into the zone.
          external-dns.kubernetes.io/hostname: pihole.${home.zone}
```

Pi-hole 6 accepts each setting of its `pihole.toml` as an environment
variable named `FTLCONF_<section>_<setting>`. The recipe passes
`components.pihole.env` through, so the wiring needs no change to the
recipe.

`misc.dnsmasq_lines` adds lines to the configuration of dnsmasq, the DNS
server inside FTL, Pi-hole's core. The line
`server=/home.example/powerdns.dns.svc.cluster.local` sends every query
for the zone and its subdomains to PowerDNS. Every other name goes to the
servers in `dns.upstreams`. dnsmasq accepts a host name in `server=` and
resolves it when it reads its configuration (`parse_server` in
`src/dnsmasq/option.c` of FTL v6.8). The Service `powerdns` must
therefore exist when Pi-hole starts. If the Service is deleted and
created again with a new cluster IP, Pi-hole needs a restart.

Pi-hole's own setting for this is conditional forwarding,
`dns.revServers`. It writes the same `server=` line, but each entry also
requires the network range of a reverse zone and sends the PTR queries
for that range to the same server. PowerDNS holds no reverse zone here,
so `misc.dnsmasq_lines` carries only the forward zone.

The annotation on the Service `pihole` asks external-dns for the name
`pihole.home.example`. The recipe runs external-dns with
`--publish-internal-services`, so the record holds the Service's cluster
IP. Any Service in any namespace gets a record the same way.

## Compile and deploy

The recipes are written for the omegaconf inventory backend. With
Kapitan 0.36.3 and its `omegaconf` extra installed as the consumer docs
describe:

```sh
printf 'global:\n  inventory-backend: omegaconf\n' > .kapitan
kapitan compile
kapitan compile --reveal
```

The first compile creates the refs. The second writes their values into
the Secrets. The compile renders 10 files for `dns`, two of them the
CRDs of external-dns's chart, and 3 for `pihole`.

```sh
kubectl create namespace dns
kubectl label namespace dns pod-security.kubernetes.io/enforce=restricted
kubectl apply -R -f compiled/dns
kubectl -n dns rollout status statefulset/powerdns
kubectl create namespace pihole
kubectl label namespace pihole pod-security.kubernetes.io/enforce=baseline
kubectl apply -R -f compiled/pihole
```

PowerDNS and external-dns run as users other than root and pass the Pod
Security level `restricted`. Pi-hole's image starts as root and drops to
the user `pihole` for FTL, so its namespace gets `baseline`. `dns` goes
first, so that the Service `powerdns` exists when FTL resolves its name.

## Asking Pi-hole

`check` starts a client pod from Pi-hole's image, which brings `dig` and
`curl`, and asks Pi-hole through its Service:

```sh
dig @pihole.pihole.svc.cluster.local +short pihole.home.example A
dig @pihole.pihole.svc.cluster.local +noall +comments +authority missing.home.example A
```

The first answer is the cluster IP of the Service `pihole`, read from
PowerDNS. The second is NXDOMAIN with the zone's SOA record in the
authority section. Its contact is `hostmaster.home.example`, which
PowerDNS derives from the zone name. Neither the cluster's DNS nor the
root servers answer with that record, so the NXDOMAIN came from PowerDNS
through Pi-hole.

Blocking is tested with `ads.example`. It is NXDOMAIN until it is on a
list, whatever the blocklist holds that Pi-hole downloads at its first
start. `check` logs in to Pi-hole's API with the password from the Secret
`pihole` and puts the domain on the deny list:

```sh
sid=$(jq -nc --arg p "$password" '{password: $p}' |
  curl -fsS --data @- http://pihole.pihole.svc.cluster.local/api/auth | jq -er .session.sid)
curl -fsS -H "X-FTL-SID: $sid" --data '{"domain": "ads.example"}' \
  http://pihole.pihole.svc.cluster.local/api/domains/deny/exact
```

FTL answers the API before it reloads its lists, so `check` asks again
for up to 20 seconds. Then Pi-hole answers `0.0.0.0`, the answer of its
default blocking mode, over UDP and TCP.

## What the check showed

A run of `check` on 5 November 2026, before CI ran it, used the kind
node image `kindest/node:v1.37.0`. The compile rendered 10 files for
`dns` and 3 for `pihole`. From the first `kubectl apply` until Pi-hole's
rollout finished took 66 seconds, image pulls included.

external-dns had written `pihole.home.example` into PowerDNS by the first
query, and Pi-hole answered it with the Service's cluster IP over UDP and
TCP. For `missing.home.example`, Pi-hole returned NXDOMAIN with the flag
`aa` and this authority section:

```text
home.example.		3600	IN	SOA	a.misconfigured.dns.server.invalid. hostmaster.home.example. 2026110501 10800 3600 604800 3600
```

`ads.example` was NXDOMAIN before the deny entry and `0.0.0.0` over UDP
and TCP after it.

The wiring is the one line in `misc.dnsmasq_lines`. In a second run
without it, external-dns still wrote the record into PowerDNS, but Pi-hole
returned no address for `pihole.home.example`, and `check` failed. The
cluster's DNS, Pi-hole's only upstream then, knows nothing about
`home.example`.

## What it leaves out

Clients on the LAN. The Service `pihole` is `ClusterIP`, so only pods
reach it. Devices on the network need it exposed, for example with
`components.pihole.service.type: LoadBalancer`, and their DHCP server has
to hand out its address. For a Service of that type, external-dns writes
the load balancer's address. kind has no load balancer, so none of this is
tested. Pi-hole answers every client that reaches it
(`FTLCONF_dns_listeningMode: ALL`), so expose port 53 only to the
networks it serves.

Ingress. external-dns-powerdns 1.0.0 reads Services only
(`--source=service`), and its ClusterRole grants no access to Ingresses.
An Ingress host does not become a record without a change to the recipe.

The upstream. `FTLCONF_dns_upstreams` points at the cluster's DNS, as in
the pihole recipe's test, because a CI runner may not reach public
resolvers. On a LAN it names the resolvers Pi-hole should ask, separated
by `;`.

The SOA. The powerdns recipe 1.0.0 sets no `default-soa-content`, so the
zone's SOA names `a.misconfigured.dns.server.invalid` as its primary name
server, PowerDNS's default. The NS record names `ns1.home.example`, which
has no address record. Neither matters while Pi-hole forwards the zone,
but both show up for anyone who queries the SOA.

The API. PowerDNS serves its API to every address, and every pod that
reaches the Service `powerdns` with the key can change the zone. No
recipe renders a NetworkPolicy that limits this to external-dns.

DHCP and the blocklist. Pi-hole's DHCP server needs Pi-hole on the LAN
itself, and the recipe does not set it up. The check does not test the
blocklist Pi-hole downloads, only the deny list.
