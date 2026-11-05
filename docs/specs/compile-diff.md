# Kapitan generator marketplace: Compile diff

Status: Draft
Code: `.github/actions/compile-diff/`, `.github/actions/compile-diff-comment/`, `consumer/compile_diff.py`, `consumer/test_compile_diff.py`, `docs/consumers.md` (Compile diff)
Verified against: main @ a82f7e2

Related: [consumers.md](consumers.md) holds the consumer flow that compiles
each side (CON-1 to CON-5); [marketplace.md](marketplace.md) holds the
threat model.

## Problem

A one-line change to a class or a generator pin can rewrite manifests in
every target that includes the class. The reviewer of the pull request sees
the inventory change, not what it does to `compiled/`. The consumer
workflow (CON-1) uploads the output of one commit as an artifact, and
comparing two of them is manual work, so inventory changes get approved
without anyone looking at what they render.

Two composite actions close that gap. `compile-diff` compiles the base and
the merge commit of a pull request through the consumer flow and uploads
the difference of `compiled/` per target. `compile-diff-comment`, started by
`workflow_run` in a second workflow, posts it as one comment on the pull
request and edits that comment on every later push.

## Decisions

- DEC-31: Both actions live in this repository under `.github/actions/`,
  next to the consumer flow they run. A consumer pins both at the same
  commit SHA of `main` and names the release tag of that commit in a
  comment:

  ```yaml
  uses: kadet-hub/registry/.github/actions/compile-diff@<sha> # index-<serial>
  ```

  The compile action runs `consumer/run` and the sandbox image of its own
  commit, and the comment action reads the artifact the compile action of
  the same commit wrote. Every release run tags its commit `index-<serial>`
  (PUB-12), so the tag tells a reviewer which release the pin is at. The
  SHA decides what runs, because organization owners can move tags.

- DEC-32: Each side compiles through `consumer/run` (CON-1 to CON-5) with
  its own `.kapitan-sandbox.yaml`. The actions take no Kapitan version or
  image: the image is the sandbox image of the action's commit, found by
  its `sandbox/` tree and verified by attestation (PUB-6), and Kapitan is
  the version `sandbox/Dockerfile` pins. A consumer moves Kapitan by moving
  the action pin. Dependencies are fetched as CON-1 and CON-4 fetch them: by
  digest, verified against the attested index, recipes from the fetch
  inventory, never with `--fetch`.

- DEC-33: The diff compares the merge commit GitHub builds for the pull
  request (`github.sha` on `pull_request`) with its first parent,
  `pull_request.base.sha`, so it shows what merging changes in `compiled/`.
  When the base has no `.kapitan-sandbox.yaml` in the working directory,
  the base output is empty and every file counts as added; the pull request
  that adds a project gets a diff as well.

- DEC-34: Neither side compiles with `--reveal` (CD-2).

- DEC-35: Pull requests from forks get the comment through two workflows. A
  compile workflow on `pull_request` with read permissions uploads the diff
  as an artifact. A comment workflow on `workflow_run` holds
  `pull-requests: write`, downloads the artifact and posts it without
  checking out or running anything from the pull request.

- DEC-36: The comment shows a summary line and one collapsed `<details>`
  block per changed target with its changed files and their unified diff.
  Each block is cut to its share of GitHub's limit of 65536 characters per
  comment; the artifact `compile-diff` keeps the full diff.

## Compile

`compile-diff` takes two inputs:

| Input | Default | Meaning |
|---|---|---|
| `working-directory` | `.` | Kapitan project inside the repository, holding `.kapitan-sandbox.yaml` |
| `targets` | `*` | Glob over target names; only matching targets are diffed |

It checks out the base and the merge commit without credentials, installs
gVisor and oras with the setup actions of its own commit (`$/`), runs
`consumer/run` on each side and writes one `<target>.diff` per changed
target. The output `path` names that directory, which is also uploaded as
the artifact `compile-diff`.

Both sides compile every target, because `consumer/run` runs Kapitan with
fixed flags (CON-1); `targets` filters the diff. The action fails outside
`pull_request` and when `working-directory` leaves the checkout.

- CD-1: `compile-diff` MUST compile the base and the merge commit of the
  pull request with `consumer/run` and MUST fail when either compile fails.

  A failed CON check on either side ends the run without an artifact, so
  the comment reports a failed run instead of a diff that looks clean.

  - Test: manual: AC-15
  - Since: #537

