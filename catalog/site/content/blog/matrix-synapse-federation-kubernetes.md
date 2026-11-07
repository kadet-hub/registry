---
title: "Matrix Synapse federation: well-known delegation and TLS on 443"
date: 2026-11-27
topics: [kapitan, matrix, verification]
description: "Matrix Synapse federation between two homeservers from one Kapitan recipe on kind: the well-known file, TLS on port 443, and what a missing setting breaks."
stack:
  recipes: [matrix-synapse, postgresql, cnpg]
  generators: [kubernetes, cloudnative-pg]
  example: matrix-federation
---

A Matrix homeserver's server name is the domain in the IDs of its users
and room aliases, such as `example.com` in `@admin:example.com` and
`#room:example.com`. Federation lets the users of one homeserver take
part in rooms of another, so the servers have to reach each other. By
default, other servers look for a homeserver at its server name
([Synapse's federation docs](https://element-hq.github.io/synapse/v1.164/federate.html)).

This post runs two Synapse homeservers, `a.example.test` and
`b.example.test`, in one [kind](/glossary/#kind) cluster. Both come from
the [recipe](/glossary/#recipe) [matrix-synapse](/recipes/matrix-synapse/)
that kadet-hub publishes for [Kapitan](/glossary/#kapitan), with its
option `federation`. The project is
[matrix-federation](https://github.com/kadet-hub/examples/tree/main/matrix-federation)
in kadet-hub/examples. Its `check` script deploys it to a new kind
cluster on every change and once a week. It passes only when the admin
of `a.example.test` joins a room of `b.example.test` and both admins read
each other's message. It also requires a join to fail with 404 while
`b.example.test` runs without the option, and with 502 while
`a.example.test` lacks one setting that only this cluster needs.

## What a homeserver needs to federate

By default, other servers reach a homeserver at its server name on port
8448, with TLS. Delegation sends them elsewhere. A JSON file at
`https://<server_name>/.well-known/matrix/server`, served on port 443,
names the host and port for federation traffic. When
`https://<server_name>/` on port 443 already reaches Synapse, Synapse can
serve the file itself with
[`serve_server_wellknown: true`](https://element-hq.github.io/synapse/v1.164/usage/configuration/config_documentation.html#serve_server_wellknown),
and the file then sends other servers to port 443 of the server name
([Synapse's delegation docs](https://element-hq.github.io/synapse/v1.164/delegate.html)).
Asked from the pod of `a.example.test`, `b.example.test` answers:

```json
{"m.server":"b.example.test:443"}
```

The server name therefore has to resolve to an address where port 443
answers TLS with a certificate for the name, and both `/_matrix` and
`/.well-known/matrix/server` have to reach Synapse's listener behind it.
Synapse's federation client speaks TLS only. It verifies the certificate
of each server it calls, as
[`federation_verify_certificates`](https://element-hq.github.io/synapse/v1.164/usage/configuration/config_documentation.html#federation_verify_certificates)
defaults to true. It also refuses to call an address in a private range
such as `10.0.0.0/8`, which its default
[`ip_range_blacklist`](https://element-hq.github.io/synapse/v1.164/usage/configuration/config_documentation.html#ip_range_blacklist)
lists.

Two servers in one cluster meet these needs differently from a server on
the internet:

| Need | Here, in one kind cluster | A server on the internet |
|---|---|---|
| The name resolves | CoreDNS rewrites it to the Service `matrix-tls` of the server's namespace | a public DNS record |
| TLS on port 443 | nginx in the Deployment `matrix-tls`, with a certificate that `check` signs with its own CA | the ingress, with a certificate of a public CA |
| The certificate is trusted | `federation_custom_ca_list` names that CA | the CAs of the operating environment, Synapse's default |
| The address may be called | `ip_range_whitelist: [10.96.0.0/12]`, kind's Service addresses | a public address, outside `ip_range_blacklist` |

[`federation_custom_ca_list`](https://element-hq.github.io/synapse/v1.164/usage/configuration/config_documentation.html#federation_custom_ca_list)
replaces the CAs of the operating environment, so a server with it
trusts only the listed CA for federation. Synapse's docs advise it for a
private network of homeservers only.

## What each recipe brings

A recipe is a directory of Kapitan classes, published as a signed OCI
artifact.

- [matrix-synapse](/recipes/matrix-synapse/) 1.0.0 runs Synapse 1.164.2
  from element-hq's image as the StatefulSet `matrix-synapse`, with a
  claim for the signing key and the media. Synapse reads its settings
  from the YAML files of the ConfigMap `matrix-synapse` at `/config`. The
  Job `matrix-synapse-admin` registers the first admin. Federation is off
  unless the option is on. The recipe renders with the
  [kubernetes](/generators/kubernetes/) generator 1.14.0.
- [postgresql](/recipes/postgresql/) 1.1.1, which matrix-synapse
  includes, renders the CloudNativePG `Cluster` `postgresql-cluster`
  with PostgreSQL 18.6 for Synapse's database, with the
  [cloudnative-pg](/generators/cloudnative-pg/) generator 1.1.0.
- [cnpg](/recipes/cnpg/) 1.0.3 is the CloudNativePG operator 1.30.1, here
  with its CRDs, in the target `cnpg`.

## The fetch inventory

`fetch/targets/recipes.yml` pins the two recipes the targets include:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/recipes/cnpg:1.0.3@sha256:f38aafdaf2a7ff8fe9a3356e435d05d23f0e7584299f7b326d7f25f2500a2343
        output_path: inventory/classes/recipes/cnpg
      - type: oci
        source: ghcr.io/kadet-hub/recipes/matrix-synapse:1.0.0@sha256:53c575c0f9d62a0b9506c2aa98fb63f35f1f6a00362c4c6a6eb2abdf7e85d885
        output_path: inventory/classes/recipes/matrix-synapse
```

`check` adds postgresql 1.1.1 at the digest that the index record of
matrix-synapse 1.0.0 lists under `includes`. It verifies the signed
[index](/glossary/#index), the three recipes and the two generators they
pin, and pulls them all by [digest](/glossary/#digest), as the
[Open WebUI and SearXNG post](/blog/open-webui-searxng-kubernetes/#verify-then-pull-by-digest)
shows step by step.

## Two targets and one class

`inventory/targets/synapse-a.yml`:

```yaml
classes:
  - recipes.matrix-synapse
  - recipes.matrix-synapse.federation
  - federated
parameters:
  namespace: synapse-a
  kapitan:
    vars:
      target: synapse-a
  federated:
    name: a
```

The option is the class `recipes.matrix-synapse.federation`, listed after
the recipe. `synapse-b.yml` is the same with `b` in place of `a`.

The recipe keeps its federation settings in the file `federation.yaml`
of the ConfigMap. Without the option, the listener serves the client API
only, and `federation_domain_whitelist: []` denies federation with every
server, which Synapse's docs recommend for turning federation off. The
option replaces the file. In the compiled ConfigMap of `synapse-b`:

```yaml
federation.yaml: |
  listeners:
    - port: 8008
      type: http
      x_forwarded: true
      resources:
        - names:
            - client
            - federation
  serve_server_wellknown: true
```

The listener on port 8008 now serves the federation API next to the
client API, and Synapse serves the well-known file.

The class `inventory/classes/federated.yml` holds what both servers
share. `federated.name` sets the server name and the paths of the
[refs](/glossary/#ref):

```yaml
parameters:
  applications:
    matrix-synapse:
      server_name: ${federated.name}.example.test
      registration_shared_secret: ?{base64:federated/${federated.name}/registration-shared-secret||random:str:32}
      admin:
        username: admin
        password: ?{base64:federated/${federated.name}/admin-password||random:str:24}
    # One node: further instances on it would share its disk.
    postgresql:
      instances: 1
  components:
    matrix-synapse:
      config_maps:
        config:
          data:
            kind.yaml:
              value: |
                federation_custom_ca_list:
                  - /secrets/ca.crt
                ip_range_whitelist:
                  - 10.96.0.0/12
      secrets:
        credentials:
          string_data:
            ca.crt:
              value: ?{base64:federated/ca.crt}
```

`kind.yaml` is a third file in the ConfigMap, with the two settings from
the table that only a cluster with both servers needs. The CA goes into
the recipe's Secret `matrix-synapse`, which the StatefulSet mounts at
`/secrets`.

The same class adds the component `matrix-tls`, nginx from the image
`docker.io/nginxinc/nginx-unprivileged:1.31.7-alpine`, pinned by digest.
Its Service maps port 443 to the container's 8443, and its configuration
passes every request to Synapse:

```nginx
server {
  listen 8443 ssl;
  ssl_certificate /tls/tls.crt;
  ssl_certificate_key /tls/tls.key;
  location / {
    proxy_pass http://matrix-synapse:8008;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto https;
  }
}
```

The certificate and the key come from the refs `federated/a.crt` and
`federated/a.key`, or the pair of `b`. This component is what a real
deployment replaces with its ingress.

## Certificates and refs

`check` creates the CA and one certificate per server, valid for two
days, and writes them as refs:

```sh
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 2 \
  -subj '/CN=matrix-federation example CA' -addext basicConstraints=critical,CA:TRUE \
  -addext keyUsage=critical,keyCertSign,cRLSign -keyout ca.key -out ca.crt
openssl req -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -subj /CN=a.example.test \
  -addext subjectAltName=DNS:a.example.test -keyout a.key -out a.csr
openssl x509 -req -in a.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 2 \
  -copy_extensions copy -out a.crt
kapitan refs --write base64:federated/a.crt -f a.crt
```

`ec_paramgen_curve:prime256v1` is OpenSSL's name for the curve P-256.
`check` runs the same for `b` and writes `ca.crt`, `a.key`, `b.crt` and
`b.key` to refs of the same form. A repository writes these refs once,
with the backend it keeps refs in. The shared secret and the admin
passwords get random values in the first compile, and a second compile
with `--reveal` writes all refs into the Secrets.

## Compile and deploy

The recipes are written for the omegaconf inventory backend, which
`.kapitan` selects. The two compiles write 42 files for the targets
`cnpg`, `synapse-a` and `synapse-b`. Chainsaw then applies them to the
new cluster, each step waiting for what the next one needs.

First CoreDNS gets one rewrite rule per server and restarts:

```text
rewrite name exact a.example.test matrix-tls.synapse-a.svc.cluster.local answer auto
```

A pod that looks up `a.example.test` then gets the address of the
Service `matrix-tls` in `synapse-a`, as a public DNS record would give
the address of the ingress.

Then come the namespaces, at Pod Security `restricted`, and the
operator. Synapse, its PostgreSQL, the proxy and the operator all meet
that level. For each server, the CloudNativePG `Cluster` goes first,
because Synapse exits while PostgreSQL refuses connections. The rest
follows, and the step ends when the StatefulSet `matrix-synapse` and the
Deployment `matrix-tls` are ready and the Job `matrix-synapse-admin` is
complete.

To run it:

```sh
matrix-federation/check
```

It needs `gh` (logged in), `jq`, `oras`, `uv`, `kind`, `kubectl`,
`chainsaw`, `curl`, `openssl` and `docker`. With `KEEP=1`, the cluster
stays after the check.

## What the check proves

`tests/federate.sh` reaches the client API of each server through
`kubectl port-forward` to its Service `matrix-synapse` and logs in both
admins. The admin of `b.example.test` creates a public room with the
alias `#fed:b.example.test` and sends a message. The admin of
`a.example.test` then joins the room by its alias, through the client
API of `a.example.test`:

```sh
curl -H "Authorization: Bearer $token" -H 'Content-Type: application/json' --data '{}' \
  "$a/_matrix/client/v3/join/%23fed%3Ab.example.test"
```

`$a` stands for the local end of the port-forward to `a.example.test`.
The join has to return 200 with the room's ID. The admin of
`a.example.test` then has to find the message of `b.example.test` in the
room's history, and the admin of `b.example.test` the reply. Each admin
reads through the client API of their own server, so each message
crossed from one server to the other.

The CI log has no Synapse logs. In a local run of the same `check`,
Synapse on `a.example.test` logged the join like this, shortened to the
messages, with the room and event IDs cut:

```text
Fetching https://b.example.test/.well-known/matrix/server
Response from .well-known: {'m.server': 'b.example.test:443'}
{GET-O-1} [b.example.test] Completed request: 200 OK in 4.53 secs, got 87 bytes - GET matrix-federation://b.example.test/_matrix/federation/v1/query/directory?room_alias=%23fed%3Ab.example.test
{GET-O-2} [b.example.test] Completed request: 200 OK in 0.02 secs, got 428 bytes - GET matrix-federation://b.example.test/_matrix/federation/v1/make_join/...
{PUT-O-3} [b.example.test] Completed request: 200 OK in 0.08 secs, got 5089 bytes - PUT matrix-federation://b.example.test/_matrix/federation/v2/send_join/...
```

It fetched the well-known file, looked up the alias through the
federation API of `b.example.test` and joined the room with `make_join`
and `send_join`. The reply went out later as a `PUT` to
`/_matrix/federation/v1/send/`, which `b.example.test` answered with
200.

`check` compiles each of the two failing cases from a copy of the
inventory with one change, and takes only Synapse's ConfigMap from it.
`federate.sh` applies that ConfigMap and replaces the pod
`matrix-synapse-0`, because Synapse reads its configuration only when it
starts.

### Without the option on b.example.test

The copy leaves `recipes.matrix-synapse.federation` out of
`synapse-b.yml`. `check` requires that its ConfigMap lack the resource
`federation` and carry `federation_domain_whitelist: []` again. A join
of the new alias `#fed-off:b.example.test` then has to return 404.

It returns 404 with `M_NOT_FOUND`. In the local run, the listener of
`b.example.test` answered the alias lookup with
`404 - Unrecognized request`, and `a.example.test` passed the 404 on to
its client:

```text
Error retrieving alias #fed-off:b.example.test -> 404 Not Found
SynapseError: 404 - Room alias #fed-off:b.example.test not found
```

`a.example.test` still called port 443 here, because it had fetched the
well-known file of `b.example.test` for the first join. Synapse keeps a
fetched file for about 24 hours when the answer sets no cache headers,
as here
(`WELL_KNOWN_DEFAULT_CACHE_PERIOD` in
[`well_known_resolver.py`](https://github.com/element-hq/synapse/blob/v1.164.2/synapse/http/federation/well_known_resolver.py)).
The local run's log shows a single fetch of it before `a.example.test`
was restarted. Without the option, `b.example.test` no longer serves the
file. A server that has not fetched it before falls back to port 8448,
as `a.example.test` does after its restart in the next case. The Service
`matrix-tls` that the name resolves to has no port 8448, and what such a
join returns is not tested.

### Without ip_range_whitelist on a.example.test

The copy leaves the two lines of `ip_range_whitelist` out of the class
`federated`, and `check` compiles only `synapse-a` from it. `federate.sh`
first puts `b.example.test` back on its ConfigMap with the option, then
applies the copy's ConfigMap to `a.example.test` and replaces its pod. A
join of `#fed-open:b.example.test` then has to return 502.

It returns 502 with `M_UNKNOWN`. `b.example.test` resolves to the address
of the Service `matrix-tls` in `synapse-b`. That address lies in kind's
Service range `10.96.0.0/12`, inside `10.0.0.0/8` of the default
`ip_range_blacklist`. In the local run, the restarted Synapse fetched
the well-known file again, and that failed on the blocked address. For
the join it then logged:

```text
Blocked <address> from DNS resolution to b.example.test
Failed to connect to b.example.test:8448: DNS lookup failed: no results for hostname lookup: b.example.test.
SynapseError: 502 - Failed to fetch alias
```

`<address>` stands for the address of that Service. Synapse removes a
blocked address from the DNS answer, so no address was left to connect
to, and the alias lookup ended in 502.

## What the CI run showed

[Run 42362659622](https://github.com/kadet-hub/examples/actions/runs/42362659622)
of the examples workflow tested commit `3e1dd74` of main on 7 November
2026, on GitHub's `ubuntu-24.04` runner. The folder `matrix-federation`
is the one that
[kadet-hub/examples#172](https://github.com/kadet-hub/examples/pull/172)
merged. The durations below come from the log's timestamps, in whole
seconds.

Verifying the index, the three recipes and the two generators, and
pulling them, took 24 seconds. The refs and the two compiles took 15
more, and the two compiles of the copies 6. kind had the cluster ready 47
seconds after that. Chainsaw needed 122 seconds for the deploy, image
pulls included. `federate.sh` printed its first line 18 seconds later,
the second 20 seconds and the third 39 seconds after that. The second
case replaces one Synapse pod, the third two. The whole `check`, up to
its last line, took 4 minutes and 51 seconds.

```text
@admin:a.example.test joined #fed:b.example.test (!-SORyCsTcZx0_NA6PCfCVhdx5FRhT0_6H61UKg15r-E) and read 'hello from b.example.test 16733', @admin:b.example.test read 'hello from a.example.test 2533'
b.example.test without the option federation: the join got 404, M_NOT_FOUND
a.example.test without ip_range_whitelist: the join got 502, M_UNKNOWN
```

## What it leaves out

The internet. A public DNS name, a certificate of a public CA,
delegation to another host, port 8448, more than two servers and servers
outside the cluster are not tested.

Whom a server federates with. With the option, `federation_domain_whitelist`
is not set, and Synapse then federates with every server
([`federation_domain_whitelist`](https://element-hq.github.io/synapse/v1.164/usage/configuration/config_documentation.html#federation_domain_whitelist)).
A private federation lists its servers there, in a file of its own such
as `kind.yaml`.

Where the signing keys come from. Synapse needs the signing key of each
server it federates with, and
[`trusted_key_servers`](https://element-hq.github.io/synapse/v1.164/usage/configuration/config_documentation.html#trusted_key_servers)
names the servers it downloads keys from. Without the option, the recipe
sets it to `[]`. The option replaces that file, so Synapse falls back to
`matrix.org` and warns about it when it starts. In the local run,
`a.example.test` asked `matrix.org` first for the key of
`b.example.test`. That request failed with `certificate verify failed`,
because `federation_custom_ca_list` leaves only `check`'s CA. Synapse
then fetched the key from `b.example.test` itself. `check` does not test
which way a key came.

High availability. Each server runs one Synapse pod, and one PostgreSQL
instance because the cluster has one node.
