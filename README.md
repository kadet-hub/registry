# kadet-hub registry

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/kadet-hub/registry/badge)](https://scorecard.dev/viewer/?uri=github.com/kadet-hub/registry)

Reviewed [Kapitan](https://kapitan.dev) generators and Kubernetes app
recipes, published as attested OCI artifacts that you pin by digest.

[Try Kapitan in the playground](https://kadet-hub.org/playground/): it
compiles an inventory in your browser, with nothing to install.

## Generators and recipes

A generator is a reusable
[kadet](https://kapitan.dev/latest/pages/input_types/kadet/) module, the
Python input type of Kapitan. It reads a block of inventory parameters and
writes many files, such as every resource of an operator or Terraform JSON
for a cloud provider. Each listed version passed a gate of scans, a
sandboxed fixture compile and a maintainer's review, and is published as an
attested OCI artifact under `ghcr.io/kadet-hub/<name>`.

A recipe is a set of inventory classes that installs one application or
operator with these generators. It rebuilds the project's Helm chart,
release manifest or Docker Compose file, or is designed on its container
image when the project ships none of these. The same release workflow
publishes it under `ghcr.io/kadet-hub/recipes/<name>`, with a
[proof level](https://kadet-hub.org/glossary/#proof-level) that says how
far CI tested it.

Coming from Helm, the recipe takes the place of the chart and a Kapitan
target takes the place of `values.yaml`. The target can override any value
the recipe's classes set, not only the ones a template exposes.

| | Helm | Kapitan with kadet-hub | Guide |
|---|---|---|---|
| Environments | a base and an environment values file per app | a target per environment that includes shared classes, merged in the order listed | [Helm vs Kustomize vs Kapitan](https://kadet-hub.org/guides/same-app/) |
| A field the chart does not template | fork the chart, or patch the rendered manifests with a post-renderer or Kustomize | the mutate generator rewrites the rendered files in `compiled/`, where the patched YAML is readable in a pull request | [Patch a Helm chart without forking it](https://kadet-hub.org/guides/patch-helm-chart/) |
| Releases | `helm install`, `upgrade` and `rollback` keep a release history in the cluster | no release: Kapitan writes files that you apply with kubectl, Argo CD or Flux | [Helm vs Kustomize vs Kapitan](https://kadet-hub.org/guides/same-app/) |

## Quickstart

This compiles the
[uptime-kuma recipe](https://kadet-hub.org/recipes/uptime-kuma/) on your
machine, without a cluster. It needs [uv](https://docs.astral.sh/uv/).
Kapitan 0.36.3 needs the pins of the install command, as
[docs/consumers.md](docs/consumers.md#kapitans---fetch-is-not-enough)
explains:

```sh
uv tool install --python 3.13 --with omegaconf==2.4.0.dev4 --with oras 'kapitan[omegaconf,reclass-rs]==0.36.3'
```

The project selects the omegaconf inventory backend, and the target
includes the recipe:

```sh
mkdir -p uptime-kuma/fetch/targets uptime-kuma/inventory/targets
cd uptime-kuma
cat > .kapitan <<'EOF'
global:
  inventory-backend: omegaconf
EOF
cat > inventory/targets/uptime-kuma.yml <<'EOF'
classes:
  - recipes.uptime-kuma
parameters:
  namespace: uptime-kuma
  kapitan:
    vars:
      target: uptime-kuma
EOF
```

Save the fetch inventory from the recipe page's
[Fetching it](https://kadet-hub.org/recipes/uptime-kuma/#fetch) section as
`fetch/targets/recipes.yml`. It pins the latest version by digest, and the
same section has the `gh attestation verify` command for that digest. Then
compile:

```sh
kapitan compile --inventory-path fetch --fetch --output-path .
kapitan compile --fetch
```

The first command fetches the recipe and exits with status 1, because the
fetch target compiles nothing. The second fetches the kubernetes generator
the recipe pins and writes a StatefulSet and a Service to
`compiled/uptime-kuma/manifests/`. `--fetch` checks neither digests nor
attestations, and the generator runs with your environment and
credentials. The [consumer workflow](docs/consumers.md#workflow) verifies
what it fetches and compiles in the gVisor sandbox the gate uses. The
[quickstart on the site](https://kadet-hub.org/quickstart/) continues to a
running app on kind.

## Recipes and the catalog

Recipes include cert-manager, Keycloak, CloudNativePG, Strimzi, Immich,
Vaultwarden, Nextcloud, Home Assistant, Paperless-ngx and Open WebUI. Each
has a page under [kadet-hub.org/recipes](https://kadet-hub.org/recipes/)
with its fetch inventory and the commands that compile it. Their source is
[kadet-hub/recipes](https://github.com/kadet-hub/recipes).

- Catalog: [kadet-hub.org](https://kadet-hub.org)
- Using a generator: [docs/consumers.md](docs/consumers.md)
- Changes to the consumer workflow: [CHANGELOG.md](CHANGELOG.md)
- Adding a generator: [docs/authors.md](docs/authors.md)
- Design and requirements: [docs/specs/marketplace.md](docs/specs/marketplace.md) and the area specs it indexes
- Reporting a vulnerability or requesting removal: [SECURITY.md](SECURITY.md)
- Terms of listing: [TERMS.md](TERMS.md)

kadet-hub is a community project and is not affiliated with or endorsed by
the Kapitan project or kapicorp. Listed generators are the work of their
authors. The marketplace is offered free of charge, as is and on a
best-effort basis: use it at your own risk, and review the compiled output
before you apply it ([TERMS.md](TERMS.md#no-warranty)).

## How changes are reviewed

`neat-bot` reviews the pull requests. It is an automated reviewer, not a
person. Its review either approves the head commit or leaves one comment
per finding. A pull request merges only after `neat-bot` approved its
current head commit. The author fixes each finding or answers it in its
thread, then asks for a new review. Every push, also an update from
`main`, needs a new approval. `neat-bot` works through a queue that can
lag by hours, so a merge can wait for it. The rulesets do not enforce
this, because `neat-bot` has read access only. It is the process the
maintainer follows.

No second person reviews the maintainer's own changes or those coding
agents make for the maintainer. They merge through the maintainer's admin
bypass once `neat-bot` approved. Pull requests from anyone else also need
the maintainer's approval. Renovate merges most of its own dependency
updates once every check passed, without `neat-bot`. The rules are in
[docs/specs/gate.md](docs/specs/gate.md#review).
