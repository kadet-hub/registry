# Kapitan generator marketplace: Catalog

Status: Approved
Code: `catalog/`, `policy/tags.yaml`, `.github/ISSUE_TEMPLATE/`, `docs/authors.md`, `README.md`
Verified against: main @ 970a5d4

Related: [marketplace.md](marketplace.md) holds the problem, threat model, decisions,
acceptance criteria, residual risks, open questions and the implementation inventory.

## Catalog

The catalog at `https://kadet-hub.org` lets people find a generator and
copy a pinned inventory entry. It is a view on the index: the release
workflow generates it with Hugo from the `index.json` the index job just
published or verified unchanged, and deploys it with GitHub Pages from
`kadet-hub/registry`. The site has no backend, no accounts and no data of
its own, so a later platform with ratings can read the same index instead
of migrating site data.

Each generator has a card (CAT-22) and a page at `/generators/<name>/`
with the latest version's README and every version. The home page's
introduction spans the width of the card grid below it. Search and tag filter run in the browser over the rendered cards.
Owner logins and stars come from the GitHub API at build time; they are
display data only, and a failed lookup shows the user ID or no stars.

A generator has no logo of its own: the card shows the icon of its first
tag on a tile coloured from a fixed palette by a hash of the name; the
generator page keeps the monogram of its name. Submitters supply no images, so none needs to be checked. The
icons are Lucide's (ISC), inlined into every page as an SVG sprite. The
site follows the system colour scheme; a toggle overrides it and is
remembered in the browser's `localStorage`.

- CAT-7: The generator page MUST show the README of the latest version that
  is not yanked, read from that version's published artifact by digest, as
  Markdown without raw HTML.

  The README passed the gate and the review with the rest of the tree;
  the catalog job pulls the layer by digest, so it shows exactly what
  consumers fetch. Raw HTML is omitted and links with a script or data
  scheme are dropped. Images are not loaded, since the CSP allows only
  the site's own origin; each becomes a link to its target. Relative links
  and images point into the source tree at `source.sha`. A README above
  256 KiB is not shown.

  - Test: `catalog/test_catalog.py`
  - Since: #45

- CAT-8: Selecting several tags MUST show the generators that carry all of
  them, and the selection MUST be kept in the URL as `?tags=<a>,<b>`; every
  tag shown on a card or page MUST link to that filtered view.

  Tags are multiply assigned (a generator can be `helm`, `operators` and
  `kubernetes` at once), so OR would widen the result with every click.
  The result line names the selected tags. Without
  JavaScript the home page lists every generator.

  - Test: `catalog/test_catalog.py` (partial: the links and the markup; the
    filter itself runs in the browser)
  - Since: #45

- CAT-9: Code blocks, tables and long values such as digests MUST wrap
  instead of scrolling horizontally, and every inventory entry and command
  MUST have a copy button.
  - Test: `catalog/test_catalog.py` (partial: the markup)
  - Since: #45

- CAT-10: The home page MUST let visitors sort the cards by name, by the
  time of the latest version and by popularity score (CAT-23).

  Sorting by stars or 👍 alone was replaced by the score, which combines
  both with pulls; sorting by maintainer was considered and left out while
  every generator has the same one.

  - Test: `catalog/test_catalog.py` (partial: the sort keys in the markup)
  - Since: #45

- CAT-11: Every page MUST have a title of 30 to 65 characters, a meta
  description of 50 to 160 characters, one `h1` and an absolute canonical
  URL; the site MUST publish `sitemap.xml` with every generator page and a
  `robots.txt` that names it.

  The length limits are the ones kapicorp/kapitan enforces for its
  documentation (`tests/test_docs_rendering.py`); here they are checked on
  the built HTML. Filtered views (`?tags=`) are the home page and share
  its canonical URL. Generator pages carry schema.org
  `SoftwareSourceCode` as JSON-LD, which the CSP does not block because a
  data block is never executed. A generator description that leaves the
  title or description outside the limits is padded or cut by the
  template, not rejected at the gate.

  - Test: `catalog/test_catalog.py`
  - Since: #45

