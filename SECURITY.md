# Security

Report a vulnerability in the marketplace itself (the gate, the sandbox, the
release workflow, a way to get unreviewed code to consumers) privately through
[GitHub private vulnerability reporting](https://github.com/kadet-hub/registry/security/advisories/new).
Do not open a public issue for it. Without a GitHub account, write to
security@kadet-hub.org.

A listed generator that behaves maliciously is reported the same way. A
confirmed malicious version is yanked, its artifact deleted and an advisory
published ([docs/incident.md](docs/incident.md), INC-1). The marketplace has one
maintainer, so the 24-hour target is best effort.

For vulnerabilities in a generator's own code that are not malicious, contact
the generator's repository first.

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
