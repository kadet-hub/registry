# Kapitan generator marketplace: Agent identity

Status: Draft
Code: `.github/actions/review-gate/`, `.github/workflows/review-gate.yml`; kadet-hub/.github `tools/agent/`; the GitHub App `kadet-hub-agent` (name tbd), its installation, and the rulesets and CODEOWNERS of the repositories in AGT-3
Verified against: main @ 94fdda4; GitHub API state of kadet-hub on 2026-11-05; ossf/scorecard @ 61e84743356275f6ffca23b1b2f2cb945e19eb96

Related: [gate.md](gate.md) REV-1 (the `main` ruleset), REV-3 (branch
rulesets), REV-4 (`neat-bot`'s review) and REV-5 (Renovate's merges);
[marketplace.md](marketplace.md) RISK-1 and RISK-9.

## Problem

Coding agents, run by the maintainer, do most of the work in kadet-hub. They
create branches, commit as `Moep90` with a `Signed-off-by` line, open pull
requests and merge them with `gh pr merge --admin` once CI and the neat-bot
review pass. The last five commits on the registry's `main` all carry the
maintainer's sign-off, and every one is a squash commit that GitHub signed
(`web-flow`). Release tags in recipes are annotated and signed with the
maintainer's GPG key; `wordpress-v1.0.0` reports `verified=true`.

On GitHub the agent's work and the maintainer's own work are therefore the
same login. Nobody reading a pull request, the audit log or a Scorecard
result can tell what a person wrote from what an agent wrote and merged
unattended. The agent also holds everything the maintainer's token holds.
`gh auth status` in the maintainer's environment lists two keyring logins,
`Moep90` with scopes `admin:org`, `repo`, `workflow` and `write:gpg_key`,
and `neat-bot`. An agent process running as the same OS user can use both.

Scorecard's Code-Review check sees the maintainer as author and merger of
nearly every change. How the check treats a GitHub App is read from its
code in "Scorecard Code-Review" below.

## Decisions

- DEC-48: Agents act as a dedicated GitHub App, `kadet-hub-agent` (name
  tbd), installed on selected kadet-hub repositories with contents, pull
  requests and workflows write.

  An app gives each session a token that expires after an hour and covers
  only the repositories and permissions it was minted for. Actions done with
  it are attributed to the app. The existing apps stay as they are:
  `kadet-hub-kapitan-next` is scoped to the kapitan fork by DEC-27, and
  `kadet-hub-upstream` serves the generators upstream sync.

- DEC-49: The app merges its own pull requests through a bypass in
  `pull_request` mode on a ruleset that holds only the approval rule.
  Required checks, the review gate and code owner review live in a second
  ruleset the app cannot bypass.

  The maintainer is often offline, so a required human approval would stop
  agent work. Splitting the rulesets lets the app skip the one rule that
  needs a person and nothing else.

- DEC-50: Tags and releases stay a maintainer act, signed with the
  maintainer's GPG key in a maintainer session. The app gets no bypass on tag
  rulesets.

- DEC-51: Agent commits carry no `Signed-off-by`. The maintainer adds his
  own sign-off only to changes he reviewed.

- DEC-52: Agent sessions run as a separate OS user or in a rootless podman
  container that holds the app token and no other credential (AGT-5).

- DEC-53: `neat-bot`'s review is a real review. A pull request merges only
  after `neat-bot` approved its exact head commit, and the author fixes or
  answers every finding until it does (REV-4). For the app, the review gate
  of AGT-11 enforces this.

  The maintainer's approval is not required (DEC-49), so `neat-bot`'s
  approval is the review an agent change gets before it merges. A change
  request by the maintainer still stops the merge.

## App and permissions

GitHub's table of permissions required for GitHub Apps maps each action to
one repository permission. Metadata read is granted to every app and covers
the read endpoints the rest need.

