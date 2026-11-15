# Kapitan generator marketplace: krab next

Status: Draft
Code: kadet-hub/krab `.github/workflows/next.yml`, `Dockerfile` and `.dockerignore`, its repository variables and secret, the installation of the GitHub App `kadet-hub-kapitan-next` on kadet-hub/krab, `ghcr.io/kadet-hub/krab`
Verified against: kadet-hub/krab next @ tbd

Related: [kapitan-next.md](kapitan-next.md), whose workflow this build
ports; kapicorp/krab#319, the closed pull request the Dockerfile comes from.

## Problem

krab (kapicorp/krab) is Kapitan rewritten in Rust. Its open upstream pull
requests can only be tried by building them by hand, and krab publishes no
container image: the image per release that kapicorp/krab#319 proposed was
closed without a merge.

kadet-hub/krab is a fork of kapicorp/krab whose default branch `next` a
workflow rebuilds from upstream `main` plus open upstream pull requests, and
publishes as the image `ghcr.io/kadet-hub/krab:next`. The build works like
the `next` of kadet-hub/kapitan. This spec states where it differs and cites
the NXT requirements of [kapitan-next.md](kapitan-next.md) for the rest. No
kadet-hub repository uses the image yet. A consumer pins it by digest and
names the tag `next`, for the reasons of NXT-14.

## Decisions

- DEC-49: The fork carries its own `.github/workflows/next.yml`,
  `Dockerfile` and `.dockerignore`, and nothing of the build goes upstream
  to kapicorp/krab.

  With kapicorp/krab#319 closed there is no upstream version the fork could
  run through repository variables, as DEC-25 does for Kapitan. The fork
  maintains the three files alone and no upstream maintainer reviews them.
  They are its only changes, which the fork's description states. The spec
  lives here for the reason of DEC-24.

- DEC-50: The fork pushes `next` with the GitHub App
  `kadet-hub-kapitan-next`, installed on kadet-hub/krab in addition to
  kadet-hub/kapitan.

  The reasons of DEC-27 apply to krab as well. Of the open kapicorp/krab
  pull requests on 2026-11-15, the Dependabot bumps #252, #254, #255, #314
  and #316 and three PRs of `NEXT_AUTHOR` (#291, #308, #309) change files
  under `.github/workflows/`, and GitHub rejects those commits from
  `GITHUB_TOKEN`.

  The cost of one App for both forks is that a private key leaked from the
  secret of either repository can push to the `next` of both. Each run asks
  for a token of its own repository only, which does not limit a leaked key.
  A second App would keep the forks apart, but has to be created in the
  browser and adds a second App to maintain. Both forks select code by the
  same rule (DEC-26) and serve the same purpose, so one App is used.

## Selection

- KNX-1: The workflow MUST take every open kapicorp/krab PR of
  `NEXT_AUTHOR` as NXT-1 describes, every open PR of a login in
  `NEXT_GREEN_AUTHORS` as NXT-2 describes, and no other PR.

  The labelled mode of NXT-3 is left out because the workflow runs only in
  the fork. With `NEXT_AUTHOR` empty the workflow takes only the green PRs.
  Without `NEXT_SOURCE` it does not run.

  - Test: manual: the `Merged:` and `Conflicting:` lines of the latest
    `next` commit list every open kapicorp/krab PR of `NEXT_AUTHOR`
  - Since: not implemented

## Assembly and the fork's own files

- KNX-2: The rebuild MUST assemble `next` from kapicorp/krab `main` as NXT-4
  and NXT-5 describe for `master`.

  Each selected PR is merged with `--no-ff` in PR number order, a PR that
  conflicts is left out, and the result is one commit with a
  `Next-Fingerprint:` trailer, force-pushed to `next`.

  - Test: manual: `git log -1 origin/next` names the `main` commit and the
    merged and left-out PRs
  - Since: not implemented

