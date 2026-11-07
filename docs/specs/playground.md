# Kapitan generator marketplace: Playground

Status: Draft
Code: `catalog/playground/`, `catalog/site/static/playground/`, `catalog/site/layouts/playground.html`, `catalog/site/content/playground.md`, `catalog/build` (PG-13), `.github/workflows/playground.yml`
Verified against: main @ a82f7e2

Related: [catalog.md](catalog.md) CAT-3, CAT-7, CAT-25, CAT-38; [marketplace.md](marketplace.md) DEC-5, DEC-7

## Problem

Someone who finds a generator or a recipe in the catalog has to install
Kapitan, write an inventory and run `kapitan compile` before seeing a single
manifest. The pages show an inventory snippet, not what it compiles to or
what changes when a class or a value changes. The playground at
`/playground/` lets a visitor edit a target, its classes and a kadet or
Jinja2 component and see the compiled YAML in the page, without installing
anything.

The site has no backend (DEC-5) and admits scripts only from its own origin
(CAT-3). Kapitan is Python with native extensions, compiles targets in a
multiprocessing pool and runs some inputs as subprocesses.

## Decisions

- DEC-40: The playground compiles in the visitor's browser with Pyodide,
  CPython compiled to WebAssembly. No server compiles anything; the
  alternatives are in the table at the end.
- DEC-41: The playground runs the gate's Kapitan and its pure-Python
  dependencies unchanged, at the versions of `sandbox/requirements.txt`, and
  Pyodide's own builds of the compiled ones. A Kapitan update moves the
  playground in the same pull request, and PG-6 checks it.
- DEC-42: Pyodide is served from the site, runs in a module Web Worker and
  is downloaded only after the visitor starts the playground. The page's CSP
  is every other page's.
- DEC-43: omegaconf is the default inventory backend and reclass can be
  selected. reclass-rs, the gate's default, is a Rust extension without a
  WebAssembly build. Recipes are written for omegaconf (DEC-3 of
  kadet-hub/recipes).
- DEC-44: The build ships precompiled bytecode for the modules the examples
  import and leaves out cryptography, requests and jsonschema. Pyodide memory
  snapshots, importing Kapitan ahead of the first compile and recompressing
  the archives were measured and not adopted (Start-up).
- DEC-46: The page shows where each parameter of a target comes from by
  replaying the backend's merge in the runtime module and comparing the
  replay with the inventory Kapitan rendered (Merge order and parameter
  sources).
- DEC-47: The Terraform example uses terraform-opentelekomcloud, the
  smallest of the four Terraform generators in the index (Examples).
- DEC-48: The page highlights the read-only output with Prism 1.30.0 and
  leaves the editor a plain textarea (Highlighting).

## Runtime

The playground runs Pyodide 314.0.7, whose Python is 3.14. Pyodide ships
WebAssembly builds of the compiled packages Kapitan needs on its compile
path: pyyaml, markupsafe, pydantic-core and regex. The pure-Python wheels
come from PyPI at the gate's versions: kapitan, kadet, kapicorp-reclass,
omegaconf, python-box, typeguard, pydantic-settings, python-dotenv, filetype
and toml. They are loaded without dependency resolution, because Kapitan's
own pins (`regex<2025`, `packaging<26`) exclude the builds Pyodide ships.
Pyodide's compiled packages are not the gate's versions; pydantic, for
example, is 2.12.5 against the gate's 2.14.1. PG-6 shows whether that reaches
the output.

Pyodide has no processes. `multiprocessing.Pool` and `Manager` fail with
`No module named '_multiprocessing'`, and Kapitan opens a pool for every
compile, as does the omegaconf backend for rendering. The runtime module
`kapitan_wasm.py` replaces both with a serial stand-in, so targets compile
one after another in the worker. GitPython and copier fail at import:
GitPython runs `git version`, copier's dependency plumbum imports `grp`, which
Pyodide removed. Kapitan imports both on its compile path but calls neither,
so the runtime serves them as empty modules. It does the same for the
clients of the refs backends (boto3, googleapiclient, azure, gnupg, hvac),
for yamllint and for the three packages DEC-44 leaves out.

