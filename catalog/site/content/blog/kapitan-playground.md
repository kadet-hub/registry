---
title: "Try Kapitan in your browser"
date: 2026-11-24
topics: [kapitan, generators, terraform]
tools: [Pyodide, Terraform]
description: "The kadet-hub playground runs Kapitan 0.36.3 in the browser with Pyodide: edit a target, compile Kubernetes or Terraform output, see where values come from."
---

Seeing what [Kapitan](/glossary/#kapitan) does usually starts with
installing Python and Kapitan and writing an
[inventory](/glossary/#inventory). The [playground](/playground/) skips
that. It runs Kapitan 0.36.3 in a browser tab with Pyodide, CPython
compiled to WebAssembly. You edit a [target](/glossary/#target), its
[classes](/glossary/#class) or a [kadet](/glossary/#kadet) component, and
the page shows the files Kapitan compiles.

Nothing loads until you press "Start the playground". The page names the
download next to the button, about 13 MB from kadet-hub.org. It holds
Pyodide 314.0.7 and Kapitan 0.36.3, the version kadet-hub's
[gate](/glossary/#gate) compiles with.

## Five minutes in the playground

1. Open [kadet-hub.org/playground/](/playground/) and press "Start the
   playground". The example "Inventory basics" compiles first: two classes,
   a target, a kadet component and a Jinja2 template.
2. Open `inventory/targets/dev.yml`, change `replicas: 3` to `replicas: 5`
   and press Ctrl+Enter. The compiled `dev/docs/README.md` now reads
   "Image nginx:1.27, 5 replicas."
3. Type `app.replicas` into "Why is this value set?" and open the entry.
   It lists every file that set the value, in merge order: `common` set 1,
   `apps.web` set 2, and the target set the final value.
4. Choose the example "kubernetes generator", switch the inventory backend
   to reclass and compile again. The target compiles to the same four
   files as under omegaconf: a ConfigMap, a Deployment, a Service, and one
   file with the autoscaler and the disruption budget.
5. Break the YAML on purpose, for example by changing `replicas: 5` to
   `replicas: [5`. The page shows Kapitan's own error with file, line and
   column.

## The examples

The page offers five examples. Each one says which backends it is tested
with.

| Example | What it compiles | Backends |
|---|---|---|
| Inventory basics | Two classes merge into a target, and a kadet component and a Jinja2 template read the result | omegaconf |
| kubernetes generator | The usage example of the [kubernetes](/generators/kubernetes/) generator's README | omegaconf, reclass |
| Terraform generator for Open Telekom Cloud | Terraform JSON for a VPC with two subnets, NAT egress and an encrypted state bucket, from the [terraform-opentelekomcloud](/generators/terraform-opentelekomcloud/) generator | omegaconf, reclass |
| Recipe uptime-kuma | The [uptime-kuma](/recipes/uptime-kuma/) [recipe](/glossary/#recipe) and the target of its README | omegaconf |
| Recipe blackbox-exporter next to its Helm chart | The [blackbox-exporter](/recipes/blackbox-exporter/) recipe, shown next to `helm template` of the chart it rebuilds | omegaconf |

Generator and recipe files come from their published artifacts, pulled by
the digest the index lists. The recipe examples run on omegaconf only. A
recipe's `init.yml` lists `.uptime-kuma`, which omegaconf reads as the file
next to it and reclass as the class itself. The page says that reclass
cannot read these inventories and shows reclass's error.

## Where a value comes from

After each compile, the section "Where the values come from" lists the
selected target's classes in the order the backend merged them. It says
whether the other backend merges the same class files in the same order.
Below that, every parameter names the file that set its final value. Opening
a parameter shows the values it overrode, and an interpolated value shows
both its raw and its resolved form.

Kapitan 0.36.3 does not record where a value came from. The page therefore
replays the backend's merge from the class files. It compares the replay
with the inventory Kapitan rendered on every compile and names every path
where the two differ.

## The same Kapitan as the gate

Kapitan's code is unchanged. A browser has no processes, so the page
replaces `multiprocessing`'s pool, which Kapitan opens for every compile,
with one that compiles targets one after another. Kapitan imports some
modules on its compile path without calling them, such as GitPython,
copier and the clients of the refs backends. The page serves those as
empty modules.

A workflow compiles every example under each of its backends twice: in
Pyodide and in the container image the gate compiles with. It fails when
one file differs by a byte. It runs on every change to the playground and
daily against the published index, because a new generator or recipe
version changes the examples without a pull request here.

## What does not run

These parts of Kapitan are not available in the browser:

- The reclass-rs backend, the gate's default. It is a Rust extension with
  no WebAssembly build. The reclass backend in the playground reads the
  same syntax.
- The jsonnet input, which needs a native extension.
- The helm, kustomize, CUE and external inputs, which run a subprocess.
- Fetching dependencies, which needs the network.
- Refs, Kapitan's secrets backends.

The Terraform example writes `*.tf.json` files. `terraform init`, `plan`
and `apply` do not run. Terraform is a native binary that downloads the
provider, and a plan needs the cloud's credentials. In the
blackbox-exporter example, the Helm side was rendered by `helm template`
when the site was built. The page labels it that way, and your edits do
not change it.

## How long the first start takes

Most of a cold start is CPU, not download. Pyodide ships Python's standard
library and the wheels as source, so every start would compile several
hundred modules to bytecode. The site ships that bytecode instead, compiled
by the same Pyodide in the same build.

The [playground's spec](https://github.com/kadet-hub/registry/blob/main/docs/specs/playground.md#start-up)
records the measurement behind this. It was taken on a prototype of the
page in headless Chrome 156 on a shared 24-core x86_64 host, with the
files served from localhost. The values are seconds from
navigation to the first compiled output, the median of three runs. The
second column limits Chrome to a quarter of one core, as a stand-in for a
phone.

| Variant | First output | Quarter of one core |
|---|---|---|
| Unchanged Pyodide and wheels | 11.0 s | 51.9 s |
| Precompiled bytecode, cryptography, requests and jsonschema left out (chosen) | 3.4 s | 26.5 s |

A real phone has not been measured. CI tests the page in Chrome only.

## What leaves your browser

Kapitan runs in a Web Worker of the page. What you type is not sent
anywhere, and the page does not load a project from a URL or from another
origin. After the start, every request is a GET for a file from
kadet-hub.org, which a browser test in CI checks. The page view itself is
counted like every other page, as the [privacy page](/privacy/) describes.

## Next step

The [quickstart](/quickstart/) takes the uptime-kuma recipe from the
playground to a real cluster. It installs Kapitan 0.36.3 with uv, fetches
and verifies the recipe, compiles it and applies it to a kind cluster on
your machine in about five minutes.
