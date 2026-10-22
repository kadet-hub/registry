# Kapitan generator marketplace: Catalog

Status: Approved
Code: `catalog/`, `policy/tags.yaml`, `.github/ISSUE_TEMPLATE/`, `docs/authors.md`, `README.md`, `docs/consumers.md` (CAT-34d)
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
  Markdown without raw HTML. The README MUST NOT be able to call a
  shortcode.

  Hugo expands shortcodes in text passed to `RenderString`, and an unknown
  one fails the whole build, so one README could block every deploy. The
  delimiters `{{<` and `{{%` are escaped before rendering, as for the
  CHANGELOG sections of CAT-36b. In prose they show as typed; in code the
  escaping backslash shows (`{{\<`), since Markdown keeps backslashes there.

  The README passed the gate and the review with the rest of the tree;
  the catalog job pulls the layer by digest, so it shows exactly what
  consumers fetch. Raw HTML is omitted and links with a script or data
  scheme are dropped. Images are not loaded, since the CSP allows only
  the site's own origin; each becomes a link to its target. Relative links
  and images point into the source tree at `source.sha`. A README above
  256 KiB is not shown.

  - Test: `catalog/test_catalog.py`
  - Since: #45, #293

- CAT-8: Selecting several tags MUST show the generators that carry all of
  them, and the selection MUST be kept in the URL as `?tags=<a>,<b>`.

  Tags are multiply assigned (a generator can be `helm`, `operators` and
  `kubernetes` at once), so OR would widen the result with every click.
  The result line names the selected tags. Without
  JavaScript the home page lists every generator.

  - Test: `catalog/test_catalog.py` (partial: the links and the markup; the
    filter itself runs in the browser)
  - Since: #45

- CAT-8a: Every tag shown on a card, a generator page or the tag overview
  MUST link to that tag's page `/tags/<tag>/`.

  Until this change the links went to the filtered home page. Audit tools
  flag internal links with query parameters, and the tag page (CAT-18)
  lists the same generators with the tag's definition; the filter chips
  on the home page still combine tags.

  - Test: `catalog/test_catalog.py`
  - Since: #221

- CAT-9: Code blocks, tables and long values such as digests MUST wrap
  instead of scrolling horizontally, and every inventory entry and command
  MUST have a copy button.
  - Test: `catalog/test_catalog.py` (partial: the markup)
  - Since: #45

- CAT-9a: Below 48rem the site header MUST be one row with a menu button
  that opens the nav as a list below it, the tag chips MUST be collapsed
  behind a "Filter by tag" button that counts the selected tags, and the
  home page filters MUST NOT stay fixed while the visitor scrolls.

  At 393 px, an iPhone 15, the ten nav links wrapped into four
  right-aligned rows and the header was 150 px tall; the eleven tag chips
  took five rows, and the sticky filters covered 354 px of a 660 px
  viewport, more than half of every scrolled screen. The menu follows
  GitHub's mobile header: brand, theme button, menu button; Escape closes
  the open menu. The filters scroll with the page; the search is at the top
  of the list, one scroll up. The hero buttons share each row's width
  instead of leaving ragged gaps.

  Both buttons are added by `site.js`. Without JavaScript the nav and the
  chips stay open, so every link and tag remains reachable.

  - Test: `catalog/test_catalog.py` (partial: markup and stylesheet);
    manual: 393 px viewport, menu and tag filter open and close, filters
    not sticky
  - Since: #309

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

- CAT-11a: The home page MUST have a title of 50 to 60 characters and
  MUST carry schema.org `WebSite` and `Organization` as JSON-LD.

  Audit tools such as SEOptimer score a home page title below 50
  characters as too short and look for an identity schema; the
  `Organization` names kadet-hub, its logo and the GitHub organization as
  `sameAs`, without an address or phone number, which the site does not
  publish.

  The home page's title, `h1` and description, and the titles of guides
  and recipes about Kapitan, name Kapitan together with Kubernetes or
  Terraform; only the home page is tested. Blog post titles and generated
  page titles (generator, tag, kind, release digest) lead with the
  searched term instead and name Kapitan where it fits. On its own,
  "kapitan" completes in search suggestions to a restaurant and a border
  crossing, and "kadet" to a car (checked 2026-10-17 with Google's and DuckDuckGo's suggestion endpoints);
  "kapitan kubernetes" and "kapitan generator" are unambiguous. Guide
  titles lead with the term searched for: "migrate ingress-nginx to
  Gateway API", "kapitan generator vs helm chart vs kustomize", "Bitnami
  chart alternatives".

  The Bitnami guide is one page with a section per chart rather than a
  page per chart: near-identical pages per search term are doorway pages
  under Google's spam policies.

  - Test: `catalog/test_catalog.py`
  - Since: #196, #274, #279

- CAT-11f: The home page's title, `h1` and description MUST name Helm as
  what kadet-hub is an alternative to, and the description MUST also name
  Kustomize.

  kadet-hub wants to appear where Helm, Kustomize and Pulumi appear. The
  queries below complete in Google's or DuckDuckGo's suggestions (checked
  2026-10-19, the cert-manager and trust-manager row 2026-10-20, the
  kustomize, thanos and prometheus operator queries 2026-10-21);
  suggestions show that a query is made, not how often. A new
  page title or description SHOULD lead with one of them when the page
  answers it, and the list is rechecked when a page is added for a query
  not on it.

  | Query | Answered by |
  |---|---|
  | helm alternatives kubernetes | home page, guide "Helm alternatives for Kubernetes" |
  | kustomize alternatives | home page, same guide |
  | pulumi vs helm | same guide |
  | helm vs helmfile (also "helmfile vs helm"), helm chart vs helmfile, helm umbrella chart vs helmfile (checked 2026-10-22) | same guide, section #helmfile |
  | cdk8s vs helm, cdk8s vs kustomize, cdk8s vs pulumi, grafana tanka vs helm | same guide, blog post "cdk8s vs Tanka vs Kapitan for Kubernetes config" |
  | kustomize vs helm (also "helm vs kustomize"), kustomize vs helm charts, helm chart vs kustomize, helm template vs kustomize | blog post "Helm vs Kustomize vs Kapitan on one Kubernetes app" |
  | helm vs kustomize vs jsonnet, helm vs kustomize vs terraform | blog post "Helm vs Kustomize vs Kapitan on one Kubernetes app", guide "Kapitan generator vs Helm chart vs Kustomize" |
  | bitnami alternative | guide "Bitnami chart alternatives", `/recipes/` |
  | thanos helm chart not bitnami, thanos bitnami alternative, prometheus operator helm chart bitnami | guide "Bitnami chart alternatives" |
  | bitnami alternative postgres, bitnami alternative redis, bitnami alternative kafka, cloudnativepg vs bitnami | `/recipes/`, blog post "Bitnami Helm alternatives", `/recipes/postgresql/` |
  | postgres, redis, keycloak, rabbitmq or kafka helm chart without bitnami (also "not bitnami", "bitnami alternative"), valkey helm chart not bitnami | the matching `/recipes/<name>/` page, `/recipes/valkey/` for redis |
  | mysql helm chart not bitnami, bitnami mysql alternative, bitnami alternative mongodb | `/recipes/mysql/`, `/recipes/mongodb/` |
  | kubernetes configuration management tools | blog post "cdk8s vs Tanka vs Kapitan for Kubernetes config" |
  | ingress nginx retirement replacement, ingress nginx gateway api migration | guide "Migrate ingress-nginx to Gateway API" |
  | kubectl dry run server side, kubectl dry run server vs client, kubeconform github action | blog post "kubectl server-side dry run in CI, without a cluster" |
  | kubeconform vs kubeval, helm lint vs kubeconform, kubelinter vs kubeconform (checked 2026-10-22) | same post, section #kubeval-helm-lint-kube-linter |
  | kubectl validate crd | guide "Validate Kubernetes custom resources against their CRDs" |
  | kustomize json patch add, kustomize add annotation, service appprotocol, kubernetes trafficdistribution (checked 2026-10-21) | blog post "Kustomize JSON patch add: fields a Helm chart does not template", one section per chart |
  | cosign verify-attestation, gh attestation verify, slsa provenance attestations | blog post "cosign verify-attestation vs gh attestation verify" |
  | gvisor sandbox | blog post "gVisor in CI: sandboxing untrusted code on GitHub Actions" |
  | kyverno chainsaw, chainsaw test kubernetes, kubernetes e2e testing, kubernetes end to end testing, kind cluster github actions | blog post "Kyverno Chainsaw: Kubernetes e2e testing on kind in CI" |
  | talos machine config, talos machine config example, talos machine config patch, talos machine config network, talos machine config schema | guide "Talos machine config for Kubernetes from a Kapitan inventory" |
  | argocd vs flux (also "flux vs argocd", "argo cd vs flux") | guide "Argo CD vs Flux, deployed side by side on kind" |
  | helm vs argocd, kustomize vs helm vs argocd, kustomize vs argocd | same guide |
  | gvisor vs docker (also "docker vs gvisor", "gvisor docker runtime") | blog post "gVisor in CI: sandboxing untrusted code on GitHub Actions", section #gvisor-vs-docker |
  | helm vs terraform, helm chart vs terraform, kubernetes manifests terraform | guide "Helm vs Terraform for Kubernetes, and Kapitan for both" |
  | kustomize patch env variable, kustomize patch environment variable, kustomize patch add env var (checked 2026-10-21) | blog post "Kustomize patch env variable with valueFrom in a Helm chart", sections #keda-http-add-on-env and #crossplane-env-secret |
  | patch helm chart, patch helm chart with kustomize, kustomize patch helm chart, helm patch chart, modify helm chart, edit helm chart | guide "Patch a Helm chart: post-renderers, Kustomize and Kapitan" |
  | kustomize delete resource, kustomize patch delete resource, kustomize remove resource (checked 2026-10-21) | blog post "Kustomize delete resource: Kyverno PDBs and ESO webhooks", sections #kyverno-pdb and #external-secrets-webhooks |
  | helm post renderer, helm post renderer kustomize, helm post renderer argocd, kustomize helm charts, argocd kustomize helm, flux helmrelease postrenderer patch example | same guide |
  | kube prometheus stack dashboards, kube prometheus stack default dashboards, kube prometheus stack default grafana dashboards (checked 2026-10-21) | blog post "kube-prometheus-stack default Grafana dashboards, one by one", section #disable-default-dashboards |
  | kustomize helm chart generator, kustomize render helm chart, kustomize enable helm, kustomize helm values file, kustomize helm argocd, render helm chart locally | same guide, section "Kustomize with helmCharts" |
  | cert-manager helm chart, helm chart initcontainers, trust-manager helm chart, cert manager trust manager helm chart | blog post "cert-manager Helm chart initContainers and trust-manager issuer" |
  | actions runner controller dind, github actions runner controller dind, gha runner scale set dind (checked 2026-10-21) | blog post "Actions Runner Controller dind image from your own registry", section #arc-dind-image |

  The two requests that post answers, "cert-manager helm chart
  initcontainers" and "trust-manager custom issuer", complete in neither
  engine. Its sections keep the fixed anchors `#cert-manager-initcontainers`
  and `#trust-manager-custom-issuer`, so that a link to a section, from
  cert-manager/cert-manager#6071 or cert-manager/trust-manager#778 for
  example, stays valid when a heading changes.

  "kapicorp" is not a target: the people who search it know Kapitan
  already, and a page ranking for it could be taken for kapicorp's own.

  - Test: `catalog/test_catalog.py` (`test_home_identity_schema_and_title`)
  - Since: #284, #287, #288, #290, #291, #297, #298, #299, #304, #312, #313, #314, #315, #316, #318, #319, #320