Kapitan keeps the rendered inventory in module globals, so the runtime drops
the `kapitan` modules before every compile after the first. Kapitan 0.36.3
logs why a compile failed only at debug level, so an inventory error printed
nothing; the runtime lets that one debug record through.

- PG-1: The playground MUST load Kapitan and its pure-Python dependencies at
  the versions of `sandbox/requirements.txt`, each wheel checked against the
  hashes listed there, Pyodide at the version
  `catalog/playground/package-lock.json` pins, and each Pyodide package
  checked against the sha256 of that Pyodide's `pyodide-lock.json`.

  - Test: `catalog/test_catalog.py` (`Playground.test_build_takes_the_latest_listed_version_and_the_gate_hashes`); `build.py` exits on a mismatch, in the `playground` workflow and the release's catalog job
  - Since: #543

- PG-2: The playground MUST NOT change Kapitan's code. The runtime MAY
  replace `multiprocessing.Pool` and `Manager` and serve the modules in
  `STUBBED` of `kapitan_wasm.py` as empty modules, and nothing else.

  An empty module raises on first use, so PG-6 notices an example that
  reaches one.

  - Test: `.github/workflows/playground.yml` (`check`)
  - Since: #543

- PG-3: When a compile fails, the page MUST show Kapitan's error message.

  - Test: `catalog/playground/browser.mjs`, YAML error, via `Playground.test_runs_in_chrome`
  - Since: #543

## Inventory backends and limits

The visitor chooses omegaconf (DEC-43) or reclass, the Python
implementation of the syntax reclass-rs reads. Inputs are kadet and Jinja2.
The jsonnet input needs a native extension, and helm, kustomize, CUE and
external inputs and dependency fetching need a subprocess or the network, so
none of them is available.

- PG-4: The page MUST offer the omegaconf backend first and reclass second,
  and MUST name the backends, inputs and features it does not support.

  - Test: `catalog/test_catalog.py` (`Playground.test_backends_and_limits`)
  - Since: #543

## Examples

`catalog/playground/examples.json` lists the examples in the order the page
offers them. Each names the backends it is written for.

| Example | Files | Backends |
|---|---|---|
| Inventory basics | two classes, a target, a kadet component and a Jinja2 template, kept in `catalog/playground/examples/basics` | omegaconf |
| kubernetes generator | the usage target of the generator's README, with the generator's latest listed version | omegaconf, reclass |
| Terraform generator for Open Telekom Cloud | two classes and a target for a VPC with subnets, NAT and a state bucket, kept in `catalog/playground/examples/terraform`, with terraform-opentelekomcloud's latest listed version | omegaconf, reclass |
| Recipe uptime-kuma | the recipe's latest listed version with the generator its index record pins, and the target of its README | omegaconf |
| Recipe blackbox-exporter next to its Helm chart | as uptime-kuma, plus `helm template` of the chart the recipe rebuilds | omegaconf |

The uptime-kuma recipe's layer is 17,456 bytes, 1,580 of them classes and
the rest its README and licence. Its generator, kubernetes 1.14.0, ships as
17 files of 233,123 bytes, 168,839 of them Python; the generator's `schemas/`
and `tests/` serve the gate and the author's suite and are left out. A
generator that several examples use is shipped once.

The Helm side is static. The build renders the chart of the recipe's index
record (`chart.repo`, `version`, `digest`) with the helm version
`sandbox/Dockerfile` pins, with the values in the example's directory, as
the recipe proof does. The page shows it next to the live compile and says
that it was rendered when the site was built and is not affected by edits.

- PG-5: Generator and recipe files MUST come from their published artifacts,
  pulled by the digest the index lists: the latest listed version of a
  generator or recipe, and for a recipe the generators its index record pins.

  CAT-7 and CAT-38 read the same artifacts, so the playground runs the bytes
  the gate vetted.

  - Test: `catalog/test_catalog.py` (`Playground.test_build_takes_the_latest_listed_version_and_the_gate_hashes`); `build.py` checks each manifest's `artifactType`
  - Since: #543

- PG-11: The Helm side MUST be `helm template`'s output of the chart the
  recipe's index record names, rendered by the build, and the page MUST
  label it as rendered at build time and not compiled in the browser.

  - Test: `catalog/test_catalog.py` (`Playground.test_backends_and_limits`), `browser.mjs`
  - Since: #543