- KNX-3: The rebuild MUST take `.github/workflows/next.yml`, `Dockerfile`
  and `.dockerignore` from the commit the run started on, replacing any
  version that `main` or a merged PR brings.

  Scheduled runs start from `next`, the default branch, so each rebuild
  hands the files on to the following one. NXT-6 lets a version from
  upstream win instead. Here nothing upstream carries the files (DEC-49),
  and a `Dockerfile` that upstream might add later would not expect the
  binary where the workflow puts it (KNX-8).

  - Test: manual: `git diff <start commit of the run> origin/next --
    .github/workflows/next.yml Dockerfile .dockerignore` prints nothing
  - Since: not implemented

A change to one of the three files is a signed commit pushed on top of
`next`, followed by a dispatch of the workflow. The commit has no
`Next-Fingerprint:` trailer, so the dispatched run rebuilds and carries the
change on. A run that was already in progress started from the commit
before and force-pushes over the change, so push only while no run of
`next` is in progress.

- KNX-4: The fingerprint MUST be that of NXT-7 with the blobs of all three
  files of KNX-3 in place of the blob of `next.yml`.

  A run started from a commit whose files differ from those of the last
  rebuild therefore rebuilds.

  - Test: manual: a dispatched run right after a rebuild ends with
    "Nothing changed since next was last built."
  - Since: not implemented

## Rebuilds and push

- KNX-5: The workflow MUST run on a `*/15` cron schedule and on
  `workflow_dispatch`, one run at a time without cancelling a running one.

  The push trigger of NXT-8 is left out because nothing pushes the fork's
  `main`. Schedules run best effort, as NXT-8 records for Kapitan, so
  whoever needs a fresh build runs `gh workflow run next -R kadet-hub/krab`.

  - Test: none; `gh run list -R kadet-hub/krab -w next` shows the runs
  - Since: not implemented

- KNX-6: `assemble` MUST check out and push with a token of the App
  `kadet-hub-kapitan-next`, created per run for the repository `krab` with
  `contents: write` and `workflows: write`. API calls of the run MUST use
  `GITHUB_TOKEN`.

  The client ID is the variable `NEXT_APP_CLIENT_ID` and the private key
  the secret `NEXT_APP_PRIVATE_KEY`. Without them the run fails at the
  token step. The Kapitan workflow falls back to `GITHUB_TOKEN` there
  (NXT-9), but in this fork the push would be rejected as soon as one
  merged PR changes a workflow file (DEC-50).

  - Test: manual: `assemble` of the latest run passes and `next` moved
  - Since: not implemented

## Tests and image

- KNX-7: Every rebuild MUST run `cargo test --locked` on the `next` commit,
  and the image MUST be pushed only when it passes.

  The test job installs the Python packages of the test job in kapicorp/krab
  `ci.yml` (PyYAML, omegaconf 2.4.0.dev3, kadet, jinja2) on Python 3.13, the
  `python3` of Debian trixie that the image runs kadet with. Clippy, the
  parity job against Kapitan, the MSRV check and cargo-deny of upstream CI
  do not run on `next`. As in NXT-12, a failing test leaves the `next` tag
  on the last tested build while the branch already has the failing commit.

  - Test: manual: the line "cargo test" in the status issue, and a failed
    run whose `image` job is skipped
  - Since: not implemented

- KNX-8: Every rebuild whose tests passed MUST push a `linux/amd64` image
  of the `next` commit as `ghcr.io/kadet-hub/krab:next` and
  `ghcr.io/kadet-hub/krab:next-<first 12 hex digits of the commit>`, with a
  build provenance attestation pushed to the registry. The package MUST be
  public.

  - Test: manual: anonymous `docker pull ghcr.io/kadet-hub/krab:next`, and
    `gh attestation verify oci://ghcr.io/kadet-hub/krab@<digest> --owner kadet-hub`
  - Since: not implemented