- CAT-11g: Every guide and recipe MUST carry `lastmod` in its front
  matter, the day its text last changed, and schema.org `TechArticle`
  JSON-LD with that date as `dateModified`.

  Without a date, guides and recipes were the only content pages without
  `<lastmod>` in the sitemap and without JSON-LD (55 of 110 pages had
  none). The date is in the front matter because `catalog/build` copies
  the site to a work directory, where Hugo has no Git history to read.
  Hugo would otherwise take `lastmod` as `date` too, which orders lists;
  `[frontmatter] date` names `date` and `publishDate` only, so guides and
  recipes keep their order by title.

  - Test: `catalog/test_catalog.py` (`test_guides_and_recipes_dated`)
  - Since: #322

- CAT-11h: A guide, recipe or post that names a listed generator as
  "`<name>` generator" MUST link that generator's page there.

  The posts and guides are where search traffic arrives, the generator
  pages are what kadet-hub lists. A name in running text without the link
  leaves the reader one search away from the page.

  - Test: `catalog/test_catalog.py` (`test_generator_mentions_linked`)
  - Since: #322

- CAT-11c: Every `img` MUST have a non-empty `alt`, and every page MUST
  link an Apple touch icon.

  The logo next to the site name used `alt=""` as decorative; audit tools
  count that as missing, so it is named at the cost of the name being read
  twice. The touch icon is `favicon.svg` rendered as a 180 by 180 PNG.

  - Test: `catalog/test_catalog.py`
  - Since: #221

- CAT-11b: Headings MUST NOT skip a level, a list of cards MUST sit under
  an `h2`, and a card's name MUST NOT be a heading.

  Card names were first `h2` directly under the page's `h1` (36 `h2`, no
  `h3`), then `h3` under an `h2`, which gave the home page 37 headings
  for little text. Guides for listing pages keep headings for the page
  and its sections, not for every item of a list, and avoid linked
  headings; the cards are a list, which assistive technology can step
  through as such. The home page has a short section on how a version
  gets listed, an `h2` with an `h3` per step, which links the guide of
  CAT-35 for the whole process.

  - Test: `catalog/test_catalog.py`
  - Since: #196, #230, #257

- CAT-11e: A README heading MUST be rendered at most one level below the
  heading before it.

  READMEs come from submitters and may jump from `#` to `###`; rendered
  as written, that breaks CAT-11b and, through CAT-11d, would block every
  deploy until the generator publishes a fixed README. The render hook
  shifts README headings one level down (the page's `h1` is the generator
  name) and clamps each to one below the previous heading, starting below
  the `h2` of the table of contents.

  - Test: `catalog/test_catalog.py`
  - Since: #228

- CAT-11d: Every HTML page of the built site MUST pass the checks of CAT-8a
  and CAT-11 to CAT-11c, in `catalog-tests` on the fixture build and in the
  release before the site is deployed. A failure MUST stop the deploy, so
  the previous site stays live.

  Until this change `test_seo` checked 14 listed pages of the fixture
  build, and the release deployed the real site, with the submitters'
  READMEs and descriptions, unchecked. `catalog/seo_check.py` walks the
  built site, prints one finding per line as `CAT-11x: <path>: <message>`
  and exits 1 on any. In the release's catalog job it runs between the
  build and the upload of the Pages artifact, so a finding fails the job
  and the `pages` job does not run.

  Lengths are counted after HTML unescaping, as a browser shows the text.
  The canonical URL must be the absolute URL of the page itself. A Hugo
  alias page (a meta refresh to the new URL) is a redirect, not a page,
  and is not checked; the site has none.

  README headings are rendered one level below the page's own (`#`
  becomes `h2`), so a README that skips a level, such as `#` followed by
  `###`, fails CAT-11b. The gate does not check README headings, so such a
  version stops every catalog deploy until a new version fixes the README
  or the version is yanked. On 2026-10-15 the 59 pages of the live site's
  sitemap, 36 generator pages with 35 READMEs, had no finding.

  - Test: `catalog/seo_check.py`; `catalog/test_catalog.py` (`test_seo`,
    `test_seo_check_finds_violations`); release step "Check the built site
    (CAT-11d)" in `.github/workflows/release.yml`
  - Since: #227

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

- CAT-31: The site MUST have a page at `/wanted/` that lists every open
  issue of the registry with the label `generator-request`, each with its
  title linked to the issue, its 👍 count and the date of its last
  activity, most 👍 first and, among equal counts, the oldest issue first.
  The home page MUST link the page next to "Request a generator".

  The request form (CAT-12) sets the label. Without a list of open
  requests, an author looking for something to write has to search the
  tracker, and a visitor with the same wish opens a second issue instead of
  adding a 👍 to the first. A 👍 on the issue counts as it does on a
  generator's discussion (CAT-20).

  The catalog job reads the issues at build time with `gh api` from
  `/repos/<owner>/registry/issues?labels=generator-request&state=open`,
  leaving out pull requests, with `issues: read`. "Last activity" is the
  issue's `updated_at`; the page also shows the date the issue was opened,
  since that breaks ties. The release workflow runs daily, so the list is
  at most a day old. An offline build reads the list from `CATALOG_WANTED`.

  Titles come from whoever opened the issue. The page shows each title as
  text through Hugo's escaping, without the control characters of CAT-27
  (`_partials/text.html`) and without the form's `[request] ` prefix, and
  shows nothing of the body. The link is built from the issue number.

  Without an open request the page says so and links the form. When the
  issues cannot be read, the job warns and the page says the list was not
  read, so a failed lookup does not read as "nothing wanted".

  - Test: `catalog/test_catalog.py`
  - Since: #245