The four Terraform generators in the index, terraform-aws, terraform-google,
terraform-azurerm and terraform-opentelekomcloud, are pure Python, list no
binaries and import nothing besides Kapitan's kadet module and `ipaddress`,
`itertools`, `json` and `re`, so each runs in Pyodide. As the build ships
them, without `schemas/` and `tests/`, terraform-opentelekomcloud 0.1.3 is
the smallest with 5 files of 31,942 bytes, 9,702 of them Python;
terraform-google 0.1.4 has 34,303 bytes, terraform-aws 0.1.4 34,372 and
terraform-azurerm 0.1.4 39,782 (DEC-47). Its example spreads the inventory over two classes and the target,
so the merge order and parameter sources have something to show. Kapitan
writes `*.tf.json`; terraform itself does not run, because it is a native
binary that downloads the provider and needs the cloud's credentials for a
plan.

- PG-21: The playground MUST offer an example that compiles a Terraform
  generator from the index to `*.tf.json` files, under omegaconf and reclass.

  PG-6 compares it with the gate image like every other example.

  - Test: `browser.mjs` (PG-21); `.github/workflows/playground.yml` (`check`)
  - Since: #563

- PG-22: The page MUST say that terraform plan does not run in the browser.

  - Test: `catalog/test_catalog.py` (`Playground.test_backends_and_limits`), `browser.mjs` (PG-22)
  - Since: #563

## Equivalence with the gate

The examples are what a visitor sees first, so they must compile in the
browser exactly as the gate compiles them. The `playground` workflow builds
the playground from the published index, compiles every example under each of
its backends in Pyodide (`compile.mjs`, in Node, from the files the page
serves) and in the sandbox image built from `sandbox/`, and compares the two
trees. Because the examples come from the index, a new recipe or generator
version changes them without a pull request here, so the workflow also runs
daily on `main` against the index published at that time.

- PG-6: Every example MUST compile under each backend it names, in Pyodide,
  to the same files with the same bytes as in the gate's sandbox image.

  - Test: `.github/workflows/playground.yml` (`catalog/playground/check`)
  - Since: #543

- PG-14: The `playground` workflow MUST run daily against the published
  index. When a scheduled run fails, it MUST open one issue titled
  "Playground differs from the gate image" with the summary of `check` and
  a link to the run, or update the body of the open issue with that title.
  `issues: write` MUST be held only by the job that writes the issue, which
  holds `contents: read` besides.

  The issue covers a failure before the comparison too, such as an example
  that no longer compiles in Pyodide; its body then says that the
  comparison did not run. Decided with #543, formerly OQ-43.

  - Test: `catalog/test_catalog.py` (`PlaygroundReport`); `.github/workflows/playground.yml` (job `report`)
  - Since: #543

## Merge order and parameter sources

After a compile the page shows, for the target the visitor selects, the
classes in the order the backend merged them and, for each parameter, the
file that set its final value and the values it overrode. A visitor who
wonders why `app.replicas` is 3 reads the answer there instead of following
`classes:` through the files by hand.

Kapitan 0.36.3 does not record where a value came from. The omegaconf
backend (`OmegaConfInventory.load_parameters_from_file`) merges, for each
entry of a file's `classes:`, that class's own classes first and then the
class, and the target last, with `OmegaConf.unsafe_merge` and
`ListMergeMode.EXTEND_UNIQUE`: a list gains the items it does not hold yet.
A class listed twice is merged twice. Its `target.classes` is that merge
order. reclass (`Core._recurse_entity`) walks the same way but merges a class
only the first time. Its lists append every item, and a key with the prefix
`~` replaces the value instead of merging into it. Its `classes` output is
the union of the `classes:` lists in the order the files were merged, which
is not the merge order: for a target that lists `a` and `e`, where `a` lists
`b` and `e` lists `f`, reclass merges `b, a, f, e` and reports
`b, f, a, e`. Both backends resolve `${...}` after the merge.