- CAT-12: The generator page MUST link to an issue form for reporting a
  problem with that generator, prefilled with its name and latest version,
  and the home page MUST link to an issue form for requesting a new
  generator.

  The forms are GitHub issue forms in `.github/ISSUE_TEMPLATE`; the site
  has no backend, so a visitor needs a GitHub account. The report form
  sends malicious behaviour and vulnerabilities to private vulnerability
  reporting (SECURITY.md) instead of a public issue. The request form
  asks what the generator should render and for the upstream sources it
  would wrap: Helm chart, Kustomize base, manifests or CRDs, Dockerfile,
  Terraform module.

  - Test: `catalog/test_catalog.py` (the links); `tests/workflow-policy`
    does not cover the forms
  - Since: #45

- CAT-14: The card MUST show the date of the latest version's scan record
  and the version page the full record with a link to the release run;
  the page MUST offer the version's SBOM for download, taken from its
  verified attestation.

  The catalog job runs `gh attestation verify` with the SBOM predicate
  type for each listed version and writes the predicate to
  `/generators/<name>/<version>.spdx.json`. A version without a record or
  SBOM says so. The page names what the checks cover, as listed checks
  that ran and passed, and links to what a listing covers; it shows no
  score or "secure" badge.

  In the rehearsal the fork's catalog showed the record and served
  `generators/keda/1.0.0.spdx.json`.

  - Test: `catalog/test_catalog.py`; manual: fork rehearsal (2026-10-11)
  - Since: #47

- CAT-21: The generator page MUST link "Request a feature" to a new issue
  in the generator's source repository, prefilled with the generator's
  name in the title and its version and catalog page in the body.

  Owners implement features in their own repository and watch its
  tracker, not the registry's; the registry's report form (CAT-12) stays
  for problems with a listed version. Sources are on github.com or
  gitlab.com (`policy/entry.schema.json`), so there are two URL forms: `/issues/new?title=&body=`
  and `/-/issues/new?issue[title]=&issue[description]=`. The link is on
  the page, not the card, as in the catalogs compared (Raycast puts
  "Request Feature" on the extension page, none of ten catalogs on the
  card); the card keeps one click target and the tag links.

  Sources under the registry's GitHub owner open the issue form
  `feature-request.yml` instead (`template=` with the `generator` and
  `version` fields prefilled). The form is an organisation default in the
  owner's `.github` repository, so every generator repository there gets
  it, and the generator template ships a copy for repositories created
  from it. Other sources keep the prefilled body, because the registry
  cannot tell whether a foreign repository has the form.

  - Test: `catalog/test_catalog.py`
  - Since: #73, #93

