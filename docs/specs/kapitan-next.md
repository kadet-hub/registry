# Kapitan generator marketplace: Kapitan next

Status: As-built
Code: kadet-hub/kapitan `.github/workflows/next.yml` (from kapicorp/kapitan#1637), its repository variables and secret, the GitHub App `kadet-hub-kapitan-next`, `ghcr.io/kadet-hub/kapitan`
Verified against: kadet-hub/kapitan next @ 6f288a2, running the workflow of kapicorp/kapitan#1637 at 6b4302f; kadet-hub/recipes main @ e54cf9f

Related: kadet-hub/recipes
[`docs/specs/recipes.md`](https://github.com/kadet-hub/recipes/blob/main/docs/specs/recipes.md)
RCP-24 and RCP-29 consume the image; kapicorp/kapitan#1637 holds the
workflow; kadet-hub/kapitan#1 is the status issue.

## Problem

kadet-hub depends on Kapitan changes that are open upstream pull requests,
such as the omegaconf pin and the reload after fetch
(kapicorp/kapitan#1640, #1641). Some of them only make sense together, and
a release that contains them is not in sight. Recipes and generators should
be tested against those changes before they are released, so that a
breaking change shows up as a report and not on release day. A branch that
merges the PRs by hand goes stale within days, which is what happened to
the earlier `bleeding-edge` branch.

kadet-hub/kapitan is a fork of kapicorp/kapitan whose default branch `next`
a workflow rebuilds from upstream `master` plus open upstream PRs. It
publishes the result as the image `ghcr.io/kadet-hub/kapitan:next`. This
spec records how that build works today.

## Decisions

- DEC-24: This spec lives in kadet-hub/registry, not in kadet-hub/kapitan.

  The fork has no changes of its own, which its description states. Every
  rebuild force-pushes `next` from upstream `master` plus PRs and keeps only
  `.github/workflows/next.yml` from the previous `next` (NXT-6). A spec
  committed to the fork would be dropped on the next rebuild. kadet-hub/recipes
  is the only consumer today, but the image is shared kadet-hub
  infrastructure like the mirrors of PUB-13, whose specs live here.

- DEC-25: The workflow is contributed upstream as kapicorp/kapitan#1637, and
  the fork runs it through repository variables instead of carrying a
  variant.

  A fork-only workflow would be simpler to change, but it would have to be
  committed to `next` and kept there by hand. Upstream, the same workflow
  builds a shared `next` from PRs labelled `next`. If #1637 is merged, the
  fork keeps working without changes.

- DEC-26: The fork takes the open PRs of one maintainer (`NEXT_AUTHOR`) and
  Dependabot's PRs once their checks pass, not labelled PRs.

  A fork cannot label upstream PRs. Taking every open PR would put code
  from anyone into an image that kadet-hub CI runs. A later push to a
  selected PR lands in `next` without another look, so the selection is
  limited to authors that are trusted anyway.

- DEC-27: The fork pushes `next` with a token of a GitHub App installed on
  kadet-hub/kapitan only, with `contents` and `workflows` write.

  `GITHUB_TOKEN` cannot hold the `workflows` permission, and GitHub rejects
  a push of commits that change workflow files unless those commits already
  exist in the repository. Upstream they do, under `refs/pull/<n>/head`. In
  the fork they are new, as kapicorp/kapitan#1637 records. A personal access
  token would work too (the earlier `NEXT_PUSH_TOKEN` of 3f7072a), but it
  acts as a person and reaches every repository that person can write to.

## Selection

- NXT-1: With `NEXT_AUTHOR` set, the workflow MUST take every open PR of
  `NEXT_SOURCE` whose author is that login, without a label.

  - Test: manual: the `Merged:` and `Conflicting:` lines of the latest
    `next` commit list every open kapicorp/kapitan PR by `NEXT_AUTHOR`
  - Since: kapicorp/kapitan#1637 (37250d0), kadet-hub/kapitan variables set
    2026-10-23

- NXT-2: The workflow MUST take an open PR by a login in
  `NEXT_GREEN_AUTHORS` only when its head has at least one check and every
  check concluded `SUCCESS`, `SKIPPED` or `NEUTRAL`.

  The selection runs before the fingerprint (NXT-7), so a PR that turns
  green triggers a rebuild. In the fork the list is `dependabot[bot]`.

  - Test: none
  - Since: kapicorp/kapitan#1637 (6b4302f)

- NXT-3: Without `NEXT_AUTHOR`, the workflow MUST take only open PRs
  labelled `next` whose author has write, maintain or admin permission on
  `NEXT_SOURCE`.

  This is the upstream mode and does not run in the fork. The version the
  fork runs (6b4302f) still checks `author_association`, which triage users
  can pass by setting the label themselves. #1637 replaced that with a
  permission query in 5ab8799 (OQ-13).

  - Test: manual: the permission query returns `write` for a maintainer
    and `read` for an outside account, per kapicorp/kapitan#1637
  - Since: kapicorp/kapitan#1637 (b6f65bc, permission query 5ab8799); not
    run in the fork

## Assembly

The workflow fetches `master` of `NEXT_SOURCE` and merges each selected PR
with `--no-ff` in ascending PR number. The PR number order is stable across
rebuilds, so a conflict between two PRs always leaves out the later one. A
PR whose head moved between listing and fetching is merged at its new head,
with a warning in the run.

- NXT-4: A PR that does not merge cleanly onto `master` and the PRs merged
  before it MUST be left out with `git merge --abort`, and the remaining
  PRs MUST still be tried.

  At 6f288a2, 53 PRs are merged and kapicorp/kapitan#1641 is left out. The
  workflow does not resolve conflicts. A PR that is left out stays out until
  it is rebased or an earlier PR leaves.

  - Test: manual: `Conflicting:` line of the latest `next` commit and the
    status issue
  - Since: kapicorp/kapitan#1637 (b6f65bc)

- NXT-5: The rebuild MUST end in one commit on top of the merges whose
  message names the upstream `master` commit, the merged and the left-out
  PRs, and the fingerprint as a `Next-Fingerprint:` trailer, and MUST
  force-push it to `next`.

  - Test: manual: `git log -1 origin/next`
  - Since: kapicorp/kapitan#1637 (b6f65bc)

- NXT-6: The rebuild MUST restore `.github/workflows/next.yml` from the
  commit the run started on.

  In the fork `next` is the default branch, and scheduled runs start from
  the default branch, so the workflow must survive a rebuild whose PRs do
  not contain it. A side effect is that a newer version of the workflow in
  #1637 never replaces the one the fork runs (OQ-13).

  - Test: manual: `git rev-parse origin/next:.github/workflows/next.yml`
    equals the blob of the version the fork was bootstrapped with
  - Since: kapicorp/kapitan#1637 (37250d0)

## Rebuilds

- NXT-7: A run MUST stop after the selection when the fingerprint equals
  the `Next-Fingerprint:` of the current `next` commit. The fingerprint is
  the upstream `master` commit, the blob of `next.yml` and every selected
  PR number with the head commit seen in the listing.

  - Test: manual: a dispatched run right after a rebuild ends with
    "Nothing changed since next was last built."
  - Since: kapicorp/kapitan#1637 (b6f65bc)

- NXT-8: The workflow MUST run on a `*/15` cron schedule, on
  `workflow_dispatch` and on a push to `master`, one run at a time without
  cancelling a running one.

  GitHub runs schedules best effort. Between the first scheduled run on
  2026-10-23 13:28 UTC and 2026-10-25 01:46 UTC there were 12 scheduled
  runs where the cron asks for about 145, at gaps of 2 to 4.7 hours.
  The fork's `master` is not synced automatically, so the push trigger does
  not fire there, and a fork receives no events for upstream PRs. Whoever
  needs a fresh build dispatches the workflow:
  `gh workflow run next -R kadet-hub/kapitan`.

  - Test: none; `gh run list -R kadet-hub/kapitan -w next` shows the runs
  - Since: kapicorp/kapitan#1637 (b6f65bc)

## Push

- NXT-9: In the fork, `assemble` MUST check out and push with a token from
  the GitHub App `kadet-hub-kapitan-next`, created per run by
  `actions/create-github-app-token` for the repository `kapitan` with
  `contents: write` and `workflows: write`. API calls of the run MUST use
  `GITHUB_TOKEN`.

  The App has `contents` and `workflows` write and `metadata` read, no
  events, and is installed on kadet-hub/kapitan only. Its client ID is the
  variable `NEXT_APP_CLIENT_ID`, its private key the secret
  `NEXT_APP_PRIVATE_KEY`. Without the variable the workflow falls back to
  `GITHUB_TOKEN`, which is the upstream case (DEC-27).

  - Test: manual: `assemble` of the latest run passes and `next` moved
  - Since: kapicorp/kapitan#1637 (6b4302f), App installed 2026-10-23

## Image and wheel

- NXT-10: Every rebuild MUST push a `linux/amd64` image built from the
  `next` commit as `ghcr.io/kadet-hub/kapitan:next` and
  `ghcr.io/kadet-hub/kapitan:next-<first 12 hex digits of the commit>`, and
  upload the wheel as the run artifact `kapitan-next-wheel` for 14 days.
  The package MUST be public.

  The version comes from `uv-dynamic-versioning` over the upstream tags.
  The label `org.opencontainers.image.revision` names the `next` commit.
  An anonymous pull of `next` returns `sha256:fca6da0d…` at 6f288a2.

  - Test: manual: anonymous `docker pull ghcr.io/kadet-hub/kapitan:next`
  - Since: kapicorp/kapitan#1637 (b6f65bc)

- NXT-11: The image and the status issue MUST say that `next` contains
  unreviewed changes and is for testing only.

  The image's `org.opencontainers.image.description` says so, as do the
  status issue and the fork's description. The content of `next` is code
  from open PRs that no upstream maintainer has approved. kadet-hub uses it
  in reports only. RCP-24 lets a failed or different compile on `next`
  change no exit status.

  - Test: manual: `docker inspect` of the image and the issue body
  - Since: kapicorp/kapitan#1637 (b6f65bc)

- NXT-12: The inventory and compile tests MUST run on every rebuild, and
  their result MUST be reported in the status issue. The image MUST NOT
  wait for them.

  `test` and `image` both depend only on `assemble`, so `next` and
  `next-<sha>` move even when `test_omegaconf`, `test_inventory`,
  `test_inventory_backend_examples` or `test_compile` fail. A consumer that
  needs a passing build reads the result from the status issue, which names
  the image by digest.

  - Test: manual: the line "Inventory and compile tests" in
    kadet-hub/kapitan#1
  - Since: kapicorp/kapitan#1637 (b6f65bc)

## Status issue

- NXT-13: After every rebuild, `report` MUST write the open issue titled
  "next: integration status", creating it when none exists, with the
  `next` commit, its `master` base, the image `next-<sha>` with its digest,
  the test result, the run, and a table of merged and of left-out PRs with
  title, author and the head commit taken.

  In the fork this is kadet-hub/kapitan#1. It runs even when `test` or
  `image` fail, and then says "not built in this run" for the image.

  - Test: manual: kadet-hub/kapitan#1 names the current `next` commit
  - Since: kapicorp/kapitan#1637 (a9e1272)

## Consumers

kadet-hub/recipes compiles every recipe a second time with the `next` image
pinned by digest in `check/check.py` and reports what differs from Kapitan
0.36.3 (RCP-24). Renovate moves that digest to the current `next` in a
daily window, in a PR that does not merge automatically (RCP-29).

- NXT-14: A consumer MUST pin `ghcr.io/kadet-hub/kapitan` by digest and
  name the tag `next` next to it, not `next-<sha>`.

  A new build can follow every 15 minutes, so a moving tag without a
  digest would change a consumer's result between two runs of the same
  commit.
  Renovate cannot order the `next-<sha>` tags, which is why the pin names
  `next` and Renovate updates its digest.

  - Test: kadet-hub/recipes `check/check.py` (`KAPITAN_NEXT`); RCP-29
  - Since: kadet-hub/recipes#2, #3

Consumers lag behind `next` until Renovate moves the pin. On 2026-10-25 the
recipes pin still pointed at `sha256:a7b7a163…`, an image whose omegaconf
lacks `ListMergeMode`, so the `next` compile failed for every recipe.
kadet-hub/recipes#11 moves the pin by hand to `sha256:fca6da0d…`. It
records two causes: Renovate had not processed the repository yet, and
`minimumReleaseAge` with `timestamp-required` would hold a digest update of
a moving tag forever. Even once Renovate works, a fix that lands in `next`
reaches the recipes report at the next schedule window plus a merge (OQ-14).

## Verification

- AC-13 (NXT-1, NXT-4, NXT-5, NXT-10, NXT-13): after a dispatched run, the
  latest `next` commit lists every open kapicorp/kapitan PR of
  `NEXT_AUTHOR` as merged or conflicting, an anonymous pull of
  `ghcr.io/kadet-hub/kapitan:next-<sha>` of that commit succeeds, and
  kadet-hub/kapitan#1 names the same commit and digest.

## Open questions

- OQ-13: How does a change to `next.yml` in kapicorp/kapitan#1637 reach the
  fork? NXT-6 restores the running version on every rebuild, so the fork
  still runs 6b4302f while #1637 is at 5ab8799. Today the difference only
  touches the upstream mode (NXT-3). Options are a manual push of the new
  file to `next`, or taking `next.yml` from the PR head when the PR is
  merged into `next`. If #1637 is merged upstream, the file comes with
  `master`, but NXT-6 would still overwrite it.
- OQ-14: Should consumers follow `next` faster than the Renovate window of
  RCP-29, for example by a dispatch from the `report` job to kadet-hub/recipes,
  or is a lag of up to a day plus a review acceptable for a report that
  never gates?

## Implementation inventory

| Path | Purpose |
|---|---|
| kadet-hub/kapitan `.github/workflows/next.yml` | NXT-1 to NXT-13, version of kapicorp/kapitan#1637 at 6b4302f |
| kapicorp/kapitan#1637 `CONTRIBUTING.md` | "Testing unmerged changes on `next`" |
| kadet-hub/recipes `check/check.py` | `KAPITAN_NEXT` pin (NXT-14, RCP-24) |
| kadet-hub/recipes `renovate.json` | Moves the pin (RCP-29) |

| Value | Setting |
|---|---|
| Fork | kadet-hub/kapitan, public, default branch `next` |
| `NEXT_SOURCE` | `kapicorp/kapitan` |
| `NEXT_AUTHOR` | the maintainer's GitHub login |
| `NEXT_GREEN_AUTHORS` | `dependabot[bot]` |
| `NEXT_APP_CLIENT_ID` | client ID of the App `kadet-hub-kapitan-next` |
| Secret | `NEXT_APP_PRIVATE_KEY` |
| GitHub App | `kadet-hub-kapitan-next`: contents write, workflows write, metadata read; installed on kadet-hub/kapitan only |
| Image | `ghcr.io/kadet-hub/kapitan:next`, `:next-<sha>`, public, `linux/amd64` |
| Wheel | run artifact `kapitan-next-wheel`, 14 days |
| Status issue | kadet-hub/kapitan#1, "next: integration status" |