- CAT-33: The site MUST have a page at `/stats/` with a section for the
  pulls of every generator, one for the versions published and yanked per
  month, and one for the entry pull requests the gate rejected, by
  requirement. The page MUST name its data sources and build time, and
  the footer and `/llms.txt` MUST link it.

  Cards and the popularity page show numbers per generator; nothing showed
  them across the registry, or how often the gate turns an entry away. Each
  section is an `h2` with tables (CAT-9, CAT-11b). The page has no Markdown
  variant (CAT-28). It shows no visitor numbers: the page views stay on the
  GoatCounter instance of CAT-25, and the build does not read them.

  Pulls are the totals the build already reads for CAT-23, most first; a
  package page that could not be read shows "not read" and adds nothing to
  the total. The previous build's `catalog.json` holds one total per
  generator, that build's, and no series, so the page shows no history.

  A version counts in the month of its `published` time in the index
  (PUB-4). The index records a yank with its reason and without a time, so
  a yanked version counts as yanked in the month it was published, and the
  page says so.

  The catalog job reads every pull request of the registry with one
  paginated `gh api graphql` query, with `pull-requests: read`: the paths
  it changes (the first 100) and each comment with its author, body and
  edit history. The gate keeps one comment per pull request and edits it on
  every run (REV-2), so the edit history holds one version per run. An entry
  pull request changes a file `generators/<name>.yaml` and has a gate
  comment: a comment by `github-actions` that starts with the marker
  `<!-- kadet-hub-gate -->`; a comment by anyone else with the marker does
  not count. It is rejected when one version of its comment reads
  `**gate: failed**`. An offline build reads the pull requests from
  `CATALOG_GATE`. When they cannot be read, the job warns and the section
  says the results were not read.

  The comment job writes `New entry; source tree:` or `Code diff since the
  approved version:` above the report, from the gate's `entry.json`. A pull
  request with a compare link in one version is an update, one with a
  source tree a new entry, and any other, such as a removal or a pull
  request the gate stopped before writing `entry.json`, is "other".

  The gate prints a finding as a line that starts with its requirement ID,
  such as `CMP-5: output differs with --cache on omegaconf:`, and prints
  lines of the same form for checks that passed: `QA-6: tag <tag>:
  <evidence>`, `QA-7`, `QA-8`, `QA-10` and `QA-11: validated against`,
  `CMP-4: krab <result>` and `SEC-12: declared`. Its section `## Output
  diff` holds no finding: SEC-13, the QA-7 schema changes and the approved
  version's compile, which is reported and not judged. A requirement counts
  for a rejected pull request when a failed version's report has, before
  `## Output diff`, a line that starts with `GI-`, `REG-`, `SEC-`, `QA-` or
  `CMP-`, a number, an optional letter and `: `, and is none of those pass
  lines (`PASSED` in `catalog/view.py`). In #191 that leaves CMP-5 of the
  six requirement IDs the report names. A gate change that adds a pass line
  of this form must add it to `PASSED`, or the page counts it as a reason.

  The static scan prints its findings by tool, such as `guarddog:
  threat-filesystem-destruction: 1` (SEC-2); a failed version without a
  requirement line counts as "no requirement ID in the report", and tool
  names are not mapped to requirements. A pull request counts once per
  requirement, so it can count in several rows.

  The report holds text from the entry and the generator's compile output,
  so a generator can print a line that reads like a finding. Of a comment,
  only the verdict, the kind of entry and the IDs that match the pattern
  reach `catalog.json`, and the page shows them with counts.

  On 2026-10-16 the gate had commented on 97 entry pull requests: 37 new
  entries, 59 updates and one removal. Their current comments showed one
  rejected pull request, the edit history three, one of each kind: CMP-5,
  REG-1 and REG-9, and one failed run named only GuardDog. The 36
  generators had 11,659 pulls; the 94 versions were all published in
  2026-10, one of them yanked.

  - Test: `catalog/test_catalog.py`
  - Since: #251

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

- CAT-27: Each listed version on the generator page MUST show its output
  diff summary (PUB-9) against `output_diff.base` and the diff text from
  its verified attestation, at most 150 lines inline, and MUST offer the
  attested diff for download at `/generators/<name>/<version>.output.diff`.

  The catalog job verifies the attestation with `gh attestation verify`
  and the predicate type `https://kadet-hub.org/output-diff/v1`, as it
  does the SBOM (CAT-14), and keeps the text only when its sha256 equals
  the record's. A file the previous build published is reused when its
  sha256 matches, so each attestation is read once (CAT-23).

  The text goes into `<pre><code>` through Hugo's escaping, never through
  `safeHTML` or Markdown, with control characters removed (Unicode Cc
  other than tab and newline, and Bidi_Control); long lines wrap (CAT-9).
  Beyond 150 lines the page says the text is truncated and links the
  download, which is the attested text unchanged.

  A version without a record was published before PUB-9 and says "No
  output diff recorded". A record with an error states the error; a
  record whose text does not verify says so.

  - Test: `catalog/test_catalog.py`; manual: fork rehearsal (pending)
  - Since: #226

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
  recorded"), "Maintainer" (the owners' logins as text; the generator page links
  their profiles), "Popularity"
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
  stretches over the card and the tag and popularity links sit above it, the block-link pattern recommended by Heydon
  Pickering and Adrian Roselli; the focus ring is drawn when the name link
  has keyboard focus, not when a tag link does.

  - Test: `catalog/test_catalog.py`
  - Since: #73, #81, #92, #230

- CAT-26: A generator without a listed version MUST NOT have a card on the
  home page or a tag page, and MUST NOT be counted there.

  Every version of a removed entry is yanked with the reason `entry
  removed`, and the index keeps them. Their card read "no listed version,
  all yanked" and looked like a second generator next to the one it was
  merged into, as calico-resources did beside calico. The generator page
  stays at its URL (CAT-5) and shows the reasons; the popularity page
  keeps its row, which that page links to.

  - Test: `catalog/test_catalog.py`
  - Since: #224

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

- CAT-30: The site MUST have a page at `/compatibility/` with one row per
  listed generator (CAT-26) showing, for its latest listed version, the
  Kapitan range the manifest declares, the Kapitan version the release
  compiled it with, the inventory backends it compiled on, whether it
  compiled to the same output with `--cache`, the krab result and what it
  is built for (CAT-15). The details of every listed version on the
  generator page and the Markdown variant (CAT-28) MUST show the same facts.
  A fact the version does not record MUST read "not recorded".

  Before adopting a generator, people ask whether it works with their
  Kapitan version and inventory backend. The answers were spread over the
  manifest range, the scan record and the krab line of each version. The
  page states only what the release recorded for the artifact itself:
  "checked" means the release build compiled the fixture with that Kapitan
  version and backend. The declared range has its own column, because
  CMP-3 only requires it to include the pinned version; no other version in
  the range is compiled.

  The facts and their sources:

  - Kapitan declared: `kapitan`, the manifest's range (PUB-4).
  - Kapitan checked: the version in the tool of the scan record's `sandbox`
    check, which reads `gVisor <release>, Kapitan <version>` (PUB-7).
  - Backends checked: `backends` (PUB-11).
  - With --cache: "passed" when `backends` is recorded. CMP-5 runs on every
    backend, and a finding fails the build before the record is written.
  - krab: `krab` (CMP-4).
  - Built for (schema-checked): `compatibility` (CAT-15).

  Versions published before PUB-11 have no `backends` record, so their
  backends and `--cache` read "not recorded". On 2026-10-15 that held for
  all 35 listed latest versions; each had a scan record naming Kapitan
  0.36.3 and the krab result `compatible`. The gate commit in 27 of those scan
  records already ran CMP-5, but the record does not say on which backends
  (PUB-11 says why that is not derived).

  The three views take the facts from one partial, `_partials/compat.html`,
  which returns label, text and HTML of each fact; the table, the version
  details and the Markdown variant only lay them out, so all three show the
  same text. In the version details the facts replace the rows Built for,
  Kapitan and krab. A separate block for the newest version would repeat
  its expanded entry, which CAT-19 removed.

  The table takes the full page width, with fixed columns, so it wraps
  instead of scrolling (CAT-9). On screens narrower than 60rem each row is
  shown as a block with every value after its column name: seven columns
  in less width break words such as "compatible" in the middle. Columns
  sized by their content were tried; with `overflow-wrap: anywhere` the
  browser squeezed the short columns further. The site navigation and
  `/llms.txt` link the page; it has no Markdown variant.

  - Test: `catalog/test_catalog.py`
  - Since: #242

