# Adding a generator

A generator is listed by a pull request that adds `generators/<name>.yaml`
to this repository. The gate checks the tagged source, a maintainer reviews
it, and after the merge the release workflow publishes the checked tree as
`ghcr.io/kadet-hub/<name>` and lists it on [kadet-hub.org](https://kadet-hub.org).
The fields of the manifest and the entry are defined under
[Registration](specs/marketplace.md#registration).

## In your repository

The generator lives in a public repository on github.com or gitlab.com, in
its own directory or at the root. That directory carries:

- `kapitan-generator.yaml`, the manifest. `owners` are GitHub numeric user
  IDs (`gh api users/<login> --jq .id`). Every program the generator starts
  is declared in `binaries`, every chart it renders in `charts` with the
  sha256 of the `.tgz`; `dependencies` stays empty.
- a fixture project, the directory named in `fixtures`: an ordinary Kapitan
  project whose compile entries load the generator from `lib/<name>`, where
  the gate places it.
- `README.md` with an inventory example, `CHANGELOG.md` with an entry for
  the version, and `LICENSE` here or at the repository root.

Tag the commit with a semver, optionally prefixed for repositories with
several generators (`v1.4.0`, `argocd-v1.4.0`).

## The pull request

```yaml
# generators/<name>.yaml
source:
  repo: https://github.com/<owner>/<repo>.git
  path: <generator dir>   # "." at the root
  tag: v1.4.0
  sha: <git rev-parse v1.4.0^{commit}>
owners: [<GitHub user ID>, ...]
```

The pull request changes only this file, is opened by one of the
manifest's owners, and lists the same owners as the manifest at `sha`.

The gate fetches the tree at `sha` without running it, scans it for
secrets, malware and dangerous code, and compiles the fixture project in a
gVisor sandbox without network, with decoy credentials and a syscall trace.
A program not declared in `binaries`, a read of a decoy or a network attempt
fails the gate. The gate posts its result as a comment; a maintainer reviews
the code and merges. Which checks are implemented is recorded per
requirement in the [spec](specs/marketplace.md).

## New versions and yanking

Renovate opens a pull request when you push a newer tag with the same
prefix; the gate and the review run again on the new commit. You can also
open the bump yourself. The version must increase, and `repo` and `path`
stay fixed.

To withdraw a version, add it under `yanked` with a reason. The catalog
then shows the reason instead of the inventory entry. A version that is
malicious is reported as described in [SECURITY.md](../SECURITY.md).