The `image` job compiles krab with `cargo build --release --locked -p krab`
on the ubuntu-24.04 runner and copies the binary to `bin/amd64/krab`, where
the Dockerfile expects it. The toolchain is the one that
`rust-toolchain.toml` of `next` names, and upstream PRs move it. A builder
stage in the Dockerfile would need a Rust image pinned by hand to the same
version. The runner's glibc 2.39 is older than the 2.41 of Debian trixie,
so the binary runs in the image.

The Dockerfile is that of kapicorp/krab#319 at 2aa6aa1 with only its header
comment changed. The image contains:

- `krab` in `/usr/local/bin` as the entrypoint, run as user 999, the user
  Argo CD runs config management plugins as
- Debian trixie-slim pinned by digest, with `ca-certificates`, `git` for git
  dependencies and `gnupg` for the `gpg` ref backend
- a venv in `/opt/krab/python` with kadet 0.3.2 and jinja2 3.1.6, the
  packages of `BASELINE` in krab's `crates/krab-compile/src/pyenv.rs`, and
  `KRAB_PYTHON` pointing to it, so krab installs nothing at run time and the
  root filesystem can stay read-only
- helm 4.3.2 for helm inputs, checked against the SHA-256 that get.helm.sh
  publishes

Nothing updates these pins. A bump is a commit on `next` as KNX-3 describes
(OQ-44).

- KNX-9: The image, the status issue and the fork's description MUST say
  that `next` contains unreviewed changes and is for testing only.

  The reason is that of NXT-11. The image says so in
  `org.opencontainers.image.description`.

  - Test: manual: `docker inspect` of the image, the issue body and
    `gh repo view kadet-hub/krab`
  - Since: not implemented

## Status issue

- KNX-10: After every rebuild, `report` MUST write the status issue of
  NXT-13 in kadet-hub/krab, with the `cargo test` result in place of the
  inventory and compile tests.

  Issues are disabled in a new fork, so they are enabled on kadet-hub/krab.

  - Test: manual: the status issue names the current `next` commit
  - Since: not implemented

## Verification

- AC-49 (KNX-1, KNX-3, KNX-6, KNX-8, KNX-10): after a dispatched run, the
  latest `next` commit lists every open kapicorp/krab PR of `NEXT_AUTHOR` as
  merged or conflicting and has the three files of KNX-3 of the run's start
  commit. An anonymous pull of `ghcr.io/kadet-hub/krab:next-<sha>` of that
  commit succeeds, `docker run --rm` of it with `--version` prints `krab`
  and the version of kapicorp/krab `Cargo.toml`, the attestation verifies,
  and the status issue names the same commit and digest.

## Open questions

- OQ-44: Should Renovate update the pins of the Dockerfile? It would need a
  Renovate config on `next` as a fourth file of KNX-3, and Renovate PRs
  against a branch that is force-pushed every rebuild.

## Implementation inventory

| Path | Purpose |
|---|---|
| kadet-hub/krab `.github/workflows/next.yml` | KNX-1 to KNX-10 |
| kadet-hub/krab `Dockerfile`, `.dockerignore` | The image of KNX-8, from kapicorp/krab#319 at 2aa6aa1 |

| Value | Setting |
|---|---|
| Fork | kadet-hub/krab, public, default branch `next`, issues enabled |
| `NEXT_SOURCE` | `kapicorp/krab` |
| `NEXT_AUTHOR` | the maintainer's GitHub login, as in kadet-hub/kapitan |
| `NEXT_GREEN_AUTHORS` | `dependabot[bot]` |
| `NEXT_APP_CLIENT_ID` | client ID of the App `kadet-hub-kapitan-next` |
| Secret | `NEXT_APP_PRIVATE_KEY`, a private key of that App |
| GitHub App | `kadet-hub-kapitan-next`, installed on kadet-hub/kapitan and kadet-hub/krab (DEC-50) |
| Image | `ghcr.io/kadet-hub/krab:next`, `:next-<sha>`, public, `linux/amd64` |
| Status issue | kadet-hub/krab, "next: integration status", number tbd |