People choose a generator version by the upstream release they run: "I run
cert-manager 1.19, which certmanager version do I use?". The answer is in
each version's `compatibility` record (CAT-15), but finding it meant opening
every version and comparing records by hand. Artifact Hub added the app
version to its version list for the same request
([artifacthub/hub#4373](https://github.com/artifacthub/hub/issues/4373)).
The site therefore shows the record of every listed version in one table and
offers a selector over it; tools read the same records from `catalog.json`.

On the index of 2026-10-16 no generator had two listed versions built for
different versions of the same software. For most typed versions the honest
answer is therefore "none", and the selector says so instead of guessing
silently.

- CAT-34: Every generator page with a listed version MUST have, under
  Versions, a table of its listed versions with a column "Built for
  (schema-checked)" that names each software and version of the version's
  record, one per line, or "not recorded".

  The table is plain HTML, so without JavaScript it is the answer, read row
  by row. Each version links its permalink (CAT-17). Yanked versions are
  left out, since none of them can be picked; their entries stay in the
  list below.

  - Test: `catalog/test_catalog.py`
  - Since: #254

- CAT-34a: Above the table, the page MUST offer a selector "I run
  <software> <version>" that shows only the listed versions whose record
  names exactly that software and version.

  The software list holds every software a listed version's record names,
  once and sorted. A generator built for several products, such as
  cert-manager with trust-manager, is matched for one product at a time.
  The version is typed, with the recorded versions of the selected software
  as suggestions, because the version a visitor runs is often one that no
  generator version was built for. Typed and recorded versions compare as
  text after trimming whitespace and one leading `v` before a digit, so
  `v1.21.2` matches `1.21.2`.

  Kubernetes is listed only for generators whose records name it, which are
  those that ship core schemas. The kube-apiserver version QA-10 checks
  against is not recorded per version, so the selector cannot answer the
  Kubernetes question for other generators.

  The selector is progressive enhancement in `site.js`, which the CSP
  allows (`script-src 'self'`). Without JavaScript the form stays hidden and
  the table lists every listed version. The script reads software and
  version from data attributes and writes its result with `textContent`, so
  it builds no markup from data (CAT-3).

  - Test: `catalog/test_catalog.py` (partial: markup, options and data
    attributes; the matching runs in the browser); manual: browser run at
    375px and desktop width, light and dark (2026-10-16)
  - Since: #254

- CAT-34b: When no listed version is built for exactly the selected
  version, the selector MUST say "No listed version is built for <software>
  <version>" and show the listed versions built for the nearest newer
  recorded version of that software, labelled as not checked against the
  selected version.

  Nearest newer is a guess about upstream compatibility, not a check: the
  schemas of cert-manager 1.21.2 can accept output that a 1.19 operator
  ignores. The result is styled as a warning and names the version it was
  not checked against.

  Two versions compare by their dot-separated numbers when both are digits
  and dots after the leading `v` is removed; a missing part counts as 0, so
  1.21.2 is newer than 1.21. A recorded version such as Linkerd's
  `edge-26.6.3` or Thanos's `main@1b6edfb` only matches exactly and is
  never the nearest newer one. When no recorded version is newer, or the
  typed version is not digits and dots, the selector says so and shows no
  version.

  - Test: manual: browser run (2026-10-16)
  - Since: #254

- CAT-34c: `/compatibility/` MUST have the same table and selector over
  every listed version of every listed generator (CAT-26).

  The table follows the CAT-30 table under its own `h2`, with one row per
  listed version, named `<generator> <version>` and linked to its
  permalink, by generator name and newest version first. CAT-34a and
  CAT-34b apply to all rows at once: the nearest newer version is the
  nearest one any generator records, so a generator whose records name only
  older versions shows nothing there. Its own page answers for it alone.

  - Test: `catalog/test_catalog.py` (partial: as CAT-34a); manual: browser
    run (2026-10-16)
  - Since: #254

- CAT-34d: `docs/consumers.md` MUST document the fields of `catalog.json`
  that hold what a version is built for, with a jq example and a Renovate
  custom datasource recipe that filter them, and MUST state that
  `catalog.json` is unsigned and that the consumer workflow still verifies
  the digest (CON-2).

  Agents and Renovate need the lookup without parsing a page. The fields are
  `generators[].versions[]` with `version`, `digest`, `yanked` and
  `compatibility[]` (`software`, `version`, `source`). The signed
  `index.json` carries the same records, since `release/index.py` copies
  every `meta.json` key, but reading it takes an OCI fetch and an
  attestation check that a Renovate custom datasource cannot do.

  `catalog.json` is the site's view model (CAT-23), served by GitHub Pages
  without a signature. It is acceptable input because Renovate only
  proposes: the consumer workflow checks the digest against the attested
  index and fails a pull request whose digest is not listed or is yanked.
  The recipe returns `releases[].digest`, which Renovate's custom datasource
  hands on as the new digest for the regex manager's `currentDigest`, and
  disables the preset's docker lookup for that generator, so the two do not
  propose competing updates.

  A test runs the documented jq example against the fixture build's
  `catalog.json` and parses the recipe, so `catalog-tests`, which also runs
  on changes to `docs/consumers.md`, fails when either drifts from the
  fields.

  - Test: `catalog/test_catalog.py`; manual: Renovate dry run of the recipe
    against the live `catalog.json` (2026-10-16)
  - Since: #254

Related: CAT-15, CAT-30, CON-2.

- CAT-16: The site MUST publish `/llms.txt` in the llmstxt.org format, naming
  the marketplace's purpose and linking the author guide, the template and
  its `AGENTS.md`, the tags, the kinds (CAT-29), the compatibility page
  (CAT-30), the wanted page (CAT-31), the statistics page (CAT-33), the
  glossary, the gate's policy files,
  and the Markdown variant (CAT-28) of every generator with a listed version
  and of every guide.

  Coding agents asked to write a generator start there instead of guessing
  the gate's rules from the HTML; agents asked to use one find it in the
  list and read its Markdown variant instead of the page.

  The template `layouts/home.llms.txt` writes the file at build time as an
  output format of the home page; until this change it was a static file
  and named no generator. The fixed sections are written out in the
  template. The section "Generators" has one line `- [<name>](<index.md
  URL>): <description>` per generator and follows CAT-26; the section
  "Guides" has one line per guide with its description. "Optional" stays
  last, the proposal's convention for links an agent can skip. The
  proposal does not define `llms-full.txt`, and the site publishes none.
  The file links `/kinds/` (CAT-29), which names every kind with its
  generators, and no kind page, since those have no Markdown variant.

  The description comes from the submitter and is written as text on one
  line: whitespace runs become one space and the control characters of
  CAT-27 are removed. Markup in it is kept as typed.

  - Test: `catalog/test_catalog.py`
  - Since: #51, #231, #235, #242, #245, #251

- CAT-28: Every generator page and every guide MUST have a Markdown variant
  at `index.md` next to its `index.html`, and `sitemap.xml` MUST NOT list
  the variants.

  The llmstxt.org proposal puts a page's Markdown at the page's URL with
  `.md` appended, and at `index.html.md` or `index.md` for a URL without a
  file name. Hugo's built-in `markdown` output format (`text/markdown`,
  base name `index`, plain text) is enabled for `/generators/*` and
  `/guides/*` by a cascade in `hugo.toml`. The sitemap names the canonical
  HTML URL of each page, and `catalog/seo_check.py` (CAT-11d) reads only
  `.html` files, so neither sees the variants. GitHub Pages serves `.md` as
  `text/markdown`, which browsers do not render (checked on llmstxt.org, a
  GitHub Pages site, on 2026-10-15).

  The variant of a generator with a listed version has the name, the
  description as in CAT-16, the latest version and its date, its
  compatibility facts (CAT-30), owners, tags, the page's URL, the inventory
  entry and verify command of that version, and its README. Entry and command come
  from the partial the page uses, `_partials/commands.html`, so both show
  the same text. The README is the Markdown of `catalog.json` as the
  artifact carries it, not the filtered HTML of CAT-7: raw HTML and links
  with any scheme and shortcode delimiters stay in as typed, and a line
  names the base relative links resolve against. The variant of a generator without a listed version has
  the name, each version with its yank reason and the page's URL. A guide's
  variant is its title and its Markdown source with its shortcodes
  rendered; the diagrams of CAT-35a render as nothing there.

  - Test: `catalog/test_catalog.py`
  - Since: #231, #242, #257, #293

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
  first, linking its permalink (CAT-17). Titles and summaries in the
  feed pass through the control-character filter of `llms.txt`, so a
  description listed before QA-5a cannot make it invalid XML. The guides are articles for
  people deciding whether and how to write or consume a generator; they
  link the reference documents instead of repeating them.

  - Test: `catalog/test_catalog.py`
  - Since: #55, #232

- CAT-29: The site MUST list at `/kinds/` every Kubernetes kind of each
  generator's latest listed version, by API group and, for an apiVersion
  without a group, by version, each with links to its
  generators, labelled "rendered by" for kinds from the version's `kinds`
  record (PUB-10) and "schema shipped by" for kinds read from the SBOM of a
  version without that record.

  People look for a generator by what it renders, such as "which
  generator renders HTTPRoute?", and neither descriptions nor tags name
  kinds. The `kinds` record names what the fixture output renders, with
  the kind's case. Versions published before PUB-10 have no record; for
  them the kinds come from the attested SBOM (PUB-8), which lists every
  schema the version ships as `schemas/<group>/<kind>_<version>.json`
  (QA-7) and which the catalog job already holds for every listed version
  (CAT-14). A generator's kinds come from one source: the record when its
  latest listed version has one, the SBOM otherwise. A version without
  either, published before #47, has no kinds.

  A shipped schema is evidence of a kind the generator is meant to
  render, not that its fixture renders it, hence the separate label.
  Measured on 2026-10-15 on the fixtures of kadet-hub/generators at
  e4891e8: of 237 rendered combinations of group, kind and version, 232
  had a shipped schema; the other five are kind's `kind.x-k8s.io` Cluster
  and loki's four `loki.grafana.com` kinds, which ship no schemas. Of 297
  shipped schemas, 65 were not rendered by the fixture: 64 Talos config
  documents of talos and one kind of kserve.

  Only schema files directly under a group directory of `schemas/` count,
  the directory every generator with schemas names in its manifest. CRD
  files under `schemas/<group>/crds/` (QA-12) and `schemas/terraform/`
  (QA-8) are not counted; Terraform resource types are inside the
  extracts and the record holds only documents with `apiVersion` and
  `kind`, so Terraform generators have no kinds. File names carry the
  kind in lower case, so a kind known only from them shows as
  `httproute`. Group, kind and version from either source must match
  `[a-z0-9]` name patterns (`[A-Za-z0-9]` for a recorded kind), so neither
  can put a path segment or markup into a page. QA-7 files the schemas of
  every apiVersion without a group under `core`, the core group's `v1`
  as well as Talos machine config's `v1alpha1`, so the index splits that
  directory by version: `v1` is the section `core`, any other version a
  section named by the version, such as `v1alpha1`.

  - Test: `catalog/test_catalog.py`
  - Since: #235, #247

- CAT-29c: `/kinds/` MUST list the sections of the groups that the QA-10
  kube-apiserver serves without CRDs under "Kubernetes built-in APIs" and
  every other section under "Custom resources and other APIs", and MUST
  name a section's software there when the index names exactly one for
  it.

  Bare group names such as `apps`, `batch` or `policy` read like projects
  of their own, and the `k8s.io` suffix does not mean built in: Gateway
  API (`gateway.networking.k8s.io`) and the Vertical Pod Autoscaler
  (`autoscaling.k8s.io`) are CRDs. The built-in set is the one QA-10
  decides by discovery. The catalog job has no API server, so `BUILTIN`
  in `catalog/view.py` lists the 22 groups kube-apiserver v1.37.1 serves,
  with `core` for the core group. A test starts the QA-10 server in the
  sandbox image and compares its served groups with the list, so a
  Kubernetes bump in `sandbox/Dockerfile` that adds or removes a group
  fails gate-selftest until the list follows. Talos's `v1alpha1` is not
  served and lists among the other APIs, with the note that its
  apiVersion has no group.

  The index does not map a group to its software: the QA-7 result in a
  version's `compatibility` record names software, version and source of
  the schema groups the fixture used, without the group. A section is
  therefore labelled when each listed generator with kinds in it whose
  latest listed version names exactly one software other than
  `Kubernetes`, the source of the built-in schemas, names the same one; a
  generator that names two or more, such as kubernetes with Gateway API,
  GKE Managed Certificates and the Vertical Pod Autoscaler, labels none.
  The label is inferred: a generator that ships schemas of two custom
  groups but used only one in its fixture would lend that one's software
  to both. On the index of 2026-10-15 the rule labelled 25 of the 45
  other sections, each as the `sources.yaml` of kadet-hub/generators at
  e4891e8 names it; the other 20 belong to generators with two or more
  CRD sources and show the group alone. Labelling them needs the group in
  the QA-7 result.

  - Test: `catalog/test_catalog.py`, `sandbox/test_apiserver_check.py`
  - Since: #247

- CAT-29b: A kind that two or more listed generators render (PUB-10)
  MUST have a page at `/kinds/<section>/<kind>/` with each apiVersion, the
  cards of those generators and the generators that only ship a schema
  for it. No other kind has a page. Such a page MUST keep its URL while
  the kind has two or more such generators, and `sitemap.xml` MUST list
  it.

  The section is that of CAT-29: the group, `core` for `v1` without a
  group, the version for any other apiVersion without a group. A core
  kind keeps `/kinds/core/<kind>/`, and a kind of the same name in
  `v1alpha1` gets `/kinds/v1alpha1/<kind>/`, so the two never share a
  page. Within a named group a kind is one resource in every version, so
  its page lists each apiVersion.

  The URL takes the kind in lower case, so a page keeps its URL whatever
  case the record has. A page for one generator repeats that generator's
  page: with the SBOM kinds of 2026-10-15, 286 of 291 kinds had one
  generator. Kinds known only from a shipped schema do not count toward
  the two, so a page states only what the fixtures render. A page
  appears with the second generator that renders the kind and disappears
  when fewer than two do; the index links it while it exists, and Hugo's
  sitemap lists exactly the pages that exist. On 2026-10-15 no listed
  version had a `kinds` record, so the site had the index and no kind
  page.

  A page links no upstream API reference, because the schema sources of
  `sources.yaml` are not in the index per group (CAT-29c). The site
  navigation links `/kinds/`. Title and description stay within
  CAT-11 for any length of kind and group: the title drops its suffix and
  then the group, and the description is cut at 160 characters, so a long
  CRD group such as Crossplane's `insights.azure.upbound.io` cannot stop
  the deploy (CAT-11d).

  - Test: `catalog/test_catalog.py`
  - Since: #235, #247

- CAT-29a: The home page search MUST match the kind names (CAT-29) of
  each card's latest listed version, from either source.

  Search compares in lower case, so "HTTPRoute" finds the generators of
  every `httproute`, in any group. The search field says so in its
  placeholder, "Search <n> generators or kinds".

  - Test: `catalog/test_catalog.py` (partial: the search text in the
    markup; the matching runs in the browser)
  - Since: #235

- CAT-24: The guide "Writing a Kapitan generator" MUST have a section
  "Generator contract" at `#generator-contract` that states what `main()`
  receives and returns, how a target wires a generator, and the
  conventions for the inventory key, output file names and the
  precedence of defaults, `spec` and flat keys, and that links the gate
  requirements on imports, programs, network, determinism, output and
  schemas.

  Upstream has asked for this contract since 2023
  ([kapicorp/kapitan#975](https://github.com/kapicorp/kapitan/issues/975));
  the answer there links the anchor, so it stays stable like the URLs of
  CAT-5. The Kapitan behaviour the section states is that of the pinned
  0.36.3 (`kapitan/inputs/kadet.py`). The conventions are those of
  kadet-hub/generators, which the gate does not check. Gate rules are
  linked to their requirement, not restated, as CAT-18 has the guides do.

  - Test: `catalog/test_catalog.py`
  - Since: #157

- CAT-35: The guide "How kadet-hub works" at `/guides/how-kadet-hub-works/`
  MUST show the overview and the processes of listing, release,
  consumption, upstream update and withdrawal each as a diagram followed by
  a numbered list that states the same steps without it. Requirement IDs
  MUST appear only in the table of gate stages, linked to their spec
  section.

  The home page section of CAT-11b, the author and consumer guides and the
  incident runbook each describe one area. How the areas hand over (a tag
  becomes a Renovate bump, the bump runs the gate, the merge starts a
  release, the release a consumer pull request) was written down nowhere
  in one place. Readers of the catalog are not expected to know the
  requirement IDs, so the text names checks instead and the stage table
  links the IDs for those who follow up.

  - Test: `catalog/test_catalog.py` (`test_how_kadet_hub_works`)
  - Since: #257

- CAT-35a: Every diagram MUST be an SVG under
  `catalog/site/assets/diagrams/` rendered by Graphviz `dot` from the
  `.dot` file next to it, inlined into the page in a `<figure role="img">`
  named by a `<title>` and described by a `<desc>` in the SVG, and MUST
  contain no `<style>` element, `style` attribute, `<script>` element,
  event handler attribute or `href` to another document.

  The CSP (`style-src 'self'`) blocks a `<style>` element and a `style`
  attribute inside an inline SVG; presentation attributes and the rules
  of `style.css` for SVG classes apply. Inline, the diagrams take their
  colours from the tokens and follow both the system scheme and the
  toggle; an SVG loaded through `<img>` sees neither `style.css` nor
  `data-theme`. Graphviz writes presentation attributes only, turns
  `style=dashed` into `stroke-dasharray`, and passes a node's or edge's
  `class` through to its `<g>`; checked with Graphviz 14.1.4. Mermaid
  renders in the browser and would add a script; Hugo's GoAT sets `style`
  on its text elements (checked with Hugo 0.167.0); mermaid-cli and D2
  were not checked. A hand-written SVG would need a manual relayout on
  every process change.

  The SVG is committed as `dot` writes it, so neither CI nor the release
  needs Graphviz; `render` in the same directory regenerates every SVG,
  and each `.dot` names the Graphviz version that rendered it. CI does
  not re-render and compare: the runner image has no Graphviz, and another
  version changes the output without a change to the source (Graphviz
  16.1.0 moves coordinates in every one of the six SVGs). The test checks the constraints
  above on every committed SVG, which also catches a hand edit or another
  tool's output.

  Lines and arrowheads take `--text-muted`, text `--text`; a failure path
  takes `--warn`, is dashed and labelled "fails", so colour never carries
  the meaning alone. `pointer-events: none` keeps the `<title>` that
  `dot` writes for every node and edge from showing as a tooltip. Every
  diagram runs top to bottom and is at most 340 pt wide, so at a 360 px
  viewport it shrinks to the 328 px column with 12 pt labels at about
  12 px, and the page does not scroll sideways; the figure would scroll
  inside itself if a diagram outgrew the column. On wide screens a diagram
  keeps its natural size, at most 453 px wide.

  The shortcode `diagram` has a Markdown template that writes nothing, and
  the guide's Markdown variant renders shortcodes, so the variant (CAT-28)
  holds the text without the figures.

  - Test: `catalog/test_catalog.py` (`test_how_kadet_hub_works`,
    `test_diagram_svgs`); `test_seo` checks the page (CAT-11d); manual:
    the page in Chromium at 375 px and 1280 px, light and dark
  - Since: #257

- CAT-36: The site MUST have a blog at `/blog/` that lists every post
  under `catalog/site/content/blog/`, newest first with its date, and an
  Atom feed of the posts at `/blog/index.xml`. Each post MUST show its
  date and have a Markdown variant (CAT-28).

  Posts live on the site's own domain, so links to them count for
  kadet-hub.org and the SEO check (CAT-11d), sitemap and Markdown
  variants cover them without another build or deploy. A subdomain would
  need its own DNS record and deploy, and search engines rank it largely
  apart from the main site. A post appears here first; elsewhere it goes
  as an excerpt with a link, or as a copy that the other site keeps out of
  its index, which Google recommends since 2023 instead of a cross-domain
  canonical.

  The release feed at `/index.xml` (CAT-18) stays limited to published
  versions, so its subscribers get no posts; the blog and its posts
  announce the blog feed in their `<head>`. A post is a Markdown page with
  a `date`; it gets the `post` layout from the `/blog/*` cascade in
  `catalog/site/hugo.toml` and comes in through a maintainer pull request
  like a guide.

  - Test: `catalog/test_catalog.py`
  - Since: #271, #308

- CAT-36a: A post page MUST show a byline (author, publication date, an
  update date only when `lastmod` is later, reading time), the post's
  description as a lead, a contents list when the post has 800 words or
  more, a link on every heading, a copy button on every code block, links
  to discuss and edit the post, up to three related posts by shared
  `topics`, and the next older and newer post. The page MUST carry
  `BlogPosting` JSON-LD with headline, description, image, publication and
  update dates, and the maintainers as an `Organization` author, and
  `og:type` `article`. Body text MUST be 18 px with lines of at most 68
  characters; code blocks scroll sideways instead of wrapping.

  The choices follow published guidance rather than taste. Google asks
  for a visible, labelled date that matches `datePublished` and
  `dateModified`, a byline that leads to the author, and recommends
  `headline`, `image`, the dates and `author` for Article structured data
  ([publication dates](https://developers.google.com/search/docs/appearance/publication-dates),
  [Article](https://developers.google.com/search/docs/appearance/structured-data/article)).
  Readers scan: in Nielsen's study 79 % scanned, and concise, scannable
  text measured 124 % more usable
  ([NN/g](https://www.nngroup.com/articles/how-users-read-on-the-web/)),
  hence the lead, the contents list and the anchors. WCAG 1.4.8 sets lines
  of at most 80 characters and line height of at least 1.5. The author is
  the maintainers as an organization because the site names no person
  (the imprint is `tbd`).

  The heading link carries no text; CSS draws its "#". Medium's import
  copies text, so a "#" in the markup ended up after every imported
  heading (checked 2026-10-17).

  The update date comes from `lastmod` in the front matter, not from git,
  so a typo fix does not make a post look new. A post dated in the future
  stays out of the build until the daily release run (04:17 UTC, the
  schedule CAT-20 added to `release.yml`) on or after
  that date, which schedules posts without another mechanism. A queued
  article post is dated on the first day after the newest post that is
  not a Monday and has no post yet, so the blog gains one post a day;
  Mondays belong to the release posts (CAT-36b).
  The six posts queued for Tuesdays up to 1 December 2026 were instead
  published together on 21 October 2026, and so were the five posts on
  Helm chart patches queued for 22 to 27 October. Topics are
  front matter only; there are no topic pages, since `/tags/` belongs to
  the generator tags (CAT-18). A per-post Open Graph image, a newsletter
  and comments were left out: the first has no measured effect, the
  others need third-party code the CSP does not allow.

  Related: CAT-36, CAT-11d.

  - Test: `catalog/test_catalog.py` (`test_blog_post_page`)
  - Since: #272, #278

- CAT-36b: For every week from Monday 12 October 2026 in which at least
  one version was published and is not yanked, the blog MUST have a post
  dated the following Monday at `/blog/releases-<monday>/`, with one line
  per generator: its versions of that week, "new" when its first version
  is among them, and links to the generator page and to the CHANGELOG at
  the source commit of the newest of them. Below the lines, the post MUST
  show each generator's CHANGELOG sections of that week's versions, at most
  15 lines per generator, ending with a "Full changelog" link to that
  CHANGELOG when lines were cut.

  The post is generated at build time from the index, through the content
  adapter, so no one writes or commits it, and it enters the blog feed and
  the outreach pipeline like a written post. A week's post is dated after
  the week ends; Hugo leaves future-dated pages out, so a post appears
  complete with the first daily build on that Monday. Article posts do
  not share its day (CAT-36a). Grouping by generator keeps
  a week of upstream bumps to one line each. The week of 5 October, when
  the first 30 versions were imported, has no post; the launch post covers
  it.

  The sections come from the CHANGELOG.md in the artifact layer of the
  generator's latest listed version, which the catalog job pulls for the
  README (CAT-7) and which holds the earlier entries too. A version's
  section starts at a heading that names the version as QA-1 matches it,
  so 1.2.0 matches neither 1.2.0-rc.1 nor 11.2.0, and ends at the next
  heading of the same or a higher level; lines inside fenced code are not
  headings. `catalog.json` keeps the sections next to the README, and a
  build that reuses the README of an unchanged digest reuses them, so each
  layer is still pulled once (CAT-23). The 15 lines count over the week's
  versions, newest first; a cut inside a fenced code block closes the
  fence. A generator without CHANGELOG.md, without a section for the
  week's versions or whose layer was not read keeps its line only.

  Since the text is the latest version's, a later version that edits an
  older entry changes a published post, and the post of 12 October changed
  when the sections were added. Generated posts have no `lastmod`, so
  neither shows an update date (CAT-36a).

  The text is the generator author's, reviewed with the tree like the
  README, and is rendered like it: the control characters of CAT-27 are
  removed, raw HTML is omitted, the shortcode delimiters `{{<` and `{{%`
  are escaped so the text cannot call a shortcode, links and images
  resolve relative targets against the source commit, and every link
  carries `rel="nofollow ugc"`. A section's headings sit at least one level
  below the post's `h3` for the version and at most one level below the
  heading before them (CAT-11b), including headings nested in lists or
  written with underlines. The Markdown variant (CAT-28) carries the same
  text with the same heading levels where they are written with `#`, and
  keeps raw HTML as CAT-28 does for the README.

  - Test: `catalog/test_catalog.py` (`ReleaseDigest`)
  - Since: #280, #289

- CAT-36c: Every post page MUST link to sharing the post on LinkedIn,
  Bluesky, X, Hacker News and Reddit and to cross-posting it to dev.to,
  each link carrying the post's canonical URL and, where the network takes
  one, its title, URL-encoded. Other pages MUST NOT carry these links.

  The links are plain `<a>` elements with the values in the query string,
  so they work without JavaScript. They load nothing from the networks and
  set no cookie; a network learns of the post only when the visitor
  follows its link. Each opens in a new tab with `rel="nofollow noopener
  noreferrer"`: Google asks for `nofollow` on links it should not crawl
  from the site
  ([qualifying outbound links](https://developers.google.com/search/docs/crawling-indexing/qualify-outbound-links)),
  and every target is a compose form behind a login. They point to other
  origins, so the sitemap and the CAT-11d check do not see them, and the
  Markdown variant (CAT-28) does not carry them.

  Guides and recipes have layouts of their own and no share links; the
  weekly release posts (CAT-36b) are posts and have them.

  | Network | Link | Source, checked 2026-10-20 |
  |---|---|---|
  | LinkedIn | `https://www.linkedin.com/sharing/share-offsite/?url=<url>` | LinkedIn's documentation describes only the Share Plugin, which loads `platform.linkedin.com/in.js`; the URL redirects to LinkedIn's share form |
  | Bluesky | `https://bsky.app/intent/compose?text=<title> <url>` | [Action Intent Links](https://docs.bsky.app/docs/advanced-guides/intent-links) |
  | X | `https://x.com/intent/tweet?text=<title>&url=<url>` | [Web Intent](https://docs.x.com/x-for-websites/post-button/guides/web-intent), which does not name `intent/post` |
  | Hacker News | `https://news.ycombinator.com/submitlink?u=<url>&t=<title>` | [bookmarklet](https://news.ycombinator.com/bookmarklet.html) |
  | Reddit | `https://www.reddit.com/submit?url=<url>&title=<title>` | no current documentation; `GET_submit` in reddit-archive/reddit reads both, and reddit.com accepts them |
  | dev.to | `https://dev.to/new?prefill=<front matter and excerpt>` | `ArticlesController#new` and `Articles::Builder` in forem/forem |
  | Mastodon (CAT-36d) | `https://<server>/share?text=<title> <url>` | `render_initial_state` in mastodon/mastodon v4.7.3 |

  Hugo's `urlquery` encodes the values and writes a space as `+`, which
  query-string parsers read as a space; checked in the source for Bluesky
  (`URLSearchParams`) and for Arc's `urldecode`, which Hacker News runs on.

  dev.to has no intent for sharing a link: `/new?prefill=` opens its
  editor with a draft, after a sign-in. The draft is front matter with the
  title in double quotes, `published: false` and `canonical_url` set to the
  post, then the description and a link to the post, so the copy is an
  excerpt with a link (CAT-36). Forem's default editor reads only the title
  and the text after the front matter: the visitor sees the quotes and
  sets the canonical URL under the post's options. The Markdown editor
  with front matter reads all of it.

  The icons are inline SVG in `currentColor`, so they follow the theme:
  Bluesky, X, Hacker News (Y Combinator), Reddit, dev.to and Mastodon from
  Simple Icons 16.35.0 (CC0). Simple Icons no longer has LinkedIn; its
  "in" is drawn for this site. Every link is an icon button named by
  `aria-label`, such as "Share on X".

  - Test: `catalog/test_catalog.py` (`test_share_links`)
  - Since: #307

- CAT-36d: With JavaScript, a post page MUST offer sharing on Mastodon
  through a server the visitor enters, and MUST offer the browser's share
  menu when `navigator.share` exists.

  Mastodon has no central instance to link to. A form asks for the server,
  such as `mastodon.social`, accepts a host name only, and opens
  `https://<server>/share?text=<title> <url>` in a new tab. Mastodon's
  share page joins `title`, `text` and `url` into the draft; the link uses
  `text` alone. The server is kept in `localStorage` under `mastodon`,
  read and written in `try`/`catch` so blocked storage only means asking
  again; the privacy page names the key (LEG-1). A share service that
  picks the server for the visitor would put a third party between them
  and was left out.

  The share button hands title and canonical URL to `navigator.share`;
  closing the menu is not an error. Form and button are `hidden` in the
  markup and shown by `site.js`, so without JavaScript, or without the
  API, a visitor has the CAT-36c links.

  - Test: `catalog/test_catalog.py` (`test_share_links`; partial: the
    markup, the script runs in the browser); manual: the post in Chromium
    at 375 px and 1280 px, light and dark, sharing on Mastodon with a
    server entered and remembered, and the share button with
    `navigator.share` present and absent
  - Since: #307

- CAT-37: The site MUST have a page at `/recipes/<name>/` for every recipe
  of kadet-hub/examples and an index of them at `/recipes/`. A recipe page
  MUST show the Bitnami charts it replaces, its generators linked to their
  pages, the operators it needs, its inventory class, the compile classes
  and operator classes that class includes, the pins of those generators,
  what the examples CI asserts after deploying it, and a link to the
  recipe's folder. The site navigation MUST link `/recipes/`.

  A recipe is an inventory class that replaces one or more Bitnami charts
  with kadet-hub generators and is deployed and checked on a kind cluster
  by the examples CI (EX-5, EX-6). The page is where a reader copies it
  from, so the class, the compile classes and the pins are the files on
  the `main` branch of kadet-hub/examples at build time, and the page shows
  what that CI last checked. The lead is the comment at the top of the
  class. The generators are the `recipes.lib.<generator>` classes the class
  includes and the generators its `recipes.operators.<operator>` classes
  compile from `lib/<generator>`, such as mutate, which patches a chart
  and has no compile class of its own (EX-5a). The pins are the entries of
  `generators.yml` whose `output_path` is `lib/<generator>`.

  What the page states around the files lives in the front matter of
  `content/recipes/<name>.md`: title, description, the replaced charts,
  the operators and the check, taken from the Recipes table of the
  examples spec. A new recipe needs that page here; the build fetches only
  the classes of recipes that have one.

  As CAT-11a asks, every recipe title and the index title lead with the
  searched term and name Kapitan, such as "PostgreSQL on Kubernetes without
  Bitnami, with Kapitan", and every description leads with "Bitnami
  <chart> Helm chart alternative:" and names Kapitan with Kubernetes. A title that leaves no room for the " · kadet-hub" suffix
  within CAT-11's 65 characters stands alone; the template counts bytes,
  so the suffix's "·" counts twice.

  A page per recipe does not conflict with the single Bitnami guide of
  CAT-11a: each recipe page carries its own tested class, not the same text
  under another search term.

  Related: EX-5, EX-5a, EX-6 (kadet-hub/examples `docs/specs/examples.md`), CAT-11.

  - Test: `catalog/test_catalog.py` (`test_recipes`)
  - Since: #283, #299, #300

- CAT-37a: The build MUST fail when a file of CAT-37 cannot be fetched or
  is missing.

  `catalog/build` fetches `generators.yml`, the class of every recipe page
  and every compile and operator class those classes include from
  `raw.githubusercontent.com` with `curl -f`, as it reads the previous
  `catalog.json`, and copies them into the site's `assets/classes/`;
  the recipe templates stop the build with `errorf` when one is missing.
  The API lookups of the build degrade to a warning because the page
  stays usable without a star count or a README; a recipe page without its
  class has nothing to copy. A failed build stops the release's catalog
  job before the Pages upload, so the previous site stays live, as with
  CAT-11d. With `CATALOG_OFFLINE=1` the build reads the files from
  `$CATALOG_RECIPES/inventory/classes/`, laid out as in the examples
  repository's `recipes/` folder, so the tests use fixtures and a local
  checkout can be previewed.

  Hugo's `resources.GetRemote` would fetch from the templates instead. Its
  file cache keeps a fetched file without expiry unless `maxAge` is set,
  and the offline switch would need an environment variable allowed
  through `security.funcs.getenv`; the build script already owns network
  access and the offline fixtures. Neither variant uses `actions/cache`
  (GI-10).

  - Test: `catalog/test_catalog.py` (`test_recipe_file_missing_fails_the_build`)
  - Since: #283, #300

- CAT-37b: Every recipe page MUST have a Markdown variant (CAT-28) with
  the same facts and files, `/llms.txt` (CAT-16) MUST list it in a section
  "Recipes" after "Guides", and the Bitnami guide MUST link the recipe of
  every chart it names that has one.

  - Test: `catalog/test_catalog.py` (`test_recipes`, `test_llms_txt`)
  - Since: #283, #299

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

- CAT-32: Every generator page MUST have a `badge.json` next to its
  `index.html` in the shields.io endpoint schema, with the label
  `kadet-hub` and, as message and colour, the latest listed version and
  `blue`, or `not listed` and `lightgrey` for a generator without a listed
  version. `sitemap.xml` MUST NOT list it.

  A badge in the README of the source repository tells its visitors that
  the generator is listed and in which version, and links the page with
  its checks. The endpoint form was chosen over an image the build renders:
  shields.io draws the badge from the JSON when the README is viewed, so it
  follows a new version or a yank with the next catalog build, without a
  commit in the author's repository, and the site keeps serving only static
  files. A generator whose versions are all yanked keeps its page (CAT-5,
  CAT-26), so a badge in a README keeps resolving and says it is no longer
  listed.

  The schema is the one documented at
  `https://shields.io/badges/endpoint-badge` (read on 2026-10-15):
  `schemaVersion` 1, `label` and `message` required, `color` a named
  colour, `lightgrey` by default. Hugo writes the file as the output
  format `badge` (`application/json`, plain text), enabled for
  `/generators/*` next to the Markdown variant (CAT-28). The sitemap names
  only the HTML URL of each page, as for the variants.

  - Test: `catalog/test_catalog.py`
  - Since: #246

- CAT-32a: The page of a generator with a listed version MUST show the
  Markdown `[![kadet-hub](https://img.shields.io/endpoint?url=<badge.json
  URL>)](<page URL>)` in a disclosure "Badge" below the page's actions, as
  a snippet with a copy button (CAT-9), and MUST NOT load the badge image.

  The CSP admits images only from the site's own origin (CAT-3, CAT-25); a
  preview would need `img-src https://img.shields.io` and would send every
  visitor's address to shields.io. The snippet is text in `<pre><code>`.
  A section "Badge" after Versions was tried first: it is too short to
  reach the part of the viewport where the "On this page" list marks a
  section (CAT-19), so the list never marked it, and authors are the only
  readers who need it. A generator without a listed version has no
  disclosure, since its badge reads "not listed". `docs/authors.md` shows
  the snippet.

  - Test: `catalog/test_catalog.py`
  - Since: #246

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

  A failed Hugo build MUST print Hugo's error. `catalog/build` runs Hugo
  with `--logLevel error` and discards its statistics on stdout; with
  `--quiet`, Hugo 0.167 printed nothing and the job only exited 1.

  - Test: manual: fork rehearsal (2026-10-09); `catalog/test_catalog.py` (`test_recipe_file_missing_fails_the_build`, the error text)
  - Since: #16, #295

- CAT-2: A version page MUST show the inventory entry with version and
  digest, `source: ghcr.io/kadet-hub/<name>:<version>@sha256:<digest>`, and
  the CON-2 verification commands; a yanked version MUST show its reason and
  no inventory entry.
  - Test: `catalog/test_catalog.py`
  - Since: #16, #234

- CAT-3: Every HTML page MUST render every value from the index and the
  GitHub API through Hugo's contextual escaping and MUST NOT load scripts,
  styles or fonts from another origin.

  Description, tags, owners and the output diff text (CAT-27) come from
  submitters; a description or diff with markup is shown as text.
  `/llms.txt` (CAT-16) and the Markdown variants (CAT-28) are plain text,
  written without HTML escaping.

  - Test: `catalog/test_catalog.py`
  - Since: #16, #226, #231

- CAT-3a: The CSP MUST allow `connect-src 'self'`.

  Lighthouse fetches `/robots.txt` from inside the page. Under
  `default-src 'none'` with no `'self'` in `connect-src` that fetch is
  blocked, and Lighthouse fails its robots.txt audit with "Lighthouse was
  unable to download a robots.txt file". That cost 8 points of the SEO
  score, 0.92 instead of 1, and audit tools built on Lighthouse report it
  as an invalid robots.txt. Crawlers fetch the file directly and were
  never affected. The site's own scripts make no requests, so `'self'`
  opens nothing they use.

  - Test: `catalog/test_catalog.py`; manual: Lighthouse SEO category on a local build
  - Since: #321

- CAT-25: When `params.goatcounter` in `catalog/site/hugo.toml` names the
  origin of a GoatCounter instance, every page MUST count its view with
  `count.js` served from the site's own origin, and the CSP MUST allow that
  origin in `connect-src` and `img-src` and no other origin besides its
  own. Without the parameter the site MUST load no counter and the privacy
  page MUST say it runs no analytics.

  GoatCounter counts without cookies. kadet-hub runs its own instance,
  `https://stats.kadet-hub.org`, on a server at netcup, so page views
  reach no third party; the hosted
  goatcounter.com service would need an account there and was set aside
  for that reason. The hosted `count.js` would need
  `script-src https://gc.zgo.at` and break CAT-3, so the site ships a copy
  of it, which receives no updates by itself: `static/count.js` is
  `https://gc.zgo.at/count.js` byte for byte, with its ISC license under
  `static/licenses/`. The script sends the path, title, referrer and
  screen width with `navigator.sendBeacon`, or an image request where
  that fails, and reads `skipgc` from `localStorage` to skip the
  operator's own visits. The privacy page names the instance and what it
  receives. Cloudflare Web Analytics was considered; its beacon script is
  only served from `static.cloudflareinsights.com`.

  - Test: `catalog/test_catalog.py`
  - Since: #196

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

- CAT-13a: Every glossary entry MUST have a lowercase, hyphenated `id`
  that is unique on the page and stays stable once published, and the
  glossary MUST carry schema.org `DefinedTermSet` JSON-LD with one
  `DefinedTerm` per entry. Every entry MUST be linked from at least one
  other page of the site.

  The glossary defines Kapitan and its concepts first (inventory, class,
  target, interpolation, ref, kadet), then kadet-hub's own (generator,
  recipe, kind, custom resource and CRD, gate, server-side dry run, output
  capability, output diff, krab), then the supply chain (OCI artifact,
  digest, SBOM, provenance, attestation, index, yanked). A Kapitan concept
  links its page in the Kapitan documentation. Entries live in the front
  matter of `content/glossary.md`, so the list and the JSON-LD come from
  the same text; each `DefinedTerm` has the entry's name, its definition
  as plain text and its URL with the anchor.

  Guides, recipe pages and posts link the first use of a term in body
  text to `/glossary/#<id>`, not in headings, code or existing link
  text, and only where the word has the glossary's meaning: "kind" in
  "kind cluster" is the tool, not a Kubernetes kind. The glossary's title
  and description follow CAT-11 and CAT-11a and name Kapitan with
  Kubernetes; which terms the description names is a choice, not
  measured search volume.

  Related: CAT-11, CAT-11a, CAT-37.

  - Test: `catalog/test_catalog.py` (`test_glossary`)
  - Since: #286

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
  - Since: #18, #158