So the runtime replays the merge (DEC-46). It walks the class files with the
backend's own class lookup, `resolve_class_file_path` for omegaconf and
reclass's storage, and merges each file's `parameters:` by the rules above.
For every leaf it keeps the files that set it, in merge order, with the raw
value each wrote. A leaf is a value that is not a non-empty mapping, so a
list is one leaf. The resolved value comes from the inventory Kapitan
rendered. Recording sources inside the backends would change Kapitan's code,
which PG-2 rules out.

What a backend starts from counts as a source: for omegaconf the target's
name metadata and the defaults of Kapitan's inventory model, for reclass its
automatic parameters `_reclass_`. Kapitan's compile sets
`kapitan.target_full_path` after the inventory rendered, and the page names
it as the source of that value. Defaults that Kapitan's inventory model adds
for keys no file set, such as `prune` in a compile entry, are not part of the
merge and are not listed.

The replay is checked on every compile. Each leaf without an interpolation
must equal the value Kapitan rendered, and each rendered leaf must be a leaf
of the replay or the result of one of its interpolations. Features the
replay does not model show up as differences: reclass's constant prefix
`=`, omegaconf's `???`, an interpolation that a later mapping merges into,
and class names that contain references.

The page also says whether the other backend would merge the same class
files in the same order. For the recipe examples it says that reclass cannot
read them: a recipe's `init.yml` lists `.uptime-kuma`, which omegaconf reads
as the file next to it and reclass as the class itself.

- PG-15: After a compile whose inventory rendered, the page MUST list the
  selected target's classes in the order the backend merged them, followed
  by the target, each with the file whose `classes:` named it.

  - Test: `catalog/playground/test_provenance.py` (`Provenance.test_class_order`), `browser.mjs` (PG-15)
  - Since: #562

- PG-16: The page MUST say whether the other backend merges the same class
  files in the same order, and when it cannot read the inventory, why.

  - Test: `test_provenance.py` (`Provenance.test_class_order`, `Provenance.test_other_backend_cannot_read`)
  - Since: #562

- PG-17: For every leaf of the target's merged parameters, the page MUST
  name the file that set its final value and list the files that set it
  before, with their raw values, in merge order.

  A list that several files merged names each of them. A value with an
  interpolation shows the raw and the resolved value.

  - Test: `test_provenance.py` (`test_override_chain`, `test_list_merge`, `test_none_replaces_a_mapping`, `test_reclass_override_prefix`, `test_interpolation`), `browser.mjs` (PG-17)
  - Since: #562

- PG-18: The page MUST filter the parameters by a path the visitor types.

  - Test: `browser.mjs` (PG-17, PG-18)
  - Since: #562

- PG-19: The runtime MUST compare the replay with the inventory Kapitan
  rendered on every compile, and the page MUST name every path where they
  differ.

  - Test: `test_provenance.py` (`Provenance.test_difference_is_reported`), `browser.mjs` (PG-19)
  - Since: #562

- PG-20: Every example MUST compile under each backend it names with no
  difference between the replay and Kapitan's inventory.

  - Test: `.github/workflows/playground.yml` (`compile.mjs`, in the build step)
  - Since: #562

## Highlighting

The compiled files and the Helm output are highlighted, the editor is not
(DEC-48). Long YAML is read in the output; the files a visitor edits are a
target, a few classes and a component. An overlay over the textarea would
have to match its wrapping, scrolling and font metrics after every
keystroke. Python and Jinja2 appear only in the editor, and no example
writes HCL: the Terraform example's output is `*.tf.json`. So the page needs
grammars for YAML, JSON and Markdown and picks one by the file name's
extension: `.yml` and `.yaml`, `.json` including `.tf.json`, and `.md`. Other
files stay plain text.

Prism's `tokenize` returns tokens, so `syntax.js` builds the spans with
`createElement` and `textContent`, and no markup string from the
highlighter reaches `innerHTML`. The spans hold the output's characters
unchanged, so selection and copy return what Kapitan wrote. The package is
pinned in `catalog/playground/package-lock.json`, whose integrity `npm ci`
checks, and `build.py` copies Prism's core, the markup grammar that Markdown
extends, the Markdown, YAML and JSON grammars and Prism's licence to
`prism/`. The five files and `syntax.js` are 19,061 bytes. Gzipped as
`build.py` counts the download the start button names, they add 7,948
bytes, 0.06 % of it (own calculation from the built files).

