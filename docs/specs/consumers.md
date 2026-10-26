# Kapitan generator marketplace: Consumers

Status: Approved
Code: `consumer/`, `sandbox/gitlab-ci.yml`, `.github/workflows/consumer.yml`, `.github/actions/consumer/`, `tests/consumers/`, `docs/consumers.md`, `policy/consumer.schema.json` (CON-4)
Verified against: main @ 970a5d4

Related: [marketplace.md](marketplace.md) holds the problem, threat model, decisions,
acceptance criteria, residual risks, open questions and the implementation inventory.

## Consumers

Kapitan 0.36.3 verifies neither attestations nor digests on OCI fetch, and
fetches only as part of `compile`. The consumer flow therefore fetches with
native tools first and compiles offline. Compiling without `--reveal` needs no
ref backend credentials, except when a `||func` ref is created or gpg
recipients lack a fingerprint; the consumer creates missing refs in a
separate step before the sandboxed compile.

A consumer repository calls the reusable workflow
`kadet-hub/registry/.github/workflows/consumer.yml` pinned by commit SHA and
commits a policy file `.kapitan-sandbox.yaml`, defined by
`policy/consumer.schema.json`:

```yaml
index_serial: 12              # lowest accepted index serial (CON-2)
inventory_backend: omegaconf   # passed to inventory and compile; default reclass
hosts:                        # allowed dependency hosts per type
  oci: [ghcr.io]
  helm: [charts.example.org]
  git: [github.com]
  https: []
binaries: ["helm template"]   # run by the consumer's own inputs
output_capabilities:          # accepted SEC-12 capabilities per output path glob (CON-1b)
  "compiled/logging/*": [host-path]
```

The workflow runs its scripts from its own commit through the
self-repository syntax (`$/`) and the sandbox image of that commit's
`sandbox/` tree (PUB-6). Its `owner` input, default `kadet-hub`, names the
registry namespace and the certificate identity; a rehearsal fork sets its
own.

- CON-1: The reusable workflow MUST, in this order:

  1. run `kapitan inventory` in the SEC-9 sandbox with the SEC-10 trace and an
     empty environment, because the inventory backend imports
     `resolvers.py`;
  2. fail on a dependency in the inventory whose type or host the policy does
     not allow, an `http` dependency, an OCI dependency whose source is not
     `<host>/<repository>[:<tag>]@sha256:<digest>` or that sets
     `insecure`, `tls_verify: false`, `subpath` or `media_type`, a helm
     dependency without an exact `version` or with `helm_path`, a git
     dependency whose `ref` is not a full commit SHA or with `submodules`,
     two dependencies sharing an `output_path`, an inventory that is not a
     mapping of target names to targets, and a target whose
     `parameters.kapitan.dependencies` is not a list of mappings;
  3. fetch the dependencies outside the sandbox (`oras pull` by digest,
     `helm pull`, `git` at the commit) and verify marketplace artifacts and
     their charts (CON-2);
  4. compile in the SEC-9 sandbox with decoys (SEC-11) and the SEC-10 trace
     policy, extended by the policy's `binaries` and the binaries the index
     lists for the fetched generators;
  5. upload the compiled output as the workflow artifact `compiled`.

  The project is the checkout (`persist-credentials: false`) without `.git`
  and `.kapitan`, mounted read-only together with the fetched dependencies,
  which replace whatever the checkout holds at their `output_path`. Kapitan
  runs with fixed flags and without `--fetch`; the policy's
  `inventory_backend` is the only flag the consumer chooses. git
  dependencies are written with `gate/fetch_tree.py`, so its symlink and
  size limits apply. A dependency URL built
  from `oc.env` resolves against the empty environment, so it either fails
  the inventory or names a host the policy has to allow.

  The tag is optional and never selects what is fetched: `oras pull` and
  `gh attestation verify` get `<host>/<repository>@sha256:<digest>`.

  - Test: `consumer-selftest` (AC-10); `consumer/test_consumer.py`
  - Since: #15, #234, #244

