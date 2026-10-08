# Security

Report a vulnerability in the marketplace itself (the gate, the sandbox, the
release workflow, a way to get unreviewed code to consumers) privately through
[GitHub private vulnerability reporting](https://github.com/kadet-hub/registry/security/advisories/new).
Do not open a public issue for it.

A listed generator that behaves maliciously is reported the same way. A
confirmed malicious version is yanked, its artifact deleted and an advisory
published (`docs/specs/marketplace.md`, INC-1). The marketplace has one
maintainer, so the 24-hour target is best effort.

For vulnerabilities in a generator's own code that are not malicious, contact
the generator's repository first.
