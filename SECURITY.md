# Security

Report a vulnerability in the marketplace itself (the gate, the sandbox, the
release workflow, a way to get unreviewed code to consumers) privately through
[GitHub private vulnerability reporting](https://github.com/kadet-hub/registry/security/advisories/new)
or to security@kadet-hub.org. Do not open a public issue for it.

The marketplace has one maintainer. Reports are handled best effort, with
no SLA and no promised response time.

## Supported versions

The registry does not release its code. Its `index-<serial>` releases
publish the generator index, not the gate or the workflows. Only `main` is
supported. If you pin the consumer workflow or `sandbox/gitlab-ci.yml` to a
commit, move the pin past the fix.

For a listed generator, only its newest version that the index does not
mark yanked is supported; the catalog shows it as the latest version. A fix
is listed as a newer version, never as a change to an older one.

## Advisories

A vulnerability fixed in the registry gets a GitHub security advisory
(GHSA) in this repository. It names the affected versions, for the registry
the `main` commits before the fix, and a CVSS score.

## Listed generators

A listed generator that behaves maliciously is reported the same way as a
vulnerability in the marketplace. A confirmed malicious version is yanked,
its artifact deleted and an advisory published
([docs/incident.md](docs/incident.md), INC-1).

Other vulnerabilities in a generator's code go to the generator's
repository, as its `SECURITY.md` describes. The gate requires that file
for every new generator and version (REG-10).

## Removal requests

To request removal of a listed generator or of content on kadet-hub.org
because it infringes your rights (copyright, license, trademark) or is
unlawful, open a [report](https://github.com/kadet-hub/registry/issues/new?template=generator-report.yml)
and choose "License, copyright or trademark concern". Name the generator and
version, the content concerned and why it is infringing or unlawful. If the
request cannot be public, send it to abuse@kadet-hub.org. The maintainers
check each request, tell you and the generator's owners their decision and
its reason, and yank or remove the content when the request is justified
(LEG-3, [TERMS.md](TERMS.md#review-and-removal)).