- CD-2: Neither compile MAY use `--reveal`.

  Without it, compiled output holds ref tags such as
  `?{gpg:db/password:3f2a8c1e}` instead of secret values, so the diff, the
  comment and the artifact hold no revealed secret. The tag carries a short
  hash of the stored ref. Changing a ref therefore changes the tag, and the
  diff shows that line like any other: the reviewer learns that a secret
  changed, not its value.

  - Test: `consumer/test_compile_diff.py` (`NoReveal`)
  - Since: #537

- CD-3: The diff MUST list, for every target whose name matches `targets`
  and whose files under `compiled/<target>` differ, each added, removed and
  changed file, with a unified diff of three context lines for text files
  and one line for a binary file. Symbolic links MUST NOT be followed.

  A file that is not UTF-8 or holds a NUL byte counts as binary. A symbolic
  link is compared by the path it points to. The SEC-10 trace already fails
  a compile that creates one; the diff does not rely on that.

  - Test: `consumer/test_compile_diff.py` (`Diff`)
  - Since: #537

## Pull requests from forks

On `pull_request`, a workflow from a fork gets a read-only `GITHUB_TOKEN`
and no secrets, whatever its `permissions` key asks for, so it cannot
comment. `pull_request_target` has a write token and the secrets of the
base repository; a job there that checks out and compiles the pull request
runs the fork's resolvers, generators and templates next to that token.

The two workflows split the two. The compile workflow runs the pull
request's content with read permissions only. The comment workflow holds
the write permission and runs nothing from the pull request: GitHub takes
its definition from the default branch, its action comes from the pinned
SHA, and the artifact is its only input from the pull request.

A fork can change the compile workflow in its pull request and upload any
artifact under the expected name, so the comment action treats the
artifact as hostile text. It reads only regular files named
`<target>.diff`, at most 1 MiB of each, and renders them as CD-7 says.

The pull request number does not come from the artifact. `workflow_run`
lists no pull requests for a run from a fork, so the comment action asks
the API for the open pull requests from the run's head owner and branch and
keeps the one whose head SHA is the run's head SHA. When the branch has
moved on, none matches and nothing is posted; the run for the newer head
posts. That also keeps a slow run from overwriting the comment of a newer
one.

- CD-4: The compile workflow in `docs/consumers.md` MUST run on
  `pull_request` and hold only `contents: read`, `packages: read` and
  `attestations: read`.

  `packages: read` pulls the sandbox image and the fetched artifacts;
  `attestations: read` serves `gh attestation verify` (CON-2).

  - Test: none (partial: AC-15 runs the documented workflow)
  - Since: #537

- CD-5: `compile-diff-comment` MUST fail unless it runs on `workflow_run`
  for a `pull_request` run, MUST NOT check out the repository and MUST NOT
  execute artifact content. The comment workflow in `docs/consumers.md` MUST
  hold only `pull-requests: write` and `actions: read`.

  `actions: read` lets `actions/download-artifact` read the other run.

  - Test: none (partial: AC-16 posts a forged artifact as text; the
    permissions are reviewed)
  - Since: #537

- CD-6: `compile-diff-comment` MUST post only to the one open pull request
  whose head owner, branch and head SHA equal the run's, and MUST post
  nothing when none or more than one matches.

  - Test: manual: AC-15 (re-run of a left head), AC-16
  - Since: #537

- CD-7: The comment MUST render artifact content only inside code fences
  longer than any backtick run in it, with every character outside
  printable ASCII, tab and newline replaced by `?`, and target names
  outside `[A-Za-z0-9._-]` replaced the same way.

  The gate comment renders its report the same way (REV-2). Inside the
  fence, Markdown, HTML, links and mentions stay text. Replacing non-ASCII
  characters also removes bidirectional control characters, which can make
  a rendered line read differently from the file. A diff of UTF-8 text
  shows `?` where the file has a non-ASCII character; the artifact keeps
  the bytes.

  - Test: `consumer/test_compile_diff.py` (`Render`)
  - Since: #537

## Comment

```markdown
<!-- kadet-hub-compile-diff -->
**compile diff: 1 target changed, 1 file** at `3f0c2a1`. Full diff: artifact `compile-diff` of the [run](<run url>).

<details><summary>dev: 1 file</summary>

~~~diff
M dev/apps/web.yml

diff --git a/dev/apps/web.yml b/dev/apps/web.yml
--- a/dev/apps/web.yml
+++ b/dev/apps/web.yml
@@ -40,7 +40,7 @@
...
-  replicas: 1
+  replicas: 2
~~~

</details>
```

