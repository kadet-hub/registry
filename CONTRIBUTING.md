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

## Running the tests

The tests are Python `unittest` suites and shell selftests; CI runs the same
commands (`.github/workflows/`). On Linux with Python 3 and Hugo (the version
in `.github/actions/setup-hugo`):

```sh
python3 -m unittest discover -s catalog      # catalog site, SEO and legal checks
python3 -m unittest discover -s release      # release build and index
```

The gate, scanner and consumer tests need the sandbox image, which pins
Kapitan and the scanners:

```sh
docker build -t kadet-hub/sandbox sandbox
docker run --rm --network none -v "$PWD:/repo:ro" -w /repo/gate kadet-hub/sandbox \
  python -m unittest discover -p 'test_check*.py'
docker run --rm --network none -v "$PWD:/repo:ro" -w /repo/consumer kadet-hub/sandbox \
  python -m unittest discover
tests/selftest            # every gate sample, needs gVisor (runsc), and kind, kubectl, uv and cloud-provider-kind for the recipe samples
tests/consumer-selftest   # the consumer workflow against its samples
tests/workflow-policy     # pinned actions and permissions
```

The recipe sample `pass-recipe-gateway-api` runs cloud-provider-kind, which
manages every kind cluster on the Docker host, so run the selftest where no
other kind cluster runs.

A new requirement or a changed behaviour comes with a test that fails without
the change, named in the requirement's `Test:` line.