An output is highlighted when it is first opened, so a closed one costs
nothing. Measurement in headless Chrome 156 on a shared 24-core x86_64
host, two rounds of seven runs in each of three viewports: highlighting a
generated YAML of 2,000 lines (500 mappings with a quoted string, a
comment, a number and a boolean) took a median of 11 to 20 ms per viewport
and round, and 44 to 60 ms with Chrome's 4x CPU throttling, which reaches
the page's thread. The editor stays a textarea, so editing a large file
costs what it cost before.

The token colours are the site's `--accent`, `--ok`, `--warn` and
`--text-muted` on `pre`'s `--bg-subtle`. The lowest ratio is 5.58:1, for
`--text-muted` in the light theme.

- PG-23: The page MUST highlight the compiled files and the Helm output
  whose names end in `.yml`, `.yaml`, `.json` or `.md`, and MUST NOT change
  their text.

  - Test: `browser.mjs` (PG-23)
  - Since: #565

- PG-24: The highlighter MUST come from the npm package
  `catalog/playground/package-lock.json` pins, be served from the site with
  its licence, and load only after the visitor starts the playground.

  - Test: `browser.mjs` (PG-8, PG-9, PG-24); `build.py` exits when `node_modules` holds another version than `package.json` pins
  - Since: #565

- PG-25: Every token colour MUST reach a contrast of 4.5:1 on the output's
  background in the light and the dark theme.

  - Test: `catalog/test_catalog.py` (`Playground.test_highlight_colours_reach_aa`)
  - Since: #565

## Loading, CSP and hosting

The playground's files are part of the Pages artifact, about 20 MB under
`/playground/`. Pages serves them gzipped, so a start transfers about 13 MB;
the build writes the exact gzip total to `data/playground.json` and the page
shows it on the start button. Nothing of the runtime loads with the page.
GitHub Pages allows a soft 100 GB of transfer per month, about 7,700 starts.

On the page's thread, the CSP blocks compiling WebAssembly, because
`script-src` lacks `'wasm-unsafe-eval'`. A worker loaded from an http(s) URL
takes its CSP from its own response headers, which GitHub Pages does not
send, so the worker needs no change to the page's policy. If the site ever
delivers its CSP as a header, the worker script needs `'wasm-unsafe-eval'`.
The worker runs without a CSP, so the playground runs only its own files and
the visitor's edits.

Nothing the visitor types leaves the browser, and GitHub's access logs of
the downloads are those the privacy page already describes, so the privacy
page needs no change.

- PG-7: Pyodide and Kapitan MUST run in a module Web Worker, and the page's
  CSP MUST be the one `baseof.html` renders for every page.

  - Test: `catalog/test_catalog.py` (`Playground.test_csp_is_the_home_page_csp`, `Playground.test_no_inline_script_or_style`), `browser.mjs`
  - Since: #543

- PG-8: Every file the playground loads MUST come from the site's origin.

  - Test: `browser.mjs` (PG-8)
  - Since: #543

- PG-9: The page MUST NOT load the worker or Pyodide before the visitor
  starts the playground, and the start control MUST state the download size
  the build measured.

  - Test: `catalog/test_catalog.py` (`Playground.test_start_button_names_the_download`, `Playground.test_only_its_own_script_before_start`), `browser.mjs` (PG-9)
  - Since: #543