The file list marks each file `A`dded, `D`eleted or `M`odified and comes
before the diff, so it survives a cut. The comment action edits the first
comment by `github-actions[bot]` that starts with the marker, or creates
one. A run that did not succeed gets a one-line comment with its
conclusion and link; a run without changes says so.

A repository gets one compile diff comment per pull request. Two projects
in one repository would overwrite each other's comment, and two uploads of
`compile-diff` in one run fail, so each project needs its own repository,
as the consumer workflow already requires.

- CD-8: `compile-diff-comment` MUST keep one comment per pull request and
  edit it on every run that matches the pull request (CD-6).

  - Test: manual: AC-15
  - Since: #537

- CD-9: The comment MUST start with a summary line naming the number of
  changed targets and files, follow with one `<details>` block per changed
  target, and MUST NOT exceed 65536 characters.

  The targets split what the summary leaves of the limit, smallest diff
  first: each gets an equal share of what is left, so what a small target
  does not use goes to the larger ones. A block that does not fit is cut at
  a line boundary and ends with a note naming the lines shown and the
  artifact. When a share would drop below 300 characters, the remaining
  targets, the largest, are counted in one line instead.

  - Test: `consumer/test_compile_diff.py` (`Render`); manual: AC-15
  - Since: #537

## Verification

- AC-15 (CD-1, CD-3, CD-4, CD-8, CD-9): in a repository whose default
  branch holds both documented workflows, a pull request that changes a
  replica count gets one comment whose diff holds the changed `replicas:`
  line, and a second push edits the same comment with the new diff. Check:
  manual: scratch repository run, with a step of its comment workflow that
  reads the comment back.

  Run on 2026-11-05 in a private scratch repository holding
  `first-platform` of kadet-hub/examples and both workflows pinned to #537.
  The pull request raising dev's replicas from 1 to 2 got one comment with
  `-  replicas: 1` and `+  replicas: 2` in `dev/apps/shop/web-deploy.yml`.
  A second push raising prod's from 3 to 4 edited the same comment to two
  targets, and the read-back step passed on both runs. A re-run of the
  first compile run, whose head the pull request had left, posted nothing.
- AC-16 (CD-5, CD-6, CD-7): a pull request whose compile workflow uploads a
  forged artifact (a mention, HTML, a backtick run, bidirectional control
  characters, a target name with markup, a diff above the limit) gets a
  comment with all of it inside fences, and no other pull request gets a
  comment. Check: manual: scratch repository run (partial: no pull request
  from a real fork, whose read-only token GitHub sets).

  Run on 2026-11-05 in the AC-15 repository, last at fa761d9. The forged
  artifact got a comment of 65412 characters whose rendered HTML holds no
  image, heading or mention; its only link is the run link, and the large
  target was cut after 717 of 3005 lines. The target name
  `x[y](z) @ghost &amp;` rendered as `x?y??z???ghost??amp?`, the run of 7
  backticks sat inside a fence of 8, bidirectional controls and non-ASCII
  letters became `?`, and the extra files `pr.txt` and `notes.md` were
  ignored. The comment of the other open pull request stayed unchanged.

## Alternatives

| Option | Not chosen because |
|---|---|
| `pull_request_target` that checks out and compiles the head | Runs pull request content next to a write token and the base repository's secrets |
| Kapitan image input pinned by digest, compiled outside the sandbox | Skips the attestation of PUB-6, the sandbox of SEC-9 and the fetch checks of CON-1; `sandbox/run` needs the sandbox image |
| Diff the head commit against `pull_request.base.sha` | Shows commits that reached the base after the branch point as reverted |
| Render the comment in the compile job | A fork controls that job, so the comment job would post the fork's Markdown |
| `.github/actions/compile-diff/comment/` | GI-2a and the Renovate managers match `.github/actions/*/action.yml` only |

## Open questions

- OQ-17: Does Renovate's github-actions manager update a pin with the
  comment `# index-<serial>`? Not tested. kadet-hub/renovate-config moves
  `kubernetes-versions-*` tags with a regex versioning and could match
  `index-<serial>` the same way.

## Implementation inventory

| Path | Content |
|---|---|
| `.github/actions/compile-diff/action.yml` | CD-1 to CD-3: checkouts, setup actions, `consumer/run` per side, diff, upload |
| `.github/actions/compile-diff-comment/action.yml` | CD-5 to CD-9: download, pull request lookup, render, post or edit |
| `consumer/compile_diff.py` | `diff` (CD-3) and `render` (CD-7, CD-9) |
| `consumer/test_compile_diff.py` | Unit tests, run by `consumer-selftest` |
| `docs/consumers.md` | The two consumer workflows (CD-4, CD-5) |