| Action | Endpoint | Permission |
|---|---|---|
| Push a branch, commit through the API | `git push`, `POST /repos/{o}/{r}/git/refs`, `PUT .../contents/{path}` | Contents write |
| Push or change a file under `.github/workflows/` | same endpoints | Workflows write in addition to contents |
| Open a pull request, request a reviewer, post a review | `POST .../pulls`, `.../requested_reviewers`, `.../reviews` | Pull requests write |
| Merge a pull request | `PUT .../pulls/{n}/merge` | Contents write |
| Comment on a pull request | `POST .../issues/{n}/comments` | Issues write or pull requests write |
| Create a tag object or a release | `POST .../git/tags`, `POST .../releases` | Contents write (workflows write too when the release touches workflow files) |
| Open, label or close an issue | issues endpoints | Issues write |

An app can therefore create tags and releases with contents write alone. In
recipes and generators the `tag creation` ruleset admits only the admin
role, so the app's token would be refused there. In the other repositories
no ruleset restricts tags.

- AGT-1: Agent sessions that write to kadet-hub repositories MUST act as
  the app. They MUST NOT use the maintainer's or neat-bot's token.

  - Test: manual: inside a session `gh api user` fails with 403 and
    `gh api installation/repositories` lists the repositories of AGT-3;
    `gh pr view <n> --json author` of an agent pull request shows the app
  - Since: not implemented

- AGT-2: The app MUST hold exactly contents write, pull requests write,
  workflows write and metadata read. Issues write is added only if OQ-53
  says so.

  No administration, checks, statuses, actions, secrets or packages
  permission. Without checks and statuses the app cannot post a passing
  result for a required check itself. RISK-17 describes how a workflow it
  pushes still can, and OQ-60 asks whether workflows write stays.

  - Test: manual: `gh api orgs/kadet-hub/installations` shows these
    permissions for the app
  - Since: not implemented

- AGT-3: The app MUST be installed on selected repositories only:
  registry, recipes, generators, examples, renovate-config, .github,
  generator-template and backstage-plugins.

  kapitan is left out. Its `next` branch is built by DEC-27's app, and
  pull requests to kapicorp/kapitan come from the maintainer's personal
  fork, where a kadet-hub installation has no access. outreach is private
  and has no rulesets on the current plan. OQ-54 asks whether both stay out.

  - Test: manual: `gh api orgs/kadet-hub/installations` shows
    `repository_selection: selected`; the installation's repository list
    matches
  - Since: not implemented

## Authentication

An installation token comes from `POST /app/installations/{id}/access_tokens`,
authenticated with a JWT. The JWT is signed RS256 with the app's private key,
has `iat` set 60 seconds back, `exp` at most 10 minutes ahead and the client
ID or app ID as `iss`. The token expires after one hour. The request can name
`repositories` and a `permissions` subset, which the token then cannot
exceed.

`gh` has no command that mints app tokens. It does not need one. `gh` uses
`GH_TOKEN` ahead of stored credentials, and `gh auth git-credential`, the
git credential helper `gh auth setup-git` configures, returns
`username=x-access-token` with `GH_TOKEN` as the password. That was tested
with a dummy value. One exported variable therefore moves both `gh` and
`git push` to the app.

The maintainer mints the token when launching an agent session and passes
it as `GH_TOKEN`. kadet-hub/.github `tools/agent/mint-token` does that. It
reads the key with `op read` from 1Password straight into `openssl` through
a pipe, signs the JWT, looks up the installation on kadet-hub, asks for a
token limited to the repositories named on its command line and prints only
the token. The JWT reaches `curl` on standard input, never on a command line
another local user could read. GitHub's key guidance recommends a key vault
and rules out hard-coding. 1Password prompts the maintainer before the CLI
reads an item, so a read the maintainer did not start is visible.

The script runs with access to the key and lives in a repository the app
can write to through pull requests. kadet-hub/.github's CODEOWNERS
therefore names `tools/`, so a change to it needs the maintainer's approval
once that repository's `main protect` requires code owner review (AGT-10).