- PG-10: The playground MUST NOT send what the visitor edits, and MUST NOT
  load a project from the URL or another origin.

  - Test: `browser.mjs` (every request is a GET to the site's origin)
  - Since: #543

- PG-13: Without the playground's files, offline without
  `CATALOG_PLAYGROUND` or when the online build fails, the catalog MUST still
  build and the page MUST say that the playground is not part of the build.

  - Test: `catalog/test_catalog.py` (`Site.test_playground_without_its_files`)
  - Since: #543

## Start-up

Most of a cold start is CPU, not download. Every Pyodide wheel and the
standard library ship as source, Pyodide sets `sys.dont_write_bytecode`, and
so every start compiled several hundred modules to bytecode. After compiling
the examples, `compile.mjs` writes unchecked-hash `.pyc` files for every
module they imported: next to the sources in `site-packages-pyc.zip`, which
the worker unpacks, and in place of the sources in `python_stdlib.zip`. Both
come from the same Pyodide in the same build, so the bytecode cannot belong
to other sources.

- PG-12: The build MUST compile the bytecode the page loads with the Pyodide
  it serves, from the files it serves, in the same build.

  - Test: `.github/workflows/playground.yml` (`compile.mjs` writes it, `browser.mjs` runs on it)
  - Since: #543

Measurement for DEC-44, on a prototype of this page: three cold runs per
variant in headless Chrome 156 on a shared 24-core x86_64 host, files from
localhost, Chrome in a cgroup with `CPUWeight=10000`. "4x" adds
`CPUQuota=25%`, a quarter of one core for all of Chrome's processes, as a
stand-in for a phone, because Chrome's CPU throttling does not reach
workers. The values are seconds from navigation to the first compiled output,
median of three runs.

| Variant | Download, uncompressed | First output | 4x |
|---|---|---|---|
| Unchanged Pyodide and wheels | 20.1 MB | 11.0 | 51.9 |
| Precompiled bytecode | 24.3 MB | 5.0 | 28.2 |
| Kapitan imported before the first compile | 20.1 MB | 10.3 | 44.5 |
| cryptography, requests and jsonschema left out | 16.9 MB | 8.8 | 45.5 |
| Bytecode, those three left out (chosen) | 21.1 MB | 3.4 | 26.5 |
| Bytecode, Kapitan imported before | 24.3 MB | 4.5 | 29.1 |

The download column is the prototype's; the page as built downloads 20.5 MB,
about 13.0 MB gzipped, because its bytecode covers only the modules it
imports. The host ran other
jobs at a load average of 25 to 80, so single runs varied by up to a third.
Importing Kapitan ahead of the first compile moves time from the compile to
the start and does not shorten the wait. A Pyodide memory snapshot needs
Pyodide's private `_makeSnapshot` option, refuses a snapshot after
`loadPackage` ("Unexpected hiwire entry at index 6"), failed to restore one
with "offset is out of bounds", and was 21.3 MB gzipped on its own. The
wheels and the standard library are deflate archives already: gzip saves
1.9 % and 1.7 % of them, so recompressing them gains nothing on the wire.

## Verification

- AC-40 (PG-1, PG-2, PG-5, PG-6, PG-12): the `playground` workflow builds the
  playground from the published index, compiles every example under each of
  its backends in Pyodide and in the sandbox image, and `check` finds no
  difference.
- AC-41 (PG-3, PG-7 to PG-11): in the same workflow, Chrome opens the built
  page: no worker or Pyodide request before the start, the first compile and
  every example's compile succeed, the Helm example shows the chart's
  output, a YAML error shows the parser's message, and every request is a
  GET to the site's origin.
- AC-42 (PG-4, PG-9, PG-13): the catalog tests find the start control with
  the download size, the backend order, the list of what is not supported,
  and the note of a build without the playground.
- AC-43 (PG-14): with a stand-in for `gh`, `report` creates the issue when
  no open issue has its title, edits the body of the open one that has it,
  and ignores issues whose title only contains it.
- AC-44 (PG-15 to PG-20): in the `playground` workflow, `test_provenance.py`
  passes in the sandbox image, `compile.mjs` finds no difference for any
  example, and Chrome lists `common, apps.web, dev` for the basics example
  and the chain of `app.replicas` (1, 2, then 3 from the target).
- AC-45 (PG-21, PG-22): in the `playground` workflow, `check` finds the
  Terraform example identical to the gate image under both backends, and
  Chrome shows only `*.tf.json` files for it and the note that terraform
  plan does not run.
- AC-46 (PG-23 to PG-25): Chrome loads no Prism file before the start,
  shows the first output with tokens, and gets back the same text from a
  highlighted 2,000-line YAML, a JSON and a Markdown file; Prism's licence
  is served; the catalog tests find every token colour at 4.5:1 or more.

## Alternatives

| Option | Why not chosen |
|---|---|
| Server-side compile in the gate's gVisor sandbox | Anonymous execution of arbitrary Python on a host kadet-hub runs; the gate's `docker run` sets no CPU, memory or process limit today. It contradicts DEC-5 and the reasoning of DEC-7 and sends visitors' inventories to a server. It would add reclass-rs, jsonnet and helm. |
| Pyodide from jsDelivr, packages through micropip from PyPI | Breaks CAT-3, needs three more origins in the CSP, and shows visitors' IP addresses to third parties (CAT-25) |
| Pyodide on the page's thread with `'wasm-unsafe-eval'` | Changes the CSP of the page, and the page freezes while Python starts and compiles |
| All of Kapitan's dependencies installed | 45.2 MB of wheels for refs backends that cannot reach their services from a browser |
| Output rendered at build time only, no editing | Shows output, not the effect of an edit |
| Record sources inside the backends | Changes Kapitan's code (PG-2) |
| Merge class by class with the backend and compare after each step | Works for omegaconf only: reclass keeps values in its own types until it interpolates the whole merge. It also costs one merge per class on every compile |
| Take the class order from `target.classes` | For reclass it is not the merge order (Merge order and parameter sources) |
| Highlight the editor with an overlay | Wrapping, scrolling and font metrics of the textarea and the layer under it must stay identical in every browser; the edited files are short |
| highlight.js | Returns highlighted HTML as a string, which the page would have to put into `innerHTML` |

## Open questions

- OQ-40: Do Firefox and Safari run the worker under the page's meta CSP as
  Chrome does? CI runs Chrome only.
- OQ-41: How long does a cold start take on a phone? Only the CPU-quota
  stand-in above is measured.
- OQ-42: Should a start count as a GoatCounter event, to see how much of the
  Pages bandwidth the playground takes?

## Implementation inventory

| Path | Purpose |
|---|---|
| `catalog/playground/build.py` | Fetches and checks Pyodide and the wheels, copies Prism, assembles the examples, renders the Helm side, runs `compile.mjs`, writes `data/playground.json` (PG-1, PG-5, PG-11, PG-12, PG-24) |
| `catalog/playground/compile.mjs` | Compiles every example in Pyodide in Node, checks its provenance, writes the bytecode archives (PG-6, PG-12, PG-20) |
| `catalog/playground/test_provenance.py` | Unit tests of the replay against fixture inventories, run in the sandbox image (PG-15 to PG-19) |
| `catalog/playground/check` | Compiles every example in the sandbox image and compares (PG-6) |
| `catalog/playground/report` | Opens or updates the issue of a failed scheduled run (PG-14) |
| `catalog/playground/browser.mjs` | The page in Chrome (PG-3, PG-7 to PG-11, PG-15, PG-17 to PG-19, PG-21 to PG-24) |
| `catalog/playground/examples.json`, `examples/` | The examples (PG-21) |
| `catalog/playground/package.json`, `package-lock.json` | Pyodide, Prism and playwright-core pins; Renovate's npm manager moves them (PG-24) |
| `catalog/site/static/playground/` | `playground.js` (page), `worker.js`, `kapitan_wasm.py` (PG-2, PG-3, PG-15 to PG-19), `syntax.js` (PG-23) |
| `catalog/site/layouts/playground.html`, `content/playground.md` | The page (PG-4, PG-9, PG-11, PG-13, PG-15 to PG-18, PG-22) |
| `catalog/build` | Runs `build.py` online, copies `$CATALOG_PLAYGROUND` offline (PG-13) |
| `.github/workflows/playground.yml` | AC-40, AC-41, AC-44 to AC-46, PG-14 |

| Value | Setting |
|---|---|
| Pyodide | 314.0.7, Python 3.14 |
| Prism | 1.30.0: core, markup, markdown, yaml, json |
| Packages from Pyodide | pyyaml, jinja2, markupsafe, pydantic, regex, six, pyparsing, cachetools, packaging and their lock file dependencies |
| Wheels from PyPI | kapitan, kadet, python-box, typeguard, pydantic-settings, python-dotenv, kapicorp-reclass, filetype, toml, omegaconf |
| Served empty (`STUBBED`) | git, copier, boto3, googleapiclient, azure, gnupg, hvac, yamllint, cryptography, requests, jsonschema |
