---
title: "Open WebUI with SearXNG on Kubernetes, from Kapitan recipes"
date: 2026-11-07
topics: [kapitan, helm, verification]
description: "Open WebUI with SearXNG as its web search and Ollama on Kubernetes, from four Kapitan recipes, deployed on kind and tested through Open WebUI's API."
stack:
  recipes: [open-webui, ollama, searxng, valkey]
  generators: [kubernetes]
  example: open-webui-searxng
---

A chat assistant that runs in your own cluster and can look things up on
the web takes three services. Open WebUI is the chat interface and its API.
Ollama runs the language model. SearXNG is the search engine that Open
WebUI sends its web searches to. SearXNG passes each query on to public
search engines and merges their results, without an API key or an account
with any of them. Most of the other web search engines that Open WebUI
0.12.5 can call are hosted APIs that take a key from an account with the
provider. The public engines still see the queries, coming from the
cluster's address.

This post puts the three services together from four
[recipes](/glossary/#recipe) that kadet-hub publishes for
[Kapitan](/glossary/#kapitan). The project is
[open-webui-searxng](https://github.com/kadet-hub/examples/tree/main/open-webui-searxng)
in kadet-hub/examples. Its `check` script deploys it to a new
[kind](/glossary/#kind) cluster on every change and once a week, and fails
when a step below stops working.

## What each recipe brings

A recipe is a directory of Kapitan classes, published as a signed OCI
artifact. All four render with the [kubernetes](/generators/kubernetes/)
generator 1.14.0.

- [open-webui](/recipes/open-webui/) 1.0.0 runs Open WebUI 0.12.5, rebuilt
  from Open WebUI's Helm chart 17.5.0. It renders a StatefulSet with a 2Gi
  claim for the SQLite database and uploads, and a Service on port 80. Its
  option `recipes.open-webui.ollama` adds the ollama recipe and points
  Open WebUI at it.
- [ollama](/recipes/ollama/) 1.0.0 runs Ollama 0.33.2 on the CPU, rebuilt
  from the `ollama` chart 1.79.0 that Open WebUI's chart includes. Its API
  listens on port 11434. The models live in an `emptyDir`, so a new pod
  starts without them.
- [searxng](/recipes/searxng/) 1.0.1 runs the SearXNG image
  `2026.11.2-cccbc9e15`, rebuilt from the Docker Compose file in the
  SearXNG repository. SearXNG has no releases. The tag names the build
  date and the commit. The settings live in a ConfigMap, and the Service
  listens on port 8080. The pod is ready once `/healthz` answers.
- [valkey](/recipes/valkey/) 1.0.2 runs Valkey 9.1.2 as one instance with
  a password and an 8Gi claim. open-webui and searxng both include it.
  Open WebUI keeps its websocket state in it. SearXNG connects it for its
  limiter, the bot protection, which the recipe leaves off.

## The fetch inventory

Kapitan 0.36.3 reads the [inventory](/glossary/#inventory) before it
fetches dependencies, so a recipe cannot be fetched by the inventory that
uses it. The recipes the targets include are pinned in a separate fetch
inventory, `fetch/targets/recipes.yml`:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/recipes/open-webui:1.0.0@sha256:f44fd8d69166996694c83eeb6951e95699dc8601368d0f42259068c20a0c913c
        output_path: inventory/classes/recipes/open-webui
      - type: oci
        source: ghcr.io/kadet-hub/recipes/searxng:1.0.1@sha256:9a86a09e1d5acbea6c89d73014d42c434513dc121bce8f10319b97d636f016c9
        output_path: inventory/classes/recipes/searxng
```

Version and [digest](/glossary/#digest) come from the signed
[index](/glossary/#index), downloaded and verified as in the next
section. The digest decides what is pulled. A recipe's index record also
lists the recipes it includes:

```sh
jq -c '.recipes["open-webui"]["1.0.0"].includes[] | [.name, .version]' index.json
jq -c '.recipes["searxng"]["1.0.1"].includes[] | [.name, .version]' index.json
```

```text
["ollama","1.0.0"]
["valkey","1.0.2"]
["valkey","1.0.2"]
```

The fetch inventory does not pin ollama and valkey. The registry's
consumer workflow adds the recipes a pinned recipe includes, at the
version and digest its record lists, and `check` does the same. Every
recipe unpacks into `inventory/classes/recipes/<name>`, so two recipes
can share a project only when they include the same digest of a recipe.
Both records list valkey 1.0.2 at the same digest.

## Verify, then pull by digest

The registry's
[consumer docs](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#verifying-a-recipe-by-hand)
give the steps, and `check` runs them for the two pinned recipes and the
two they include. For open-webui:

```sh
id=https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main
gh release download --repo kadet-hub/registry --pattern 'index.json*'
gh attestation verify index.json --bundle index.json.sigstore.json --owner kadet-hub --cert-identity "$id"
d=sha256:f44fd8d69166996694c83eeb6951e95699dc8601368d0f42259068c20a0c913c
tmp=$(mktemp -d)
gh attestation verify "oci://ghcr.io/kadet-hub/recipes/open-webui@$d" --owner kadet-hub --cert-identity "$id"
oras pull -o "$tmp" "ghcr.io/kadet-hub/recipes/open-webui@$d"
mkdir -p inventory/classes/recipes/open-webui
tar -xf "$tmp/open-webui.tar" -C inventory/classes/recipes/open-webui --no-same-owner
```

The first [attestation](/glossary/#attestation) check proves that the
registry's release workflow signed the index. The second proves the same
for the recipe. `check` also requires the index to list `1.0.0` under
`open-webui` with that digest and `yanked: null`.

The recipes pin the kubernetes generator 1.14.0 by digest in their
classes. `check` verifies it against the index the same way and pulls it
into `lib/kubernetes`. Kapitan then compiles without `--fetch`, which
checks neither digests nor attestations.

## Two targets

Each recipe gets a [target](/glossary/#target) and a namespace of its own,
as each recipe is used and tested on its own. Each target also runs the
Valkey of its recipe, so the stack has two Valkey instances.
`inventory/targets/searxng.yml`:

```yaml
classes:
  - recipes.searxng
parameters:
  namespace: searxng
  kapitan:
    vars:
      target: searxng
  applications:
    searxng:
      secret_key: ?{base64:searxng/secret-key||random:str:40}
    valkey:
      # Part of a URL in the recipe, so letters and digits only.
      password: ?{base64:searxng/valkey-password||random:loweralphanum:40}
  components:
    searxng:
      config_maps:
        config:
          data:
            # The recipe's settings plus the json format, which Open WebUI
            # searches with.
            settings.yml:
              value: |
                use_default_settings: true
                server:
                  image_proxy: true
                search:
                  formats:
                    - html
                    - json
```

SearXNG's settings template enables only the `html` format. A request with
`format=json`, which is what Open WebUI sends, then gets 403. The value
replaces the recipe's whole `settings.yml`, so it repeats the two
settings the recipe has. `use_default_settings: true` keeps SearXNG's
defaults for everything the file does not set, including the list of
engines.

`inventory/targets/open-webui.yml`:

```yaml
classes:
  - recipes.open-webui
  - recipes.open-webui.ollama
parameters:
  namespace: open-webui
  kapitan:
    vars:
      target: open-webui
  applications:
    open-webui:
      secret_key: ?{base64:open-webui/secret-key||random:str:40}
    valkey:
      # Part of a URL in the recipe, so letters and digits only.
      password: ?{base64:open-webui/valkey-password||random:loweralphanum:40}
  components:
    open-webui:
      env:
        ENABLE_WEB_SEARCH: "True"
        WEB_SEARCH_ENGINE: searxng
        SEARXNG_QUERY_URL: http://searxng.searxng.svc:8080/search
```

`recipes.open-webui.ollama` puts Ollama in the same namespace and sets
Open WebUI's Ollama URL to `http://ollama:11434`. On the Open WebUI
side, the three variables under `env` are the whole wiring.
`ENABLE_WEB_SEARCH` turns web search on, and `WEB_SEARCH_ENGINE` picks
SearXNG. `SEARXNG_QUERY_URL` names the Service `searxng` in the
namespace `searxng`. The form `<service>.<namespace>.svc` resolves from
any namespace and does not depend on the cluster domain. Open WebUI adds
`q`, `format=json` and its other parameters to the URL itself.

Open WebUI copies these settings into its database on its first start.
Later starts keep the database's values, so a changed value in the target
reaches a running instance only through the admin settings.

Both targets set two secrets. The open-webui secret key signs Open
WebUI's logins, and SearXNG's signs the URLs of its image proxy. Each
Valkey password protects the Valkey of its target. All four are
[refs](/glossary/#ref).
`?{base64:searxng/secret-key||random:str:40}` makes the first compile
create a random value of 40 characters and store it under
`refs/searxng/secret-key`. The base64 backend only encodes, so use one
that encrypts, such as gpg or Vault, for an install that matters.
`random:str` also yields `-` and `_`. The open-webui recipe puts the
Valkey password into a Redis URL and asks for letters and digits only.
Both Valkey passwords therefore use `random:loweralphanum`.

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
the Secrets. A first compile with `--reveal` stops with `does not exist
and must be created from function`.

```sh
for ns in searxng open-webui; do
  kubectl create namespace "$ns"
  kubectl label namespace "$ns" pod-security.kubernetes.io/enforce=baseline
  kubectl apply -R -f "compiled/$ns"
done
```

SearXNG, Open WebUI and Ollama run as root in their images, which the
Pod Security level `restricted` refuses. `baseline` admits them.
open-webui 1.0.0 has no readiness probe, so `kubectl rollout status`
returns before Open WebUI listens. `check` waits for its `/health`
instead.

## Using it

```sh
kubectl -n open-webui exec deploy/ollama -- ollama pull <model>
kubectl -n open-webui port-forward service/open-webui 8080:80
```

Then open `http://localhost:8080`. The first account that signs up
becomes admin, and Open WebUI then turns signup off. Whoever reaches the
Service first owns the instance, so sign up before anyone else can reach
it.

In a chat with the web search toggle on, Open WebUI 0.12.5 offers the
model a `search_web` tool, which uses the SearXNG settings above. The
model has to support tool calls. With its function calling set to
`legacy`, Open WebUI runs the search itself before the model answers.
`check` tests neither path in a chat. It calls the search endpoint and
the chat endpoint one after the other.

## What the CI run showed

[Run 42036520562](https://github.com/kadet-hub/examples/actions/runs/42036520562)
of the examples workflow tested commit `d59b8d2` of
[kadet-hub/examples#154](https://github.com/kadet-hub/examples/pull/154)
on 5 November 2026, on GitHub's `ubuntu-24.04` runner. The durations
below are what `check` printed, in whole seconds, or come from the log's
timestamps.

Verifying the index, the two pinned recipes, the two they include and
the generator, and pulling them, took 27 seconds. Installing Kapitan with
uv and the two compiles took 9 more, for 11 files in `compiled/searxng`
and 15 in `compiled/open-webui`. kind had the cluster ready 43 seconds
later. From the first `kubectl apply` until the last rollout finished
took 122 seconds, image pulls included. Open WebUI answered `/health` 16
seconds after that.

The web search for `kubernetes` took 5 seconds. It returned three
results, Open WebUI's default count: `https://kubernetes.io/`,
`https://en.wikipedia.org/wiki/Kubernetes` and a Red Hat page. Open WebUI
loaded all three pages. Asked directly right after, SearXNG returned 39
results. Brave had found 26 of them and Google CSE 20, some of them both.
DuckDuckGo had answered with a CAPTCHA.

Pulling `smollm:135m` through Open WebUI took 4 seconds, and the chat
completion less than one. The check sets `max_tokens: 32`, and the answer
stopped mid-sentence:

```text
Kubernetes is a container orchestration system that provides a flexible and scalable way to manage containerized applications. It is a part of the Linux kernel and is
```

The second sentence is wrong.

With SearXNG scaled to zero, the same search returned HTTP 400, and Open
WebUI's log showed `Cannot connect to host searxng.searxng.svc:8080`.
The results above therefore came through SearXNG.

## What it leaves out

GPU. Ollama runs on the CPU, and the ollama recipe requests no GPU. Its
README maps the chart's `ollama.gpu.enabled` to an `nvidia.com/gpu`
limit, which is not tested, because kind has no GPU.

TLS and an ingress. All Services are `ClusterIP`, and none of the recipes
renders an Ingress or an HTTPRoute. Reaching Open WebUI from outside the
cluster takes one in the target, with the TLS setup that goes with it.

Accounts beyond the first admin. The admin creates further accounts or
turns signup back on, and accounts that then sign up wait for approval.
Single sign-on goes through Open WebUI's `OAUTH_*` and `OPENID_*`
variables in `components.open-webui.env`, which this stack does not set.
Ollama's API has no authentication, so every pod that reaches its
Service can pull, delete and run models. None of the recipes renders a
NetworkPolicy that would limit which pods reach Ollama or SearXNG.

Model size. `smollm:135m` is a 92 MB model with 135 million parameters
and a context of 2048 tokens, picked to keep the check fast. The stack
sets no memory requests or limits for Ollama, so pick a model by the
memory the node has free. The ollama recipe's README shows how to
replace the `emptyDir` with a claim, so that models outlive the pod.

Search quality. SearXNG's results are those of the public engines it
asks, and an engine that refuses the cluster's address drops out of
them, as DuckDuckGo did in the CI run.