- AGT-4: The private key MUST NOT exist as a file. It MUST be read only
  through a store that asks the maintainer to approve the read. Tokens MUST
  be minted per session, limited to the repositories that session works on.

  - Test: kadet-hub/.github `tools/agent/test_mint_token.py` (with a
    throwaway key, a fake `op` and a local fake API: the request names the
    repositories, the JWT verifies, only the token reaches standard output,
    neither key nor JWT reaches any output or `curl`'s command line, nothing
    is written to the working or temporary directory, a run without
    repositories is refused); manual: no `*.private-key.pem` on the
    maintainer's machine, the 1Password item exists
  - Since: not implemented

- AGT-5: Agent sessions MUST run as a separate OS user or in a rootless
  container where the maintainer's and neat-bot's stored `gh` credentials,
  the keyring, an unlocked 1Password CLI session, the Vault token and the
  maintainer's SSH and GPG keys are not reachable. The app token in
  `GH_TOKEN` MUST be the only GitHub credential in the session.

  As long as the agent runs as the maintainer's OS user, `env -u GH_TOKEN
  gh auth token` returns the maintainer's token and `gh auth switch`
  reaches neat-bot. The identity split is then a convention the agent
  follows, and neat-bot's review in AGT-11 is one the agent could write
  itself. kadet-hub/.github `tools/agent/sessions.md` sets up both variants
  on Fedora and ends with the checks below.

  - Test: manual: inside a session `env -u GH_TOKEN gh auth status` reports
    no login, `gh api user` fails with 403, the maintainer's home directory
    is not readable, `ssh-add -l` reaches no agent, `gpg
    --list-secret-keys` lists nothing and no `VAULT_` variable is set
  - Since: not implemented

Sessions longer than one hour lose their token. OQ-56 asks whether to
restart the session or give it a credential helper that mints on demand
through the same approved key read.

## Commit identity and signing

The app's bot user has its own numeric ID. For the existing app,
`gh api 'users/kadet-hub-kapitan-next[bot]'` returns type `Bot` and an ID.
The commit email follows the form documented by
`actions/create-github-app-token`.

- AGT-6: Agent commits MUST use `kadet-hub-agent[bot]` as author and
  committer, with the email `<bot user id>+kadet-hub-agent[bot]@users.noreply.github.com`
  (ID tbd), and MUST NOT be signed with the maintainer's key.

  The session's own git configuration sets name and email. It holds no
  signing key and leaves `commit.gpgsign` unset, unlike the maintainer's
  configuration, which signs every commit. A bot commit signed with the
  maintainer's key would mix the two identities and show as unverified.

  - Test: manual: `git log -1 --format='%an <%ae> %G?'` on an agent branch
    shows the bot and `N`
  - Since: not implemented

Locally made bot commits are unsigned. GitHub verifies a GPG or SSH
signature against a key added to an account, and a bot user is not an
account that keys can be added to. The kapitan fork shows the result: its
last 30 commits, pushed with git by `github-actions[bot]`, all report
`unsigned`. GitHub signs a bot's commit only when it is created through the
API, authenticated as the app, with no custom author, committer or
signature (the GraphQL `createCommitOnBranch` mutation, for example).

No ruleset in kadet-hub has the `required_signatures` rule. Every repository
allows squash merges, and the registry's `main` consists of squash commits
GitHub signed. `main` stays fully verified with unsigned agent branch
commits. If signed commits are ever required, GitHub's ruleset docs say
unsigned head-branch commits can block a squash merge even though the squash
commit would be signed. Agents would then have to commit through the API.
Nothing here requires that today.

- AGT-7: Tags and releases MUST be created by the maintainer, signed with the
  maintainer's GPG key. The app MUST NOT be a bypass actor on a tag ruleset.

  A release publishes to consumers, which is a maintainer decision (DEC-3
  for entry bumps). The signed tag is the maintainer's statement that this
  commit is the release. An app tag would be signed by GitHub at best, which
  says only that the app made it. In repositories without a tag ruleset the
  app can still create tags technically; OQ-57 asks whether those
  repositories get one.

  - Test: manual: `gh api repos/kadet-hub/{recipes,generators}/rulesets`
    lists no app on `tag creation`; the latest release tag reports
    `verified=true` with the maintainer as tagger
  - Since: not implemented

## Sign-off

No kadet-hub spec, CONTRIBUTING.md or the org's `.github` repository requires
a Developer Certificate of Origin, and no DCO app is installed in the org
(installed: Renovate, `kadet-hub-upstream`, `kadet-hub-kapitan-next`). The
sign-off on today's commits is a habit.

DCO 1.1 is a person's certification: "By making a contribution to this
project, I certify that" the contribution is the signer's own, or based on
correctly licensed work, or passed on unmodified. An app cannot certify
that. The Linux kernel's rules for coding assistants say "AI agents MUST NOT
add Signed-off-by tags. Only humans can legally certify the Developer
Certificate of Origin (DCO)" and make the human submitter responsible for
reviewing the code and adding their own sign-off.

A maintainer sign-off on an agent commit that merged without his review
would certify license provenance nobody checked.

- AGT-8: Agent commits MUST NOT carry a `Signed-off-by` trailer. A
  maintainer MAY add his own when he reviewed the change.

  Pull requests to projects that require a DCO, such as upstream Kapitan
  if it does, stay with the maintainer's identity and his sign-off after
  review.

  - Test: manual: `git log --format='%(trailers:key=Signed-off-by)'` over
    agent-authored commits on `main` is empty
  - Since: not implemented

## Branches, merge and the review gate

The relevant rulesets today:

| Repository | `branches` (all refs except `main`, `renovate/**`) | `main` |
|---|---|---|
| registry | admin only | 1 approval, last push approval, code owners, checks `gate` and `renders` strict; bypass admin and Renovate, `pull_request` mode |
| recipes | admin only | 1 approval, last push approval, checks; bypass admin and Renovate, `pull_request` mode |
| generators | admin only | 1 approval, last push approval, checks; bypass admin, `pull_request` mode |
| examples, renovate-config, generator-template | none | 0 approvals, checks; bypass admin, `pull_request` mode |
| .github | none | 0 approvals; bypass admin, `pull_request` mode |
| backstage-plugins | none | none |

Only the registry has a CODEOWNERS file. neat-bot has read access, so its
approval counts toward no ruleset approval (REV-4). GitHub requires
approvals from reviewers with write permission.

GitHub defines `pull_request` bypass as: the actor must open a pull request
and "can then choose to bypass any branch protections and merge that pull
request". A bypass covers every rule of the ruleset it is granted on.
Rules from several rulesets on one branch "are aggregated" and the most
restrictive applies. GitHub's docs do not say how a bypass on one ruleset
interacts with a rule in another; OQ-58 has that tested before rollout.

- AGT-9: The app MUST push only branches under `agent/`.

  The `branches` ruleset excludes `refs/heads/agent/**/*` the way it
  excludes `renovate/**`. A new `agent branches` ruleset restricts creation,
  update and deletion there to the admin role and the app, both `always`.

  - Test: manual: `gh api repos/kadet-hub/<repo>/rulesets` matches; a push
    by the app to a branch outside `agent/` is refused
  - Since: not implemented

- AGT-10: In each repository of AGT-3, `main` MUST be protected by two
  rulesets. `main review` holds the pull request rule with one approval and
  last push approval, with the app as bypass actor in `pull_request` mode.
  `main protect` holds deletion, non-fast-forward, the required checks
  including `review-gate` (AGT-11), and code owner review, without the app
  as bypass actor.

  Admin and Renovate keep their bypass on both, as today. In the registry,
  `main protect` carries the pull request rule with zero approvals and code
  owner review, so an agent change to `.github/`, `policy/`, `gate/`, `scan/`
  or `sandbox/` still needs the maintainer. The other repositories get a
  CODEOWNERS file naming at least `.github/`; kadet-hub/.github also names
  `tools/` (AGT-4). Without it, an agent pull request could change the
  workflow that computes AGT-11 and merge on the result.

  - Test: manual: rulesets match; an agent pull request with a failing
    required check cannot be merged by the app with `--admin`; one touching
    `.github/` cannot be merged without the maintainer's approval
  - Since: not implemented

- AGT-11: The check `review-gate` MUST fail on a pull request until
  neat-bot's latest review approves the pull request's head commit and no
  user with write access has an open change request. Pull requests opened
  by Renovate MUST pass it.

  This is how DEC-53 becomes a rule the app cannot skip. A ruleset can only
  require an approval from someone with write access; it cannot require
  neat-bot's, and it cannot wait for a maintainer who might come back. With
  this check required in `main protect`, the app merges only after
  neat-bot approved the exact head, and a change request from the
  maintainer stops it until he approves or dismisses it. The maintainer
  keeps the admin bypass, so on his own pull requests the check shows
  REV-4's state without enforcing it. Renovate merges only once every
  check passed (REV-5), and the check cannot tell which of its pull
  requests Renovate will merge itself, so all of them pass.

  neat-bot's latest review counts with comments included: an approval
  followed by a comment review with a new finding fails again. A change
  request is open while the reviewer's latest approval, change request or
  dismissal is a change request; a later comment does not close it, as on
  GitHub. Write access is `admin` or `write` in the collaborator permission
  API, which maps maintain to write.

  The workflow runs on `pull_request` (opened, synchronize, reopened) and on
  `pull_request_review` (submitted, dismissed), so a push turns the check
  red until neat-bot approves the new head. Each run judges the head commit
  of its event, which is the commit its check attaches to, and a newer run
  cancels an older one of the same pull request. Both events give a fork a
  read-only token. The action reads reviews through the API and checks out
  nothing; in the registry the workflow loads it with `$/` from the commit
  it runs on.

  Like every `pull_request` workflow, this one comes from the pull
  request's merge commit, so a pull request can change the check that
  judges it. AGT-10's code owner rule on `.github/` stops that.

  - Test: `.github/actions/review-gate/test_review_gate.py` against
    `fixtures.json`: approval of the head passes; a comment review with
    findings, an approval followed by a comment review, an approval of an
    older commit, a maintainer's change request (also after his later
    comment), no review, and a maintainer pull request without a review
    fail; a dismissed change request, a change request followed by the
    same reviewer's approval, a change request without write access and a
    Renovate pull request pass; run by `workflow-lint`. manual: AC-46
  - Since: this change

- AGT-12: The app MUST NOT submit `APPROVE` reviews.

  Pull requests write lets it, and Scorecard would count an app approval
  of a maintainer pull request as a review by someone other than the
  author. Whether an app approval satisfies a ruleset approval was not
  verified (OQ-59). The rule lives in the agents' instructions.

  - Test: manual: `gh search prs --reviewed-by 'app/kadet-hub-agent'` with
    state approved returns nothing
  - Since: not implemented

## Scorecard Code-Review

Read in `clients/githubrepo/graphql.go`, `checks/raw/code_review.go` and
`probes/codeApproved/impl.go` at the pinned commit; the local copies match
the commit byte for byte.

A pull request's author is a bot when its resource path starts with
`/apps/`, so every app-authored pull request is a bot changeset. A
changeset is approved when any `APPROVED` review comes from a login other
than the author, or when the merger is not the author. The probe then
skips every approved bot changeset entirely ("skip bot authored changesets,
which can skew single maintainer projects", scorecard issue 2450). If no
human changeset is left, the check is inconclusive, and the aggregate score
skips inconclusive checks.

| Agent pull request | Code-Review sees |
|---|---|
| neat-bot `APPROVE`, app merges (this spec) | approved bot changeset, skipped |
| neat-bot `COMMENT`, app merges | unapproved bot changeset, counted as unreviewed |
| maintainer approves, app or maintainer merges | approved bot changeset, skipped |
| no approval, maintainer merges | merger is not author, approved, skipped |

So a maintainer review of an agent pull request never raises the score. It
removes the change from the count. An agent identity merged by the
maintainer counts as an implicit review only for a machine user, not for
an app.

With DEC-53 every agent pull request merges with neat-bot's approval, so
Scorecard skips all of them. Code-Review is then computed over the other
pull requests only, and turns inconclusive, which drops it from the
aggregate score, when none of them is among the last 30 changesets. The
check's documentation says reviews by bots do not count as code review.
neat-bot's approvals of agent pull requests add no reviewed changeset, but
they remove agent changes from the count, where a comment-only review would
leave them counted as unreviewed.

## Risks

- RISK-15: A leaked app key mints tokens for every repository of AGT-3 with
  every permission of AGT-2 until the key is deleted.

  Contents write lets the holder push `agent/` branches, open pull requests
  and merge them through the `main review` bypass, but not past `main
  protect` (AGT-10), and create tags and releases in repositories without a
  tag ruleset. Workflows write lets it push a workflow to an `agent/`
  branch. That workflow runs on push with a `GITHUB_TOKEN` it can declare
  write permissions for, and reads repository secrets not bound to an
  environment: generators has two, renovate-config one, the others none
  (counting unit: repository-level Actions secret; the org has none). It
  cannot pass the registry's release identity, which `consumer/run` and
  `release.yml` pin to `release.yml@refs/heads/main`. Whether such a token
  can push to `ghcr.io/kadet-hub` was not checked. Pull requests write lets
  it approve maintainer pull requests (AGT-12). This is the class RISK-9
  already describes for Renovate, which holds more permissions on every
  repository. The difference is where the key lives: on the maintainer's
  machine instead of at Mend.

  Rotation is generate, then delete: an app can hold up to 25 keys and the
  last one cannot be deleted before a new one exists. The new key goes into
  the 1Password item, then the old one is deleted on GitHub. GitHub's docs
  do not say whether tokens minted with a deleted key stay valid. They
  expire within an hour either way. Suspending the installation stops the
  app at once.

- RISK-16: Until AGT-5 holds, an agent session can act as the maintainer or
  as neat-bot. That makes neat-bot's review in AGT-11 something the agent
  could produce itself, and every authorship statement on GitHub a claim the
  agent's instructions keep, not a control.

- RISK-17: With workflows write, an agent session needs no leaked key to
  forge a passing `review-gate`. It pushes a workflow to one `agent/`
  branch that runs on push, declares `checks: write` and creates a check
  run named `review-gate` with conclusion success on the head commit of
  another agent pull request. GitHub Actions creates that check run, which
  is the source a ruleset expects, and the other pull request changes
  nothing under `.github/`, so AGT-10's code owner rule does not apply to
  it. The branch carrying the workflow never needs to merge. The same works
  for `gate` and `renders`, whose GI-5 protection covers forks only.

  Whether a ruleset then takes the forged run or the failing one of the
  same name was not tested. No existing registry workflow declares checks
  or statuses write, and the repository's default workflow token is read
  only, so the forgery needs a workflow file the app pushes. OQ-60 asks
  whether the app keeps workflows write.

## Verification

- AC-46 (AGT-1, AGT-5, AGT-6, AGT-8, AGT-10, AGT-11): an agent pull request
  in the registry is authored and merged by the app, its commits carry the
  bot identity without sign-off, the `review-gate` check failed before
  neat-bot's approval and passed after it, and a session cannot reach the
  maintainer's token. Check: manual: the first agent pull request after the
  rollout.

## Alternatives

| Option | For | Against |
|---|---|---|
| Keep the maintainer's token | Nothing to set up | Agent and person indistinguishable; agent holds `admin:org` |
| Machine user with a fine-grained PAT | Scorecard counts it as human, so a maintainer approval of its pull request raises Code-Review honestly | Long-lived token instead of one-hour tokens; a second account to secure; needs a seat in the org; no per-session down-scoping |
| Reuse `kadet-hub-kapitan-next` or `kadet-hub-upstream` | No new app | Widens DEC-27's single-repository scope; mixes pipeline and agent actions under one name |
| App with `always` bypass on `main` | Fewer rulesets | Direct pushes to `main` without checks |
| App without any bypass on `main` | Every agent change gets a human approval | Merges stop while the maintainer is away; Scorecard still skips these changes |
| Agents run in GitHub Actions with `actions/create-github-app-token` | Key never on the workstation | The agents are local Claude Code sessions; the key moves into an Actions secret instead |
| Agents commit through the API (`createCommitOnBranch`) | Branch commits verified | Needs tooling around every commit; no rule requires signed branch commits |
| Agent sessions as the maintainer's OS user | No second user or container | The maintainer's and neat-bot's logins stay one command away (AGT-5) |
| Review gate as a `pull_request_target` workflow | Its definition comes from `main`, so a pull request cannot change it | No `pull_request_review` counterpart exists, so the check would not run again when neat-bot or the maintainer reviews |
| Review gate as a reusable workflow | Callers need no job definition | It needs the decision script from the registry too, through a checkout or a composite action |

## Open questions

- OQ-53: Do agents need issues write, for opening and closing issues or
  updating status issues? Closing an issue with `Closes #n` in a merged pull
  request does not need it.
- OQ-54: Should kapitan or outreach get the app? kapitan would first need
  the `always` bypass of Integration 5438785 on its `next` ruleset
  reviewed.
- OQ-56: Sessions longer than an hour: restart with a new token, or an
  on-demand credential helper behind the 1Password approval?
- OQ-57: Should registry, examples and the other repositories without one
  get a `tag creation` ruleset like recipes?
- OQ-58: Does a `pull_request` bypass on `main review` leave `main protect`
  enforced for the app? GitHub's docs leave it open. Test on `examples`: an
  app pull request with a failing required check and one touching
  `.github/` must both be unmergeable by the app. The same test shows
  whether a `review-gate` run that passed after a failed one on the same
  head commit satisfies the required check.
- OQ-59: Does an approval by a GitHub App count toward a ruleset's required
  approvals? Not verified. It decides how much AGT-12 matters beyond
  Scorecard.
- OQ-60: Should the app drop workflows write (AGT-2)? Without it the app
  cannot push a commit that adds or changes a workflow, which closes
  RISK-17 in the registry. Agent changes to workflows would then reach
  GitHub through the maintainer. Proposed: yes, decided before the app is
  created.

## Implementation inventory

| Path or setting | Requirement |
|---|---|
| GitHub App `kadet-hub-agent` (tbd): permissions, installation | AGT-1, AGT-2, AGT-3 |
| 1Password item with the private key | AGT-4 |
| kadet-hub/.github `tools/agent/mint-token`, `tools/agent/test_mint_token.py` | AGT-4 |
| kadet-hub/.github `tools/agent/sessions.md`: the agent OS user or container | AGT-5, AGT-6 |
| Agent instructions (Claude Code agents and skills) | AGT-6, AGT-7, AGT-8, AGT-9, AGT-12 |
| Rulesets `branches`, `agent branches`, `main review`, `main protect` in the repositories of AGT-3 | AGT-9, AGT-10 |
| `.github/CODEOWNERS` in every repository of AGT-3 except the registry | AGT-10 |
| `.github/actions/review-gate/`: `action.yml`, `review_gate.py`, `test_review_gate.py`, `fixtures.json` | AGT-11 |
| `.github/workflows/review-gate.yml` in every repository of AGT-3; outside the registry it uses the action pinned by commit SHA | AGT-11 |