- CON-1a: The marketplace MUST publish a GitLab CI template that runs the
  same steps with the published sandbox image.

  GitLab-hosted runners cannot run gVisor; the template uses `--network none`
  with the default runtime and documents that SEC-10 is not enforced there.

  `sandbox/gitlab-ci.yml` is included by URL at a commit SHA and takes the
  same SHA as input; the job downloads that commit's scripts and runs
  `consumer/run` against a `docker:dind` service with `SANDBOX_TRACE=0`.
  In that mode `sandbox/run` uses the default runtime, needs no sudo, and
  writes `/out` to a plain directory that is checked for the 50 MiB limit
  after the compile, then emptied through the sandbox image as the sandbox
  user, since a non-root caller cannot delete what that user wrote;
  `noexec` on `/out` and the SEC-10 trace are not enforced. Network
  isolation, the read-only root, decoys, SEC-11 and
  SEC-12 apply as on GitHub. Work directories live under
  `$CI_PROJECT_DIR`, which the job and the dind service share. The job
  needs a `GH_TOKEN` CI variable, a GitHub token without permissions, for
  `gh attestation verify`; without it the job fails before fetching.

  Run on 2026-10-10 in a private gitlab.com project against the rehearsal
  fork's published sandbox image: the `pass-helm-input` sample compiled
  and uploaded `compiled`, the `fail-output-capability` sample failed on
  the undeclared `hostPath` in `compiled/app` and accepted the one in
  `compiled/logging`.

  - Test: manual: gitlab.com rehearsal (2026-10-10); `gate-selftest`
    compiles `pass-plain` with `SANDBOX_TRACE=0` as a non-root user
  - Since: #31, #44

- CON-1b: The compile step MUST run SEC-12 over the output and fail on every
  match the policy's `output_capabilities` does not accept for that path.

  Globs match the path below the output directory, such as
  `compiled/<target>/...`, and `*` also matches `/`. Capabilities come from
  the SEC-12 enum. Files without a parser are listed in the report and do
  not fail: the consumer has no `unparsed_outputs`, and reviews the output
  before applying it (CON-3).

  - Test: `sandbox/test_output_check.py`; `consumer-selftest` (AC-10)
  - Since: #22

- CON-2: Verification MUST check the artifact attestation with
  `gh attestation verify oci://ghcr.io/kadet-hub/<name>@sha256:<digest>
  --owner kadet-hub --cert-identity
  https://github.com/kadet-hub/registry/.github/workflows/release.yml@refs/heads/main`,
  verify the index the same way, reject an index whose `serial` is lower than
  the policy's `index_serial`, and reject a digest the index does not list
  under the same name or lists as yanked, a source whose tag is not the
  version the index lists for its digest, and a chart whose digest differs
  from the index. The documentation MUST state that Kapitan's `--fetch`
  provides no integrity check.

  A higher serial is accepted and reported, so the consumer raises
  `index_serial` in a reviewed commit. Every OCI dependency under
  `ghcr.io/<owner>/` counts as a marketplace artifact.

  oras, `gh attestation verify` and Kapitan ignore a tag next to a digest:
  `<name>:1.0.3@<digest of 1.0.0>` fetches and verifies 1.0.0. The tag is
  what reviewers and Renovate read, so a tag that names another version
  fails.

  The tag lets the Renovate preset `github>kadet-hub/renovate-config`
  propose updates from the registry tags. Renovate does not read the index,
  so it can propose a version yanked after its release; this check rejects
  it in that pull request.

  - Test: `consumer/test_consumer.py`; manual: AC-6 consumer run (2026-10-09)
  - Since: #15, #234

- CON-3: The consumer documentation MUST state what listing covers and what it
  does not, referring to the threat model.
  - Test: none
  - Since: #15

## Recipes

