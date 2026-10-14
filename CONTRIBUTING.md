# Contributing

kadet-hub has three kinds of contribution, each with its own path.

**List a generator.** Start from the
[generator template](https://github.com/kadet-hub/generator-template), then
add an entry file under `generators/` in a pull request. The gate checks the
version and posts its report on the pull request; a maintainer reviews it.
[docs/authors.md](docs/authors.md) covers the manifest, the checks and how
to run them locally. Opening the pull request accepts the
[terms of listing](TERMS.md).

**Request a generator or report a problem.** Use the issue forms for a new
generator or a problem with a listed one.
Vulnerabilities in the gate, the sandbox or the release workflow go through
private reporting as described in [SECURITY.md](SECURITY.md), not a public
issue.

**Change the registry itself.** A change to code, configuration or CI starts
by editing the spec it touches, in the same pull request, as its first
commit; [docs/specs/README.md](docs/specs/README.md) describes the format.
Each requirement names the test that checks it. Use Conventional Commits.
CI runs the catalog tests, the gate
self-test and the workflow linters on every pull request.

Questions that are neither go to
[Discussions](https://github.com/kadet-hub/registry/discussions).
