# kadet-hub registry

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/kadet-hub/registry/badge)](https://scorecard.dev/viewer/?uri=github.com/kadet-hub/registry)

Marketplace for [Kapitan](https://kapitan.dev) generators. Each listed
version passed a gate of scans, a sandboxed fixture compile and a
maintainer's review, and is published as an attested OCI artifact under
`ghcr.io/kadet-hub/<name>`.

- Catalog: [kadet-hub.org](https://kadet-hub.org)
- Using a generator: [docs/consumers.md](docs/consumers.md)
- Adding a generator: [docs/authors.md](docs/authors.md)
- Design and requirements: [docs/specs/marketplace.md](docs/specs/marketplace.md) and the area specs it indexes
- Reporting a vulnerability or requesting removal: [SECURITY.md](SECURITY.md)
- Terms of listing: [TERMS.md](TERMS.md)

kadet-hub is a community project and is not affiliated with or endorsed by
the Kapitan project or kapicorp. Listed generators are the work of their
authors. The marketplace is offered free of charge, as is and on a
best-effort basis: use it at your own risk, and review the compiled output
before you apply it ([TERMS.md](TERMS.md#no-warranty)).

## How changes are reviewed

`neat-bot` reviews the pull requests. It is an automated reviewer, not a
person. Its review either approves the head commit or leaves one comment
per finding. A pull request merges only after `neat-bot` approved its
current head commit. The author fixes each finding or answers it in its
thread, then asks for a new review. Every push, also an update from
`main`, needs a new approval. `neat-bot` works through a queue that can
lag by hours, so a merge can wait for it. The rulesets do not enforce
this, because `neat-bot` has read access only. It is the process the
maintainer follows.

No second person reviews the maintainer's own changes or those coding
agents make for the maintainer. They merge through the maintainer's admin
bypass once `neat-bot` approved. Pull requests from anyone else also need
the maintainer's approval. Renovate merges most of its own dependency
updates once every check passed, without `neat-bot`. The rules are in
[docs/specs/gate.md](docs/specs/gate.md#review).
