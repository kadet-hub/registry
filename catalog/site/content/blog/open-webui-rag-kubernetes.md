---
title: "RAG on Kubernetes with Open WebUI, Qdrant, LiteLLM and Ollama"
date: 2026-11-26
topics: [kapitan, helm, verification]
description: "A RAG stack on Kubernetes from four Kapitan recipes: Open WebUI answers from a document in Qdrant, embedded through LiteLLM and Ollama, tested on kind."
stack:
  recipes: [open-webui, litellm, qdrant, ollama, valkey]
  generators: [kubernetes]
  example: open-webui-rag
---

A language model answers from what it learned in training. Your own
documents are not part of that. Retrieval-augmented generation (RAG) closes
the gap at question time. The documents are split into chunks, and an
embedding model turns each chunk into a vector, a list of numbers that
places texts with similar meaning close together. A vector database stores
the vectors. For each question, the chat application embeds the question
the same way, asks the database for the nearest chunks and puts them into
the prompt.

In this stack Open WebUI is the chat application and keeps the knowledge
bases, the collections of documents a chat can draw on. Qdrant is the
vector database. LiteLLM is a proxy that serves one OpenAI-compatible API
for the chat model and the embedding model. Ollama runs both models on the
CPU, behind LiteLLM.

The stack comes from four [recipes](/glossary/#recipe) that kadet-hub
publishes for [Kapitan](/glossary/#kapitan). The project is
[open-webui-rag](https://github.com/kadet-hub/examples/tree/main/open-webui-rag)
in kadet-hub/examples. Its `check` script deploys it to a new
[kind](/glossary/#kind) cluster on every change and once a week, adds a
document and asks about it. It fails when Open WebUI no longer answers from
the document, and also when the answer holds what only the document says
while the document is out of reach.

## What each recipe brings

All recipes render with the [kubernetes](/generators/kubernetes/)
generator 1.14.0.

- [open-webui](/recipes/open-webui/) 1.0.1 runs Open WebUI 0.12.5, rebuilt
  from Open WebUI's Helm chart 17.5.0, as a StatefulSet with a 2Gi claim
  for its SQLite database and uploads. Its option
  `recipes.open-webui.openai` points Open WebUI at an OpenAI-compatible
  endpoint, here LiteLLM.
- [litellm](/recipes/litellm/) 1.0.0 runs LiteLLM 1.108.0, rebuilt from
  LiteLLM's own Helm chart. The target sets the models it serves and its
  master key. Its option `recipes.litellm.postgresql` adds a database for
  virtual keys and spend tracking, which this stack does not use.
- [qdrant](/recipes/qdrant/) 1.0.0 runs Qdrant 1.20.0 as one node with a
  10Gi claim, from Qdrant's own Helm chart. Every request needs the API key
  that the target sets. The pod passes the Pod Security level `restricted`.
- [ollama](/recipes/ollama/) 1.0.1 runs Ollama 0.33.2 on the CPU. The
  models live in an `emptyDir`, so a new pod starts without them.
- [valkey](/recipes/valkey/) 1.0.3 runs Valkey 9.1.2. open-webui includes
  it for its websocket state.

## How a question travels

Open WebUI sends every chat completion and every embedding request to
LiteLLM. LiteLLM routes the model name `chat` to `qwen2.5:0.5b` and
`embedding` to `nomic-embed-text:v1.5`, both in Ollama. Open WebUI writes
the chunks with their vectors to Qdrant and searches them there. Open WebUI's own
connection to Ollama stays off, so Open WebUI knows one URL and two model
names. Which model answers to a name is set in LiteLLM's model list.

## The fetch inventory

Kapitan 0.36.3 reads the [inventory](/glossary/#inventory) before it
fetches dependencies, so the recipes are pinned in a separate fetch
inventory, `fetch/targets/recipes.yml`:

```yaml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/recipes/ollama:1.0.1@sha256:7d1081b5c348b8c6e119af4a972b91a5543e0fad1f92d494c8a86bd0026d7db2
        output_path: inventory/classes/recipes/ollama
      - type: oci
        source: ghcr.io/kadet-hub/recipes/litellm:1.0.0@sha256:1c0b0e14f7d460b4b61be712bd342dd409a82c5cce62760bc2847da82e6a68c3
        output_path: inventory/classes/recipes/litellm
      - type: oci
        source: ghcr.io/kadet-hub/recipes/qdrant:1.0.0@sha256:48d3dadaf619d3bf4d640abbfe48a4f46fb1c0ba988b6436531583a8feb6794b
        output_path: inventory/classes/recipes/qdrant
      - type: oci
        source: ghcr.io/kadet-hub/recipes/open-webui:1.0.1@sha256:3af3e706db37531ed72ecfe3810a4d3cd726f3f5ca5ef5ac066ec51bffabebd7
        output_path: inventory/classes/recipes/open-webui
```

A recipe's record in the signed [index](/glossary/#index) lists the
recipes it includes:

```sh
jq -c '.recipes["open-webui"]["1.0.1"].includes[] | [.name, .version]' index.json
jq -c '.recipes["litellm"]["1.0.0"].includes[] | [.name, .version]' index.json
```

```text
["ollama","1.0.1"]
["valkey","1.0.3"]
["postgresql","1.1.1"]
```

The registry's consumer workflow adds these at the version and
[digest](/glossary/#digest) their record lists, and `check` does the same.
open-webui includes ollama for its own option `recipes.open-webui.ollama`,
which would run Ollama next to Open WebUI. This stack runs Ollama in a
target of its own instead, which includes the ollama recipe directly, so
the fetch inventory pins it too. Every recipe unpacks into
`inventory/classes/recipes/<name>`, so the pin has to be the digest that
open-webui lists. postgresql comes with litellm's record and is verified
and pulled, but no target includes its classes.

`check` verifies the index, each recipe and each generator the recipes pin
before it pulls them, as the
[consumer docs](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#verifying-a-recipe-by-hand)
describe it. The [Open WebUI and SearXNG post](/blog/open-webui-searxng-kubernetes/#verify-then-pull-by-digest)
walks through these steps for one recipe.

## One class, four targets

Each recipe gets a [target](/glossary/#target) and a namespace of its own.
What more than one target needs sits in one class,
`inventory/classes/rag.yml`:

```yaml
parameters:
  rag:
    ollama: http://ollama.ollama.svc:11434
    litellm: http://litellm.litellm.svc:4000/v1
    qdrant: http://qdrant.qdrant.svc:6333
    chat_model: qwen2.5:0.5b
    embedding_model: nomic-embed-text:v1.5
    master_key: ?{base64:rag/litellm-master-key||random:str:40}
    qdrant_api_key: ?{base64:rag/qdrant-api-key||random:str:40}
```

The two keys are [refs](/glossary/#ref). The first compile creates a
random value of 40 characters for each and stores it under
`refs/rag/`. LiteLLM and Open WebUI read the master key, Qdrant and Open
WebUI the API key, so each key is set once and both ends get the same
value. The base64 backend only encodes, so use one that encrypts, such as
gpg or Vault, for an install that matters.

`inventory/targets/litellm.yml`:

```yaml
classes:
  - rag
  - recipes.litellm
parameters:
  namespace: litellm
  kapitan:
    vars:
      target: litellm
  applications:
    litellm:
      master_key: ${rag.master_key}
      # The names Open WebUI asks for, routed to the models in Ollama.
      model_list:
        - model_name: chat
          litellm_params:
            model: ollama_chat/${rag.chat_model}
            api_base: ${rag.ollama}
        - model_name: embedding
          litellm_params:
            model: ollama/${rag.embedding_model}
            api_base: ${rag.ollama}
          model_info:
            mode: embedding
```

The prefix of `model` picks how LiteLLM calls Ollama. With `ollama_chat`
it sends chat completions to Ollama's `/api/chat`, which LiteLLM's
[Ollama docs](https://docs.litellm.ai/docs/providers/ollama) recommend.
Embeddings with `ollama` go to `/api/embed`
([`handler.py`](https://github.com/BerriAI/litellm/blob/v1.108.0/litellm/llms/ollama/completion/handler.py)
of LiteLLM 1.108.0). The target `qdrant` sets `applications.qdrant.api_key` to
`${rag.qdrant_api_key}`, and the target `ollama` sets nothing but its
namespace.

`inventory/targets/open-webui.yml`:

```yaml
classes:
  - rag
  - recipes.open-webui
  - recipes.open-webui.openai
parameters:
  namespace: open-webui
  kapitan:
    vars:
      target: open-webui
  applications:
    open-webui:
      secret_key: ?{base64:open-webui/secret-key||random:str:40}
      # LiteLLM, for the chat model.
      openai:
        url: ${rag.litellm}
        api_key: ${rag.master_key}
    valkey:
      # Part of a URL in the recipe, so letters and digits only.
      password: ?{base64:open-webui/valkey-password||random:loweralphanum:40}
  components:
    open-webui:
      env:
        # LiteLLM, for the embeddings. Open WebUI does not take them from
        # OPENAI_API_BASE_URL and OPENAI_API_KEY.
        RAG_EMBEDDING_ENGINE: openai
        RAG_EMBEDDING_MODEL: embedding
        RAG_OPENAI_API_BASE_URL: ${rag.litellm}
        RAG_OPENAI_API_KEY:
          secretKeyRef:
            name: open-webui
            key: openai-api-key
        VECTOR_DB: qdrant
        QDRANT_URI: ${rag.qdrant}
        QDRANT_API_KEY:
          secretKeyRef:
            name: open-webui
            key: qdrant-api-key
  generators:
    kubernetes:
      secrets:
        open-webui:
          string_data:
            qdrant-api-key:
              value: ${rag.qdrant_api_key}
```

The option `openai` sets `OPENAI_API_BASE_URL` and `OPENAI_API_KEY`, which
Open WebUI uses for the chat models. For embeddings, Open WebUI 0.12.5 reads
`RAG_OPENAI_API_BASE_URL` and `RAG_OPENAI_API_KEY`. Unset, the URL is
`https://api.openai.com/v1`, and the key is empty unless
`OPENAI_API_BASE_URL` is that same URL
([`config.py`](https://github.com/open-webui/open-webui/blob/v0.12.5/backend/open_webui/config.py)).
Without the two variables, Open WebUI would ask OpenAI's API for the
embeddings, with an empty key.
`RAG_OPENAI_API_KEY` reads the key `openai-api-key` that the option writes
into the Secret `open-webui`. The Qdrant key is a second key in that
Secret, added under `generators.kubernetes.secrets`.

With `RAG_EMBEDDING_ENGINE: openai`, Open WebUI does not load the
embedding model it otherwise runs in its own process,
`sentence-transformers/all-MiniLM-L6-v2`
([`get_ef`](https://github.com/open-webui/open-webui/blob/v0.12.5/backend/open_webui/routers/retrieval.py)).
`VECTOR_DB: qdrant` replaces Chroma, which the image otherwise runs
inside Open WebUI, with its data on the claim. Open WebUI copies these settings into
its database on its first start, and later starts keep the database's
values, so a changed value in the target reaches a running instance only
through the admin settings.

## Compile and deploy

The recipes are written for the omegaconf inventory backend. With Kapitan
0.36.3 and its `omegaconf` extra installed as the consumer docs describe:

```sh
printf 'global:\n  inventory-backend: omegaconf\n' > .kapitan
kapitan compile --parallelism 1
kapitan compile --reveal
```

The first compile creates the refs and the second writes their values
into the Secrets. The first one runs one target at a time, because three
targets read the refs of the class `rag`. Kapitan 0.36.3 compiles the
targets in parallel processes, and the first process to need a ref
creates its file. Another process that opens the file in that moment
reads it empty and stops with `'NoneType' object has no attribute
'items'`. One local run of `check` failed that way before
`--parallelism 1` was added. The second compile only reads the refs.

Qdrant meets the Pod Security level `restricted`. Ollama, LiteLLM and Open
WebUI run as root in their images, which `restricted` refuses, so their
namespaces enforce `baseline`. `check` applies the namespaces and all four
targets in one step of a [Chainsaw](https://kyverno.github.io/chainsaw/)
test, which waits until Ollama, Qdrant, LiteLLM, Valkey and Open WebUI are
ready.

## Adding a document and asking about it

Ollama starts without models. `check` pulls both:

```sh
kubectl -n ollama exec deploy/ollama -- ollama pull qwen2.5:0.5b
kubectl -n ollama exec deploy/ollama -- ollama pull nomic-embed-text:v1.5
```

The document is `tests/document.md`, a page of a made-up lab handbook
with a door code that exists nowhere else:

```markdown
# Lab handbook: cold storage

The cold storage room of the kadet-hub test lab is on the third floor,
next to the freight elevator. Its door code is 4417-KESTREL. The code
changes on the first Monday of every month.
```

`check` signs up the first account, which Open WebUI makes admin, and
adds the document through Open WebUI's API with the account's token:

```sh
file=$(curl -fsS -H "Authorization: Bearer $token" -F file=@document.md \
  "$url/api/v1/files/?process_in_background=false" | jq -r .id)
knowledge=$(curl -fsS -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
  -d '{"name": "Lab handbook", "description": "The test lab"}' \
  "$url/api/v1/knowledge/create" | jq -r .id)
curl -fsS -H "Authorization: Bearer $token" -H 'Content-Type: application/json' \
  -d "{\"file_id\": \"$file\"}" "$url/api/v1/knowledge/$knowledge/file/add"
```

`process_in_background=false` makes the upload return only after Open
WebUI has extracted and embedded the text. Adding the file to the
knowledge base embeds it again, into the knowledge base's own collection.
Open WebUI 0.12.5 keeps all knowledge bases in one Qdrant collection,
`open-webui_knowledge`, and tells them apart by the field `tenant_id`, the
knowledge base's id
([`qdrant_multitenancy.py`](https://github.com/open-webui/open-webui/blob/v0.12.5/backend/open_webui/retrieval/vector/dbs/qdrant_multitenancy.py)).
`check` reads the points of the knowledge base from Qdrant with their
vectors and sends the text of the point that holds the code to LiteLLM's
`/v1/embeddings` as the model `embedding`. The cosine similarity of the
stored vector and LiteLLM's must be above 0.999.

The question goes to Open WebUI's chat endpoint with the knowledge base
attached:

```json
{
  "model": "chat",
  "stream": false,
  "temperature": 0,
  "messages": [{"role": "user", "content": "What is the door code of the cold storage room in the kadet-hub test lab?"}],
  "files": [{"type": "collection", "id": "<knowledge base id>"}]
}
```

Open WebUI embeds the question through LiteLLM, asks Qdrant for the
nearest chunks of that knowledge base and puts them into the prompt.
`check` then asks twice more, once without `files` and once with `files`
while Qdrant is scaled to zero. Both answers must lack the code, and the
second time Open WebUI must log that the query of the knowledge base
failed.

## What the CI run showed

[Run 42373290544](https://github.com/kadet-hub/examples/actions/runs/42373290544)
of the examples workflow tested commit `3b9a8ed` of
[kadet-hub/examples#185](https://github.com/kadet-hub/examples/pull/185)
on 7 November 2026, on GitHub's `ubuntu-24.04` runner. The durations
below are what `check` printed, in whole seconds, or come from the log's
timestamps.

Verifying the index, the four pinned recipes, the two they include and
the two generators, and pulling them, took 39 seconds. Installing Kapitan
with uv and the two compiles took 9 more, for 24 files. kind had the
cluster ready 41 seconds later. The Chainsaw step took 149 seconds, image
pulls included. Ollama and Qdrant were ready after 70 seconds, LiteLLM
after 81, Valkey after 134 and Open WebUI after 149.

Pulling each model into Ollama took 4 seconds. Uploading the document,
creating the knowledge base and adding the file took 2. Qdrant held one
point for the knowledge base, with 768 dimensions. Its vector and
LiteLLM's embedding of its text had a cosine similarity of 1.

The answer with the knowledge base attached took 6 seconds:

```text
The door code of the cold storage room in the kadet-hub test lab is 4417-KESTREL.
```

Without the knowledge base, the model had no code to give:

```text
I'm sorry, but I cannot provide an answer without knowing the specific details of the "kadet-hub test lab" and the "cold storage room" you're referring to. Could you please provide more information or context about this?
```

With the knowledge base attached and Qdrant scaled to zero, Open WebUI
logged `query_collection: 1 collection(s) had failing queries:
8861b94e-db0b-4ef7-aa37-cb06d6279a22`, with the id of the knowledge base,
and the answer again lacked the code:

```text
I'm sorry, but I cannot provide an answer without knowing the specific details of the "kadet-hub test lab" and its location. Could you please provide me with more information about this lab or the specific door code you're referring to?
```

The code in the first answer therefore came from the document, through
the search in Qdrant.

## Using it

```sh
kubectl -n open-webui port-forward service/open-webui 8080:80
```

Then open `http://localhost:8080`. The first account that signs up
becomes admin, and Open WebUI then turns signup off, so sign up before
anyone else can reach the Service. Open WebUI's
[knowledge docs](https://docs.openwebui.com/features/workspace/knowledge/)
create a knowledge base under Workspace, Knowledge, and reference it in a
chat with `#`.

A model is added in two places: pulled into Ollama, and named in
LiteLLM's `model_list` in the target `litellm`.
LiteLLM reads its configuration only at start, so the recipe's README
asks for `kubectl rollout restart deployment/litellm` after a change.

## What it leaves out

GPU. Ollama runs both models on the CPU, and the recipe requests no GPU.
`qwen2.5:0.5b` is a 398 MB download with 494 million parameters,
picked to keep the check fast. Pick a larger model by the memory and CPU
the node has free. The stack sets no memory requests or limits for
Ollama.

Other documents and other file types. `check` adds one short Markdown
file, which becomes one chunk. Many documents, PDFs and scanned pages, and
the quality of the search among many chunks are not tested. Hybrid search
and reranking are off, as in Open WebUI's defaults.

Changing the embedding model. Open WebUI creates `open-webui_knowledge`
with the dimension of the first vectors it writes, 768 for
`nomic-embed-text:v1.5`
([`_create_multi_tenant_collection`](https://github.com/open-webui/open-webui/blob/v0.12.5/backend/open_webui/retrieval/vector/dbs/qdrant_multitenancy.py)).
Vectors of two models do not compare, so a new embedding model means
embedding the documents again. `check` does not test that.

Accounts and access. `check` uses the admin account only. Knowledge bases
have their own access settings in Open WebUI, which `check` does not test.
LiteLLM runs without its database, so there are no virtual keys, budgets
or spend per user. Every request carries the master key. Ollama's API has
no authentication, and no recipe renders a NetworkPolicy. Qdrant requires
its key on every request, and Open WebUI sends it over plain HTTP inside
the cluster.

TLS and an ingress. All Services are `ClusterIP`, and none of the recipes
renders an Ingress or an HTTPRoute.