- CAT-22: Every card MUST show the same fields in the same order: the
  name as the only card-wide link, below it the latest version and its
  date, the description clamped to three lines, the tags, and labelled
  facts: "Built for" (one software and version per line, or "not
  recorded"), "Maintainer" (the owners, each linked to their profile), "Popularity"
  (the score of CAT-23, linked to its explanation) and "Scanned" (the scan
  date or "not scanned").

  Users read the top left first and scan the first words of lines (NN/g);
  attributes that appear on some cards and not on others make a catalog
  look smaller and are hard to compare (Baymard), so missing values are
  stated instead of omitted. License and the note that stars are shared
  by several generators move to the generator page, where there is room
  to explain them. The version sits on its own line under the name, so it
  is in the same place on every card whatever the length of the name.
  Facts carry visible labels instead of bare icons. A generator built for
  several products, such as cert-manager with trust-manager, lists each
  on its own line, because a run-on line with separators reads like the
  version line above it and wraps mid-name on narrow cards. The name link
  stretches over the card and the tag and maintainer links sit above it, the block-link pattern recommended by Heydon
  Pickering and Adrian Roselli; the focus ring is drawn when the name link
  has keyboard focus, not when a tag link does.

  - Test: `catalog/test_catalog.py`
  - Since: #73, #81, #92

- CAT-23: Every generator MUST have a popularity score
  `round(10·log2(1 + 👍) + 4·log2(1 + stars ÷ n) + 2·log2(1 + pulls))`,
  shown on its card and page and explained at `/popularity/` with the
  inputs of every generator.

  👍 is the count on the generator's discussion (CAT-20), stars are the
  source repository's stars divided by the n listed generators that share
  the repository, pulls the "Total downloads" of the generator's package.
  The logarithm keeps one source from dominating and makes inflating a
  count by automation or bought stars pay off less and less; the weights
  follow how specific a signal is to one generator: a 👍 is given to this
  generator on purpose, stars are given to a repository and can be bought
  (arXiv:2412.13459), pulls include automation.

  GHCR has no download API: the REST package objects have no download
  field and the GraphQL package statistics do not cover the Container
  registry. The catalog job therefore reads the number from the public
  package page; when the page cannot be read, pulls count as 0 and the page
  says so. Every manifest fetch counts (measured: one `oras manifest
  fetch` raised the count by one), and the catalog job fetched each latest
  artifact on every build. The site therefore publishes its view model as
  `/catalog.json`, and the next build takes README, log index and SBOM of
  every unchanged digest from it and from the published SBOM files, so the
  job pulls each version once. A cache (`actions/cache`) would do the same
  but is forbidden by GI-10.

  - Test: `catalog/test_catalog.py`
  - Since: #83

- CAT-15: The card and the version page MUST show what a version is built
  for, from the software and versions of the schemas QA-7 and QA-8
  validated its output against, marked as schema-checked.

  The release's compile gate records the result in `meta.json` as
  `compatibility`, like the krab result, so only versions published after
  this requirement carry it.

  Each software and version is shown once. Several schema groups of one
  release, such as linkerd.io and policy.linkerd.io, record the same
  software and version with different sources; the first source is linked.

  - Test: `catalog/test_catalog.py`
  - Since: #50, #132

- CAT-16: The site MUST publish `/llms.txt` in the llmstxt.org format, naming
  the marketplace's purpose and linking the author guide, the template and
  its `AGENTS.md`, the tags, the glossary and the gate's policy files.

  Coding agents asked to write a generator start there instead of guessing
  the gate's rules from the HTML.

  - Test: `catalog/test_catalog.py`
  - Since: #51

- CAT-17: Every version on a generator page MUST have a permalink
  (`/generators/<name>/#v<version>`) that opens it, and MUST link the
  Sigstore transparency log entry of its provenance attestation.

  The catalog job reads the log index from the attestation it verifies
  with `gh attestation verify`, so a link only appears for a verified
  attestation. The entry lives in Sigstore's public, append-only Rekor
  log, independent of this site and of GitHub, so it stays checkable when
  a version is yanked or the catalog changes. The verify command is split
  into one flag per line.

  - Test: `catalog/test_catalog.py`
  - Since: #54

- CAT-18: The site MUST have a page per tag at `/tags/<tag>/` with the tag's
  definition from `policy/tags.yaml` and the cards of every generator that
  carries it, an Atom feed of published versions at `/index.xml`, an
  `og:image` on every page, and guides under `/guides/`.

  Tag pages are landing pages for searches such as "Kapitan Kubernetes
  generator"; they reuse the tag definitions and the card markup instead
  of copying them. The feed lists one entry per published version, newest
  first, linking its permalink (CAT-17). The guides are articles for
  people deciding whether and how to write or consume a generator; they
  link the reference documents instead of repeating them.

  - Test: `catalog/test_catalog.py`
  - Since: #55

- CAT-19: A generator page MUST show its sections in one centered column
  of equal width, in the order README, Versions, and MUST have an "On this
  page" list linking each section that is present, which marks the section
  in view. Versions MUST show the newest listed version expanded, with its
  inventory entry, verify command, details and checks, and state once above
  the list how to consume a version (consumer workflow, terms, index
  serial, what the checks cover).

  Separate Install, Verify, Checks and Details panels for the newest
  version repeated what its expanded entry under Versions already shows.
  A side column made the panels different widths and pushed Checks and
  Details below the README on narrow screens. The list replaces it as the
  way to jump to a section; sections a generator does not have, such as
  the README for a fully yanked one, are left out of the list. On wide
  screens it sits beside the column and stays in view while scrolling, as
  on MDN and GitHub Docs, so the column keeps its width; on narrow screens
  it is a collapsed disclosure above the sections. Without JavaScript it is
  open and only the marking of the section in view is missing.

  - Test: `catalog/test_catalog.py`
  - Since: #56, #79, #111

- CAT-20: Each listed generator MUST have one discussion in the
  "Generators" category of the registry's GitHub Discussions, and its card
  and page MUST show the discussion's 👍 count and link it.

  Stars belong to a repository, and one repository can hold several
  generators, so they say nothing about a single generator. A 👍 on the
  generator's discussion does, needs only a GitHub account and no backend
  here. The catalog job opens a missing discussion, titled with the
  generator's name, with `discussions: write`, and reads the counts at
  build time like the stars. It never opens a second discussion for a title
  that exists in the category, and counts only the discussion the workflow
  opened, so a discussion someone else opened under that title is not
  counted. The opening post asks for a 👍, links the generator page and
  sends bug and security reports to the report form (CAT-12), so they
  reach the owners instead of a comment thread. Without the category the
  catalog shows no counts and the job warns. The release workflow also runs daily, so counts are at most a day
  old.

  Where several listed generators share a source repository, the stars
  MUST be labelled as repository stars with the number of generators that
  share them.

  - Test: `catalog/test_catalog.py`
  - Since: #57

The footer names the index serial the site was built from, and the
generator page's Versions section explains it: consumers set `index_serial`
in `.kapitan-sandbox.yaml` to the serial they last checked, so an older
index is refused (CON-2).

- CAT-1: The release workflow MUST build the catalog from the index it
  published or verified in the same run, and deploy it from a job bound to
  the `github-pages` environment, which admits only `main`.

  Run on 2026-10-09 in the rehearsal fork: one release run published the
  artifact and the index and deployed the catalog under a project path;
  the version page showed the attested digest and the owner's login.

  - Test: manual: fork rehearsal (2026-10-09)
  - Since: #16

- CAT-2: A version page MUST show the inventory entry with the digest and the
  CON-2 verification commands; a yanked version MUST show its reason and no
  inventory entry.
  - Test: `catalog/test_catalog.py`
  - Since: #16

- CAT-3: The site MUST render every value from the index and the GitHub API
  through Hugo's contextual escaping and MUST NOT load scripts, styles or
  fonts from another origin.

  Description, tags and owners come from submitters; a description with
  markup is shown as text.

  - Test: `catalog/test_catalog.py`
  - Since: #16

- CAT-4: `tags` in the manifest MUST come from the enum in
  `policy/manifest.schema.json`: `kubernetes`, `helm`, `operators`,
  `terraform`, `cloud`, `observability`, `security`, `networking`,
  `database`, `ci`, `clusters`, at most five per manifest.
  - Test: `gate/test_check_entry.py` (`Manifest`)
  - Since: #16, #133

- CAT-13: `policy/tags.yaml` MUST define every tag of the enum, with its
  meaning and when to assign it and when not; the site MUST render it at
  `/tags/`, linked from the tag filter, and MUST have a glossary at
  `/glossary/` that links to the Kapitan documentation.

  The file is the reference for review: a tag is a claim by the
  submitter, and the reviewer checks it against this text. The
  `evidence` field names what the gate verifies for `kubernetes`,
  `helm` and `terraform` (QA-6).
  Each tag button shows how many listed generators carry the tag, as
  `security (6)`, and is disabled when the current selection would leave
  none.

  - Test: `catalog/test_catalog.py`
  - Since: #45

- CAT-5: URLs `/` and `/generators/<name>/` MUST stay stable.
  - Test: none
  - Since: #16

- CAT-6: The home page MUST link to `docs/consumers.md` and
  `docs/authors.md`, and MUST say so when no generator is listed.

  `docs/authors.md` describes registration for authors: manifest, fixture
  project, entry and what the gate and the review check, and when a
  generator is worth writing and when another Kapitan input is the better
  tool, with ideas for generators, and how to patch a Helm chart instead of
  wrapping it in a generator (DEC-15). The root `README.md` points to the
  catalog and both documents, and the template repository
  `kadet-hub/generator-template` starts a generator with the files the gate
  expects, a local check and `AGENTS.md` for coding agents.

  - Test: `catalog/test_catalog.py`
  - Since: #18, this change
