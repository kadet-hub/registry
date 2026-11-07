---
title: Renovate automerge with required reviews on GitHub
layout: prose
description: "Renovate automerge on GitHub with a required code-owner review: a pull_request ruleset bypass for the Renovate app, and Renovate waits for every check."
lastmod: 2026-11-07
aliases: [/blog/renovate-automerge-required-reviews/]
---

Renovate's automerge stops at a branch that requires an approving review.
Its documentation says so: "If you have mandatory Pull Request reviews then
it means Renovate can't automerge its own PR until such a review has
happened"
([Renovate docs](https://docs.renovatebot.com/key-concepts/automerge/#required-pull-request-reviews)).
The `main` ruleset of kadet-hub/registry requires one approving review and
a code-owner review. Since 2 November 2026 Renovate merges its own minor,
patch and digest updates there without either. The Renovate GitHub App has
a ruleset bypass that works on pull requests only. GitHub's auto-merge
stays off, so Renovate merges once every check on the pull request has
passed, including the checks the ruleset does not require.

The change is
[kadet-hub/registry#441](https://github.com/kadet-hub/registry/pull/441).
The first pull request merged this way was
[#439](https://github.com/kadet-hub/registry/pull/439), a digest update of
the distroless `debug` image that the [gate](/glossary/#gate)'s sandbox
image copies its busybox from. The GitHub docs quoted below were read on
2 November 2026, the Renovate docs and source at Renovate 44.201.0.

## Why an approval bot does not help

Renovate's docs name two ways past a required review on GitHub. One is a
bypass of the review requirement. The other is the helper apps
renovate-approve and renovate-approve-2, which "will mark all automerging
Pull Requests by Renovate as approved"
([Renovate docs](https://docs.renovatebot.com/key-concepts/automerge/#required-pull-request-reviews)).

An approval from an app does not satisfy a code-owner review. With
code-owner review required, "any pull request that modifies content with a
code owner must be approved by that code owner"
([GitHub docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets#require-a-pull-request-before-merging)).
A CODEOWNERS file lists owners as "GitHub usernames or team names"
([GitHub docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners#codeowners-syntax)).
A workflow that approves with its `GITHUB_TOKEN` approves as an app too,
because "The `GITHUB_TOKEN` secret is a GitHub App installation access
token"
([GitHub docs](https://docs.github.com/en/actions/concepts/security/github_token)).
Renovate's docs put it this way: "having a `CODEOWNERS` file could block
automerging, because it means a code owner must review the PR"
([Renovate docs](https://docs.renovatebot.com/key-concepts/automerge/#codeowners)).

kadet-hub/registry has a code owner for `.github/`, `gate/`, `policy/`,
`scan/`, `sandbox/` and `.clusterfuzzlite/`. Every file Renovate updates in
that repository sits under one of them, apart from the registry entries.
#439 changed `sandbox/Dockerfile`.

GitHub's auto-merge is the other half of that setup, and Renovate uses it
by default. "Auto-merge merges a pull request automatically after all
required reviews and status checks pass"
([GitHub docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request#about-auto-merge)).
It does not wait for a check the branch does not require. The registry's
ruleset requires two checks, `gate` and `renders`.

Several checks that exercise a dependency update in this repository come
from path-filtered workflows. `selftest` runs the gate's self tests when
`sandbox/`, `gate/`, `scan/`, `policy/` or a few other paths change.
`sandbox-advisories`
fails on an advisory that has a fix for the sandbox image. GitHub's
troubleshooting page says that the checks of a workflow skipped by path
filtering "stay in a "Pending" state and block merging", and advises:
"Avoid requiring workflows that can be skipped"
([GitHub docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks#handling-skipped-but-required-checks)).
So these checks are not required, and auto-merge would not wait for them.

## A bypass for pull requests only

#441 added one entry to the bypass list of the `main` ruleset. The
repository keeps a copy of the ruleset in `.github/ruleset.json`:

```diff
-  "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}],
+  "bypass_actors": [
+    {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"},
+    {"actor_id": 2740, "actor_type": "Integration", "bypass_mode": "pull_request"}
+  ],
```

`Integration` is the actor type of a GitHub App. `2740` is the ID that
`gh api /apps/renovate` returns for the Renovate app. The live ruleset
carries the same entry:

    $ gh api repos/kadet-hub/registry/rulesets/24720369 --jq '.bypass_actors[] | select(.actor_type == "Integration")'
    {"actor_id":2740,"actor_type":"Integration","bypass_mode":"pull_request"}

The REST API accepts `always`, `pull_request` and `exempt` for
`bypass_mode`, and its reference says: "pull_request means that an actor
can only bypass rules on pull requests"
([GitHub REST docs](https://docs.github.com/en/rest/repos/rules#update-a-repository-ruleset)).
The default is `always`. An entry that leaves `bypass_mode` out lets the
app push to `main` directly.

In the ruleset editor, `pull_request` is the option "For pull requests
only", which GitHub offers "to grant bypass to an actor without allowing
them to push directly to a repository". The same page goes on:

> The selected actor is now required to open a pull request to make
> changes to a repository, creating a clear trail of their changes in the
> pull request and audit log. The actor can then choose to bypass any
> branch protections and merge that pull request.

([GitHub docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository#granting-bypass-permissions-for-your-branch-or-tag-ruleset))

The bypass covers the rules of the whole ruleset, the required status
checks among them. Once the app is on the list, GitHub no longer stops its
merge on a failed check. That job moves to Renovate.

## What Renovate waits for

The top of `renovate.json` leaves automerge off by default and switches
GitHub's auto-merge off:

```json
  "automerge": false,
  "platformAutomerge": false,
  "minimumReleaseAge": "3 days",
  "minimumReleaseAgeBehaviour": "timestamp-required",
```

With `platformAutomerge` at its default `true`, Renovate hands the merge to
the platform, which merges "after all (if any) branch policies have been
met"
([Renovate docs](https://docs.renovatebot.com/configuration-options/#platformautomerge)).
With `false`, Renovate merges with its own API call. For the default
`automergeType` of `pr`, Renovate "automerges the PR on a subsequent run
once it detects the PR's status checks are 'green'", and "Renovate only
automerges branches which are up-to-date and green"
([Renovate docs](https://docs.renovatebot.com/configuration-options/#automergetype)).
The entry for `ignoreTests` states the default: "Renovate's default
behavior is to only automerge if every status check has succeeded"
([Renovate docs](https://docs.renovatebot.com/configuration-options/#ignoretests)).

What green means on GitHub is decided in `getBranchStatus`
([Renovate 44.201.0 source](https://github.com/renovatebot/renovate/blob/44.201.0/lib/modules/platform/github/index.ts#L1188-L1288)).
It reads the commit statuses and the check runs of the branch's head
commit. One check run with the conclusion `failure` makes the branch red.
The branch is green only when every check run has the conclusion
`success`, `neutral` or `skipped` and the remaining commit statuses are
successful. A check run that is queued or still running has no conclusion
yet, so the branch stays yellow and Renovate does not merge. Successful
statuses that Renovate sets itself, such as `renovate/stability-days`, are
filtered out first, so they cannot turn a branch green on their own. GitHub
counts the same three conclusions as a passing required check
([GitHub docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks#required-check-needs-to-succeed-against-the-latest-commit-sha)).

Renovate sees only the checks that exist on the commit when it runs. A
workflow that has not created its check run yet cannot hold the merge.

## Which updates merge

The last three `packageRules` of `renovate.json` decide what Renovate may
merge:

```json
    {
      "description": "REV-5: Renovate merges its own pull request once every check passed",
      "matchUpdateTypes": [
        "minor",
        "patch",
        "digest",
        "pin",
        "pinDigest"
      ],
      "automerge": true
    },
    {
      "description": "REV-5: an entry bump publishes a new version, which a maintainer approves (DEC-3)",
      "matchFileNames": [
        "generators/*.yaml",
        "recipes/*.yaml"
      ],
      "automerge": false
    },
    {
      "description": "REV-5: a digest update of an action under the same version is a moved tag",
      "matchManagers": [
        "github-actions"
      ],
      "matchUpdateTypes": [
        "digest"
      ],
      "automerge": false
    }
```

The descriptions cite kadet-hub's specs. REV-5 is the automerge requirement
in [gate.md](https://github.com/kadet-hub/registry/blob/main/docs/specs/gate.md),
and DEC-3 is the decision in
[marketplace.md](https://github.com/kadet-hub/registry/blob/main/docs/specs/marketplace.md)
that every new version needs a maintainer's approval.

Renovate applies `packageRules` in order, and "later rules may override
configuration options from earlier ones, if they both specify the same
option"
([Renovate docs](https://docs.renovatebot.com/configuration-options/#packagerules)).
The first rule turns automerge on for five update types. A major update
matches none of the three and keeps the top-level `"automerge": false`.

The second rule covers the registry entries. Each file under `generators/`
and `recipes/` pins a generator or a recipe to a tag and commit in its
author's repository. Merging a bump of that pin publishes the new version
in the catalog, so these bumps stay with a maintainer whatever their update
type.

The third rule is about GitHub Actions. kadet-hub pins every action to a
commit SHA with the version as a comment, through the
`helpers:pinGitHubActionDigests` preset. A new release of an action changes
the version in that comment. A `digest` update under the same version
means that the tag now points at another commit. That is how
tj-actions/changed-files was compromised in March 2025: "Attackers
retroactively modified multiple version tags to reference a malicious
commit"
([GHSA-mrrh-fwg8-r2c3](https://github.com/advisories/GHSA-mrrh-fwg8-r2c3)).
The three days of `minimumReleaseAge` do not hold such an update back: "If
an existing tag is force-pushed to new commits, the digest update ages
against the original release date, so it may pass Minimum Release Age
immediately"
([Renovate docs](https://docs.renovatebot.com/key-concepts/minimum-release-age/#digest-updates)).

Everything else still waits three days after its release when the
datasource reports a release timestamp. kadet-hub's config treats git tags
and registries other than Docker Hub as reporting none and lets those
updates through without one (`minimumReleaseAgeBehaviour:
timestamp-optional`). Such an update merges as soon as its checks pass.

kadet-hub's threat model in marketplace.md records what this gives up. A
malicious minor, patch or image digest release now reaches `main` without
a maintainer once the release age allows it and every check passes. Before
#441 it needed one approval by the single maintainer.

[kadet-hub/recipes#56](https://github.com/kadet-hub/recipes/pull/56) made
the same change in kadet-hub/recipes and keeps more updates manual. Lock
file maintenance is not on its automerge list, because "the updated
packages have no release timestamp for Renovate to check"
([Renovate docs](https://docs.renovatebot.com/key-concepts/minimum-release-age/#lockfilemaintenance-updates)).
The pin of the `next` tag of kadet-hub's Kapitan image stays manual, since
that image is rebuilt up to every 15 minutes and its digest updates have no
release timestamp. A recipe's `Source` line names the chart or image the
recipe is built from, and updates to it wait for a reviewer. The `main` ruleset
there requires one approval without a code-owner review and has the same
`pull_request` bypass for the Renovate app.

## The first merge

#439 has no review, and GitHub still reports a review as required:

    $ gh pr view 439 -R kadet-hub/registry --json mergedBy,mergedAt,reviewDecision,reviews
    {"mergedAt":"2026-11-02T10:11:50Z","mergedBy":{"is_bot":true,"login":"app/renovate"},"reviewDecision":"REVIEW_REQUIRED","reviews":[]}

The check runs on its last commit, ordered by completion time in UTC:

    $ gh pr view 439 -R kadet-hub/registry --json statusCheckRollup \
        --jq '.statusCheckRollup | map(select(.__typename == "CheckRun")) | sort_by(.completedAt)[] | [.completedAt, .conclusion, .name] | @tsv'
    2026-11-02T09:25:20Z	SUCCESS	workflow-lint
    2026-11-02T09:25:24Z	SUCCESS	checksum-pins
    2026-11-02T09:25:31Z	SUCCESS	sandbox-advisories
    2026-11-02T09:25:49Z	SUCCESS	gate
    2026-11-02T09:25:49Z	SKIPPED	renders
    2026-11-02T09:25:59Z	SUCCESS	comment
    2026-11-02T09:26:06Z	SUCCESS	consumer-selftest
    2026-11-02T09:26:26Z	SUCCESS	CodeQL
    2026-11-02T09:26:31Z	SUCCESS	analyze
    2026-11-02T10:10:36Z	SUCCESS	gate-selftest

The same rollup holds one commit status, `renovate/stability-days`, with
the state `SUCCESS`.

`gate` and `renders` are the required checks. `renders` checks a recipe on
kind and runs only when the gate compiled one, so on #439 it was skipped.
A skipped job "will not prevent a pull request from merging, even if it is
a required check"
([GitHub docs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions)).
Both required checks were done at 09:25:49. `gate-selftest` finished at
10:10:36, and Renovate merged at 10:11:50.

GitHub keeps the rule evaluations of the merge as a rule suite, which the
REST API returns
([GitHub REST docs](https://docs.github.com/en/rest/repos/rule-suites#get-a-repository-rule-suite)):

    $ gh api repos/kadet-hub/registry/rulesets/rule-suites/4853993537 \
        --jq '{actor_name, ref, result, rules: [.rule_evaluations[] | {rule_type, result}]}'
    {"actor_name":"renovate[bot]","ref":"refs/heads/main","result":"bypass","rules":[{"result":"fail","rule_type":"pull_request"},{"result":"pass","rule_type":"required_status_checks"},{"result":"pass","rule_type":"non_fast_forward"},{"result":"pass","rule_type":"deletion"}]}

The `pull_request` rule failed, and its details name the missing
code-owner review. The required status checks passed on their own. The
merge went through as `bypass`.