Kapitan 0.36.3 resolves the inventory before it fetches and does not reload
it afterwards (kapicorp/kapitan#1638). A recipe class that is missing stops
`kapitan inventory` with `Class recipes.<name> not found`, and a recipe that
is present but stale compiles in its old version even under
`--force-fetch`. The consumer therefore pins recipes in a separate fetch
inventory, which holds nothing but those pins, as RCP-15 in kadet-hub/recipes
does for local compiles:

```yaml
# .kapitan-sandbox.yaml
fetch_inventory: fetch        # optional; a Kapitan inventory path with targets/
```

```yaml
# fetch/targets/recipes.yml
parameters:
  kapitan:
    dependencies:
      - type: oci
        source: ghcr.io/kadet-hub/recipes/cert-manager:1.0.0@sha256:<digest>
        output_path: inventory/classes/recipes/cert-manager
```

The generators a recipe pins are dependencies in the recipe's own classes.
After the recipes are in place they are part of the main inventory, and
CON-1 checks, fetches and verifies them like any generator.

- CON-4: When the policy names a `fetch_inventory`, the reusable workflow
  MUST, before step 1 of CON-1:

  1. run `kapitan inventory --inventory-path <fetch_inventory>` in the SEC-9
     sandbox as in step 1;
  2. fail unless every target's `parameters.kapitan` holds only
     `dependencies`, and each dependency is an `oci` source
     `ghcr.io/<owner>/recipes/<name>[:<version>]@sha256:<digest>` with
     `output_path: inventory/classes/recipes/<name>`;
  3. fetch these outside the sandbox and verify them (CON-5), then fail
     unless, for each recipe whose record lists `includes` (REC-13), the
     fetch inventory pins every included recipe at exactly the listed
     digest;
  4. unpack each into the project at its `output_path`, replacing what the
     checkout holds there.

  Step 2 of CON-1 MUST then fail on a recipe source in the main inventory.
  The GitLab template (CON-1a) MUST run the same steps.

  A recipe pinned in the main inventory would be fetched after Kapitan
  loaded the inventory, so the workflow would verify the new recipe and
  compile the old one. All recipes of a project share
  `inventory/classes/recipes/`, so two parents that include the same recipe
  at different digests cannot both be satisfied, and step 3 names both.
  The included recipes stay in the fetch inventory because the local
  compile of CON-6 fetches only what it lists. `fetch_inventory` is a path
  relative to the repository root without `..`, as `output_path` is. The
  Renovate preset `github>kadet-hub/renovate-config` matches
  `**/inventory/**` only and needs a pattern for the fetch inventory
  (kadet-hub/renovate-config, follow-up).

  Kapitan 0.36.3 writes `compile`, `labels`, `secrets`,
  `target_full_path`, `validate` and `vars.target` into every target's
  `parameters.kapitan`, empty when the target does not set them. Step 2
  accepts these keys while they are empty, so a fetch target that sets
  `vars.target` fails. The dependencies pass the OCI checks of CON-1 step
  2, so `hosts.oci` must allow `ghcr.io`, which the generators the recipes
  pin need anyway. A recipe source in the main inventory fails whether or
  not the policy names a fetch inventory. `consumer/run` holds the steps,
  so the GitHub workflow and the GitLab template run them alike.

  - Test: `consumer/test_consumer.py` (`FetchInventory`, `Includes`, `Dependencies.test_recipe_in_main_inventory`); `consumer-selftest` (`fail-recipe-main-inventory`, `fail-fetch-inventory-shape`); manual: `consumer/run` with `SANDBOX_TRACE=0` on a cert-manager fetch inventory against index serial 64 (2026-10-26) (partial: the AC-12 samples that fetch from ghcr.io and the AC-14 samples are not written, since `consumer-selftest` has neither oras nor a token for `gh attestation verify`, and no published recipe includes another yet)
  - Since: #397

- CON-5: Verification of a recipe MUST check the artifact attestation as
  CON-2 does for `oci://ghcr.io/kadet-hub/recipes/<name>@sha256:<digest>`,
  and reject a digest that the index's `recipes` section (REC-13) does not
  list under the same name or lists as yanked, and a tag that is not the
  version listed for the digest. CON-1b applies to the compiled output
  unchanged.

  A recipe adds no binaries to the compile's trace policy. Its output
  capabilities are in the index record and on its catalog page (CAT-38), so
  the consumer sees which `output_capabilities` its policy needs before the
  first run fails; the cert-manager recipe renders admission webhooks.

  - Test: `consumer/test_consumer.py` (`RecipeIndex`); manual: the CON-4 run
  - Since: #397

- CON-6: `docs/consumers.md` MUST describe the fetch inventory, the policy
  field, the two commands of a local compile
  (`kapitan compile --inventory-path fetch --force-fetch --output-path .`
  and `kapitan compile`) and the verification of a recipe by hand.

  - Test: none
  - Since: #397
