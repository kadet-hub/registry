# Kapitan generator marketplace: Catalog

Status: Approved
Code: `catalog/`, `policy/tags.yaml`, `.github/ISSUE_TEMPLATE/`, `docs/authors.md`, `README.md`, `docs/consumers.md` (CAT-34d, CAT-34e, CAT-38b)
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
with the latest version's README and every version. The cards are listed
at `/generators/` (CAT-67a), and `/` is a start page (CAT-67). Search and tag filter run in the browser over the rendered cards.
Owner logins and stars come from the GitHub API at build time; they are
display data only, and a failed lookup shows the user ID or no stars.

A generator has no logo of its own: its card and its page show a cube,
teal where its tags name Terraform and indigo otherwise, the colours of
the start page's cargo (CAT-22). Submitters supply no images, so none needs to be checked. The
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
  JavaScript `/generators/` lists every generator.

  - Test: `catalog/test_catalog.py` (partial: the links and the markup; the
    filter itself runs in the browser)
  - Since: #45

- CAT-8a: Every tag shown on a card, a generator page or the tag overview
  MUST link to that tag's page `/tags/<tag>/`.

  Until this change the links went to the filtered home page. Audit tools
  flag internal links with query parameters, and the tag page (CAT-18)
  lists the same generators with the tag's definition; the filter chips
  on `/generators/` still combine tags.

  - Test: `catalog/test_catalog.py`
  - Since: #221

- CAT-9: Tables, long values outside code, such as a digest in a table,
  and, below 48rem, code blocks MUST wrap instead of scrolling
  horizontally.

  Below 48rem a line of code wraps between its tokens and hangs four
  characters under its own indentation. A token is a word, or a piece of
  a word longer than 24 characters cut after a slash, an `@`, a comma or
  a JSON key; it breaks only when it alone is longer than the line
  (CAT-9g). From 48rem code keeps its lines (CAT-9f).

  - Test: `catalog/test_catalog.py` (partial: the markup); manual: 375
    px, no code block scrolls sideways
  - Since: #45; code limited to below 48rem: #710

- CAT-9f: From 48rem a line of code MUST NOT wrap.

  A wrapped line of YAML or of a command reads as two. A block wider than
  its box scrolls sideways and says so with a "scroll" mark at its edge
  until its end shows; `site.js` sets the mark. The panels of CAT-9h fit
  their boxes instead.

  - Test: `catalog/test_catalog.py`
    (`Site.test_code_keeps_its_lines_from_48rem`: `pre` keeps
    `white-space: pre` from 48rem, and `site.js` marks a `pre` wider
    than its box)
  - Since: #710

- CAT-9g: A line of code MUST NOT break inside a token, unless the token
  alone is longer than the line.

  - Test: `catalog/test_catalog.py`
    (`Site.test_code_keeps_its_lines_from_48rem`: the token spans of the
    figure's and the generator page's panels); manual: 375 px, the
    figure and a generator page
  - Since: #711

- CAT-9h: At 1024 and 1440 px a code panel whose lines the site writes
  itself MUST NOT scroll sideways: the panels of the harbour figure
  (CAT-66), the panels of the live edit (CAT-68), and the Inventory and
  Verify panels of each listed version on a generator page (CAT-74).

  The site shortens the digests in these lines (CAT-64) and folds their
  commands at their flags (CAT-66n) until they fit. Every other code
  panel may be wider than its box, such as the badge snippet of CAT-32a,
  152 characters without a space for kubernetes, or code from a
  generator's README: from 48rem it scrolls sideways with the mark of
  CAT-9f, and below 48rem it wraps as CAT-9 and CAT-9g say.

  - Test: `catalog/browser.mjs` through `InChrome.test_rendered_pages`:
    every `pre` of these panels has no more width than its box at 1024
    and 1440 px
  - Since: #711

- CAT-9c: Every inventory entry and command outside the harbour figure
  and the live edit (CAT-66, CAT-68) MUST have a copy button.

  The figure and the live edit record one run, with prompts and output
  in one block, and nothing in them is meant to be copied. The commands
  a visitor runs stand on the generator pages (CAT-2) and in the
  quickstart (CAT-40).

  - Test: `catalog/test_catalog.py` (partial: the markup)
  - Since: #45; the exception for the figure and the live edit: not
    implemented

- CAT-9a: Below 48rem the site header MUST be one row with a menu button
  that opens the nav as a list below it.

  At 393 px, an iPhone 15, the ten nav links wrapped into four
  right-aligned rows and the header was 150 px tall; the eleven tag chips
  took five rows, and the sticky filters covered 354 px of a 660 px
  viewport, more than half of every scrolled screen. The menu follows
  GitHub's mobile header: brand, theme button, menu button; Escape closes
  the open menu. The filters scroll with the page; the search is at the top
  of the list, one scroll up. The start page's hero has no buttons
  (CAT-67).

  The menu button and the tag button of CAT-9d are added by `site.js`.
  Without JavaScript the nav and the chips stay open, so every link and
  tag remains reachable.

  - Test: `catalog/test_catalog.py` (`test_mobile_header_and_filters`,
    partial: markup and stylesheet); manual: 393 px viewport, the menu
    opens and closes
  - Since: #309

- CAT-9d: Below 48rem the tag chips of `/generators/` MUST be collapsed
  behind a "Filter by tag" button that counts the selected tags.

  - Test: `catalog/test_catalog.py` (`test_mobile_header_and_filters`,
    partial: markup and stylesheet); manual: 393 px viewport, the tag
    filter opens and closes
  - Since: #309 on `/`; at `/generators/`: #710

- CAT-9e: Below 48rem the filters of `/generators/` MUST NOT stay fixed
  while the visitor scrolls.

  - Test: `catalog/test_catalog.py` (`test_mobile_header_and_filters`:
    the rule `.filters { position: static; }`); manual: 393 px viewport,
    filters not sticky
  - Since: #309 on `/`; at `/generators/`: #710

- CAT-9b: The fact labels of a generator page, the check line of each
  version and the generator name of each row on `/compatibility/` MUST
  wrap only between words.

  CAT-9 rests on `overflow-wrap: anywhere` on `body`, which makes the
  smallest width of any box one character. A flex item or a column with a
  fixed share then shrinks to that width. On the live site at 375 px on
  2026-11-12, "Source" and "Image security" in the facts broke into
  pieces such as "So urc e", the check line under every version split
  into columns ("Checke d by the", 46 broken words on the `kubernetes`
  page), and the stacked rows of `/compatibility/` kept the 16 % width of
  the first column, so "argocd" showed as "argo cd". At 1280 px "Image
  security" still broke. Labels now keep their width, the check line is
  one block of text, and the stacked rows drop the column width. Digests
  and other long values still break anywhere.

  - Test: `catalog/test_catalog.py` (`Site.test_words_wrap_between_words`,
    partial: the stylesheet rules); manual: 375 px, no broken word on a
    generator page or `/compatibility/`
  - Since: #680

- CAT-54: Text MUST reach a contrast of at least 4.5:1 against its
  background in the light and the dark theme.

  4.5:1 is the WCAG 2.2 AA level for text below 24 px. It applies to all
  text here, since every pair of colour tokens reaches it; "Visual
  identity" lists the lowest pairs. The failures came from
  text faded with `opacity`. Measured in Chrome on the live site on
  2026-11-12, the version permalink "#" had 2.64:1 in light and 3.31:1 in
  dark, and the date of a yanked version 4.47:1 in light. The count in a
  selected tag chip had 4.34:1 in light and 4.33:1 in dark, calculated
  from the tokens and the rule's opacity. Text is therefore not faded. A
  yanked version is marked by its "yanked" pill and its reason. A
  disabled control stays faded, which WCAG exempts.

  Chrome's default placeholder grey has 3.71:1 on the dark field. On
  2026-11-13 the live site showed it in four fields: the home page
  search, the version field of the compatibility selector, the Mastodon
  server field under a post and the playground's parameter filter. Only
  the recipe finder's placeholder took `--text-muted`. The stylesheet now
  gives every placeholder `--text-muted`, which has 8.78:1 in light and
  7.59:1 in dark on `--surface`, the background of all six fields, the
  start page's search (CAT-67b) included.

  - Test: `catalog/test_catalog.py` (`Site.test_text_reaches_aa`,
    partial: the token pairs and the `opacity` rules of the stylesheet,
    not the rendered page; `Playground.test_placeholders_reach_aa`,
    partial: every field with a placeholder on the pages of the fixture
    build with the playground gets the rule, the field's background is
    not checked)
  - Since: #680; the ratios of the Harbour tokens: #710

- CAT-55: Every link and control MUST meet WCAG 2.2 success criterion
  2.5.8: a target of at least 24 by 24 px, or the space around a smaller
  one that the criterion allows.

  The popularity score on a card is a link of 16 by 22 px on top of the
  card's own link, and the version permalink, 18 by 25 px, sits inside
  the version's summary, which is a control too. Neither has the space
  the criterion allows, measured at 375 and 1280 px on 2026-11-12. Both
  now have a minimum size of 24 px. Links inside a sentence are exempt
  under the criterion.

  - Test: `catalog/test_catalog.py` (`Site.test_targets_reach_24px`,
    partial: the stylesheet rules of the two links); manual: 375 px, no
    link or control outside text below 24 px that overlaps another target
  - Since: #680

- CAT-10: `/generators/` MUST let visitors sort the cards by name, by the
  time of the latest version and by popularity score (CAT-23).

  Sorting by stars or 👍 alone was replaced by the score, which combines
  both with pulls; sorting by maintainer was considered and left out while
  every generator has the same one.

  - Test: `catalog/test_catalog.py` (partial: the sort keys in the markup)
  - Since: #45; at `/generators/`: #710

- CAT-11: Every page MUST have a title of 30 to 65 characters, a meta
  description of 50 to 160 characters, one `h1` and an absolute canonical
  URL; the site MUST publish `sitemap.xml` with every generator page and a
  `robots.txt` that names it.

  The length limits are the ones kapicorp/kapitan enforces for its
  documentation (`tests/test_docs_rendering.py`); here they are checked on
  the built HTML. Filtered views (`?tags=`, `?q=`) are `/generators/` and
  share its canonical URL. Generator pages carry schema.org
  `SoftwareSourceCode` as JSON-LD, which the CSP does not block because a
  data block is never executed. A generator description that leaves the
  title or description outside the limits is padded or cut by the
  template, not rejected at the gate.

  A generator page's title names what the generator writes, read from
  its tags: `<name> Kubernetes manifests from a Kapitan generator` for a
  generator tagged `kubernetes`, `<name> Terraform JSON from a Kapitan
  generator` for one tagged `terraform`. These are the outputs the gate
  checks as evidence for the two tags (CAT-13). Over 65 characters the
  title ends in "from Kapitan" instead, as for opentelemetry-operator. A
  generator with neither tag, or a name too long for both forms, keeps
  `<name> · Kapitan generator · kadet-hub` or, shorter,
  `<name> · Kapitan generator`, which has 59 bytes for the 39 characters
  REG-2 allows a name. The description stays the generator's own, which
  lists the resources it renders. calico's has 158 characters, so a
  sentence added by the template would cut it.

  The earlier title, `<name> · Kapitan generator · kadet-hub`, told a
  reader who knows Kapitan what the page is, and a searcher nothing about
  what they get. In Search Console, over the 90 days to 2026-11-20 with
  the site about five weeks old, five pages ranked in the top ten
  without a click:

  | Page | Impressions | Average position |
  |---|---|---|
  | `/generators/calico/` | 34 | 3.9 |
  | `/generators/cloudnative-pg/` | 21 | 6.8 |
  | `/guides/actions-runner-controller-dind/`, counted on its alias `/blog/actions-runner-controller-dind/` | 20 | 7.9 |
  | `/glossary/` | 11 | 6.5 |
  | `/generators/external-secrets/` | 10 | 6.9 |

  Most queries are anonymized. The known ones that reached generator
  pages name the software: "cloudnativepg", "kmcp", "prometheus
  operator", "kubevirt csi" and "cilium network policy generator". At
  these counts no click is a weak signal, and the new titles are not a
  measured fix. The guide and the glossary got new hand-written titles
  and descriptions in the same change (CAT-11f, CAT-13a).

  The title does not call a generator a Helm alternative. mutate patches
  a rendered chart and a generator tagged `helm` builds on one, so the
  claim would be wrong on their pages. For cloudnative-pg,
  "<name> Kubernetes manifests from Kapitan, a Helm alternative" would
  have 68 characters.

  - Test: `catalog/test_catalog.py`; generator titles:
    `Site.test_generator_titles_name_the_output`
  - Since: #45; generator titles that name the output: #725

- CAT-11a: The home page MUST have a title of 50 to 60 characters and
  MUST carry schema.org `WebSite` and `Organization` as JSON-LD.

  Audit tools such as SEOptimer score a home page title below 50
  characters as too short and look for an identity schema; the
  `Organization` names kadet-hub, its logo and the GitHub organization as
  `sameAs`, without an address or phone number, which the site does not
  publish.

  The home page's title, `h1` and description, and the titles of guides
  about Kapitan, name Kapitan together with Kubernetes or Terraform; only
  the home page is tested. The titles of other guides, of recipe pages and
  of generated pages (generator, tag, kind, release digest) lead with the
  searched term instead and name Kapitan where it fits; post titles follow
  CAT-11n. On its own,
  "kapitan" completes in search suggestions to a restaurant and a border
  crossing, and "kadet" to a car (checked 2026-10-17 with Google's and DuckDuckGo's suggestion endpoints);
  "kapitan kubernetes" and "kapitan generator" are unambiguous. Guide
  titles lead with the term searched for, such as "ingress-nginx Gateway
  API migration" or "Bitnami alternatives".

  A guide that compares named tools leads with them, "<A> vs <B>", also
  where CAT-11f records another query for it, as in "Argo CD vs Flux" or
  "cdk8s vs Tanka vs Kapitan". A guide that surveys alternatives leads
  with its query, as "Helm alternatives for Kubernetes" does, although its
  rows hold "vs" queries too. The words after the colon say what the
  reader gets from the page. Titles of guides, recipe pages and generator
  pages name that result, not an anecdote or a detail from the text that
  only makes sense after reading it.

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
  | helm alternatives kubernetes | home page, guide "Helm alternatives for Kubernetes that render the same app" |
  | kustomize alternatives | home page, same guide |
  | pulumi vs helm | same guide |
  | helm vs helmfile (also "helmfile vs helm"), helm chart vs helmfile, helm umbrella chart vs helmfile (checked 2026-10-22) | same guide, section #helmfile |
  | helmfile environments (also "helmfile environments example", "helmfile multiple environments"), helmfile secrets example, helmfile release needs (also "helmfile needs"), helmfile alternatives (checked 2026-11-05) | blog post "Helmfile vs Kapitan: per-environment values and release order", sections #environments, #secrets and #needs for the first three |
  | kubernetes multiple environments, helm multiple environments, helm values per environment, kustomize multiple environments (Google's suggestions, checked 2026-11-05) | blog post "Kubernetes multiple environments with a diff for every promotion", section #helm-kustomize for the last three |
  | cdk8s vs helm, cdk8s vs kustomize, cdk8s vs pulumi, grafana tanka vs helm | guide "Helm alternatives for Kubernetes that render the same app", guide "cdk8s vs Tanka vs Kapitan: which to pick for Kubernetes config" |
  | kustomize vs helm (also "helm vs kustomize"), kustomize vs helm charts, helm chart vs kustomize, helm template vs kustomize | guide "Helm vs Kustomize vs Kapitan: where each saves work on one app" |
  | helm vs kustomize vs jsonnet, helm vs kustomize vs terraform | guide "Helm vs Kustomize vs Kapitan: where each saves work on one app" |
  | bitnami alternative | guide "Bitnami alternatives, chart by chart" |
  | thanos helm chart not bitnami, thanos bitnami alternative, prometheus operator helm chart bitnami | guide "Bitnami alternatives, chart by chart" |
  | bitnami alternative postgres, cloudnativepg vs bitnami | guide "Bitnami alternative for Postgres: moving to CloudNativePG", `/recipes/postgresql/` |
  | bitnami alternative redis, bitnami alternative kafka | `/recipes/valkey/`, `/recipes/kafka/` |
  | postgres, redis, keycloak, rabbitmq or kafka helm chart without bitnami (also "not bitnami", "bitnami alternative"), valkey helm chart not bitnami | the matching `/recipes/<name>/` page, `/recipes/valkey/` for redis |
  | mysql helm chart not bitnami, bitnami mysql alternative, bitnami alternative mongodb | `/recipes/mysql/`, `/recipes/mongodb/` |
  | nextcloud helm chart, nextcloud helm chart bitnami (checked 2026-11-02) | blog post "Nextcloud Helm chart: Bitnami subcharts and Kapitan" |
  | kubernetes configuration management tools | guide "cdk8s vs Tanka vs Kapitan: which to pick for Kubernetes config" |
  | timoni kubernetes, timoni bundle (checked 2026-11-05) | blog post "Timoni vs Kapitan: CUE schemas and bundles pinned by digest" |
  | kcl kubernetes, kcl kubernetes example (checked 2026-11-05) | blog post "KCL vs Kapitan: typed schemas and locked modules on one app" |
  | external secrets operator vault (also "external secrets operator vault example", "external secrets operator vault approle"), external secrets operator rotation (checked 2026-11-05) | blog post "External Secrets Operator with Vault AppRole and Kapitan refs" |
  | ingress nginx retirement replacement, ingress nginx gateway api migration | guide "ingress-nginx Gateway API migration for Kapitan targets" |
  | kubectl dry run server side, kubectl dry run server vs client, kubeconform github action | guide "kubectl dry run server-side in CI on a bare kube-apiserver" |
  | kubeconform vs kubeval, helm lint vs kubeconform, kubelinter vs kubeconform (checked 2026-10-22) | same guide, section #kubeval-helm-lint-kube-linter |
  | kubectl wait for condition (checked 2026-11-02) | blog post "kubectl wait for condition fails on null conditions" |
  | kubectl validate crd | guide "kubectl validate CRD with a throwaway API server" |
  | kustomize json patch add, kustomize add annotation, service appprotocol, kubernetes trafficdistribution (checked 2026-10-21) | guide "Kustomize JSON patch add for nine fields charts leave out", one section per chart |
  | kustomize patch tolerations, kustomize patch nodeselector, kustomize patch add label, ipfamilypolicy requiredualstack, kubernetes service ipfamilypolicy, cilium ingress ipv6 (checked 2026-10-22) | same guide, sections #consul-hook-job-tolerations, #apisix-ingress-controller-pod-labels and #cilium-ingress-ipfamilypolicy |
  | cosign verify-attestation, gh attestation verify, slsa provenance attestations | guide "cosign verify-attestation vs gh attestation verify" |
  | docker tag and digest (also "docker tag digest"), docker image tag and digest (checked 2026-11-02) | blog post "Docker tag and digest: which one Kubernetes runs" |
  | docker compose and kubernetes, docker compose vs kubernetes (also "kubernetes docker compose"), miniflux docker compose, miniflux kubernetes (checked 2026-11-05) | blog post "Docker Compose and Kubernetes files compiled from one class", section #gaps for the second; `/recipes/miniflux/` also answers the last |
  | renovate automerge (also "renovate bot automerge", "renovate auto merge"), renovate automerge github (checked 2026-11-02) | guide "Renovate automerge with required reviews on GitHub" |
  | argocd config management plugin, argocd cmp plugin, argocd cmp sidecar, argocd sidecar plugin (checked 2026-11-05) | blog post "Argo CD config management plugin for Kapitan" |
  | open webui searxng (also "openwebui searxng", "openwebui searxng 403"), open webui web search searxng, open webui kubernetes, ollama + open webui kubernetes, searxng kubernetes (checked 2026-11-04) | blog post "Open WebUI with SearXNG web search and local Ollama models"; `/recipes/open-webui/` and `/recipes/searxng/` also answer the kubernetes queries |
  | self hosted google photos alternative (also "google photos alternative self hosted", "self hosted google photos replacement"), immich kubernetes (also "immich k8s"), immich kubernetes deployment, immich pgvector, immich reverse geocoding, immich smart search, immich backup database (also "immich database backup location"), immich backup and restore (checked 2026-11-05) | blog post "Self-hosted Google Photos alternative: Immich on Kubernetes"; `/recipes/immich/` also answers the kubernetes queries |
  | matrix synapse federation, matrix federation setup, synapse federation port, synapse well known (also "matrix synapse well known"), matrix synapse kubernetes (checked 2026-11-07) | blog post "Matrix Synapse federation: well-known delegation and TLS on 443"; `/recipes/matrix-synapse/` also answers the kubernetes query |
  | n8n queue mode (also "n8n queue mode kubernetes", "n8n queue mode worker"), n8n worker kubernetes (checked 2026-11-12) | blog post "n8n queue mode on Kubernetes: the webhook waits for a worker"; `/recipes/n8n/` also answers the kubernetes queries |
  | wordpress kubernetes, ah00072 make_sock could not bind to address (also "permission denied ah00072 make_sock could not bind to address 80"), ip_unprivileged_port_start (checked 2026-11-12) | blog post "WordPress on Kubernetes under Pod Security restricted"; `/recipes/wordpress/` also answers the first |
  | gvisor sandbox | guide "gVisor sandbox for untrusted pull request code on GitHub Actions" |
  | kyverno chainsaw, chainsaw test kubernetes, kubernetes e2e testing, kubernetes end to end testing, kind cluster github actions | blog post "Kyverno Chainsaw e2e tests that fail fast on a broken pod" |
  | kindest node (also "kindest node image", "kindest node images"), kindest node version, kind node image, kind node image version, kind custom node image, kind build node image, kind ensuring node image stuck (checked 2026-11-03) | blog post "kindest/node images: picking the version for your kind release", sections #kind-build-node-image for the custom and build queries and #ensuring-node-image-stuck for the last |
  | talos machine config, talos machine config example, talos machine config patch, talos machine config network, talos machine config schema | guide "Talos machine config for Kubernetes from a Kapitan inventory" |
  | talos homelab, talos network policy (also "talos linux network policy"), talos linux docker (checked 2026-11-05) | blog post "Talos homelab: machine configs and apps compiled together", sections #talos-network-policy and #talos-in-docker for the last two |
  | argocd vs flux (also "flux vs argocd", "argo cd vs flux") | guide "Argo CD vs Flux: sync time and drift handling measured" |
  | helm vs argocd, kustomize vs helm vs argocd, kustomize vs argocd | same guide |
  | kubernetes cluster add-ons (also "kubernetes cluster addons"), external secrets kubernetes provider (also "external secrets operator kubernetes provider"), velero s3 compatible storage (checked 2026-11-05) | blog post "Kubernetes cluster add-ons with one set of shared values", sections #external-secrets-with-the-kubernetes-provider and #velero-with-s3-compatible-storage for the last two |
  | gvisor vs docker (also "docker vs gvisor", "gvisor docker runtime") | guide "gVisor sandbox for untrusted pull request code on GitHub Actions", section #gvisor-vs-docker |
  | write your own helm chart, how to write helm charts, kube prometheus stack alternative (checked 2026-10-22) | guide "Writing a Helm chart vs Kapitan: three charts rebuilt", section #kube-prometheus-stack-alternative for the last |
  | helm chart vs operator, operator vs helm chart, kubernetes operator vs helm chart, k8s operator vs helm chart (checked 2026-10-22) | guide "Helm chart vs operator: PostgreSQL failover and config changes" |
  | helm vs terraform, helm chart vs terraform, kubernetes manifests terraform | guide "Helm vs Terraform for Kubernetes, and Kapitan for both" |
  | kustomize patch env variable, kustomize patch environment variable, kustomize patch add env var (checked 2026-10-21) | guide "Kustomize patch env variable with valueFrom by container name", sections #keda-http-add-on-env and #crossplane-env-secret |
  | patch helm chart, patch helm chart with kustomize, kustomize patch helm chart, helm patch chart, modify helm chart, edit helm chart | guide "Patch a Helm chart without forking it" |
  | kustomize delete resource, kustomize patch delete resource, kustomize remove resource (checked 2026-10-21) | guide "Kustomize delete resource: Kyverno PDBs and ESO webhooks", sections #kyverno-pdb and #external-secrets-webhooks |
  | helm post renderer, helm post renderer kustomize, helm post renderer argocd, kustomize helm charts, argocd kustomize helm, flux helmrelease postrenderer patch example | guide "Patch a Helm chart without forking it" |
  | kube prometheus stack dashboards, kube prometheus stack default dashboards, kube prometheus stack default grafana dashboards (checked 2026-10-21) | guide "kube-prometheus-stack default Grafana dashboards, one by one", section #disable-default-dashboards |
  | kustomize helm chart generator, kustomize render helm chart, kustomize enable helm, kustomize helm values file, kustomize helm argocd, render helm chart locally | guide "Patch a Helm chart without forking it", section "Kustomize with helmCharts" |
  | cert-manager helm chart, helm chart initcontainers, trust-manager helm chart, cert manager trust manager helm chart | guide "cert-manager Helm chart initContainers and trust-manager issuer" |
  | actions runner controller dind, github actions runner controller dind, gha runner scale set dind (checked 2026-10-21) | guide "Actions Runner Controller dind: override the hardcoded image", section #arc-dind-image |

  The two requests that guide answers, "cert-manager helm chart
  initcontainers" and "trust-manager custom issuer", complete in neither
  engine. Its sections keep the fixed anchors `#cert-manager-initcontainers`
  and `#trust-manager-custom-issuer`, so that a link to a section, from
  cert-manager/cert-manager#6071 or cert-manager/trust-manager#778 for
  example, stays valid when a heading changes.

  One page answers a query first, and its title leads with it, or, for a
  post, its title or description names it (CAT-11m). Other pages
  on the topic link to that page instead of competing with it. The
  Bitnami guide is that page for the generic query, the PostgreSQL guide
  for PostgreSQL, and `/recipes/` lists the tested recipes. The guide on
  Kapitan inputs is titled for that choice, so "helm vs kustomize" queries
  go to the guide that compares the tools on one app. CAT-11m checks the
  titles against the table.

  "kapicorp" is not a target: the people who search it know Kapitan
  already, and a page ranking for it could be taken for kapicorp's own.

  - Test: `catalog/test_catalog.py` (`test_home_identity_schema_and_title`)
  - Since: #284, #287, #288, #290, #291, #297, #298, #299, #304, #312, #313, #314, #315, #316, #318, #319, #320, #323, #324, #329, #331, #444, #539, #538, #556, #725

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

- CAT-11i: The site MUST serve the IndexNow key `9402a7122cd662ad840c013f9c6f7906` as
  `/9402a7122cd662ad840c013f9c6f7906.txt`, a file whose only content is the key.

  IndexNow lets a site tell Bing, Yandex and the other participating
  engines that URLs are new or changed, instead of waiting for a crawl.
  An engine accepts a submission only when the key it names is served
  from the same host. The key is public by design; it proves control of
  the host, not of an account. kadet-hub/outreach submits the URLs from
  `sitemap.xml` (OUT-14 there). A new key needs both places changed.

  - Test: `catalog/test_catalog.py` (`test_indexnow_key`)
  - Since: #325

- CAT-11j: A hand-written title MUST NOT set Kapitan against another tool
  by a contrast such as "without Helm, with Kapitan", "not with Helm",
  "Kapitan, not Helm", "instead of" or "rather than", and MUST NOT
  contain an en or em dash.

  Hand-written titles are the `title` of every page under
  `catalog/site/content/`: posts, guides, recipe pages and the pages of
  the site's sections. Titles a template or the content adapter writes
  (generator, tag, kind, release digest) are left to their template.
  Before this change 37 of the 55 recipe titles read "<name> on Kubernetes
  without Helm, with Kapitan" or "without Docker Compose, with Kapitan".
  A title names what the page shows; where the page compares tools, the
  comparison is in its text.

  - Test: `catalog/test_catalog.py` (`test_titles`)
  - Since: #651, #652, #653

- CAT-11k: Outside the searched term a hand-written title leads with, no
  three words in a row MUST appear in more than two hand-written titles.

  Many titles ended the same way: "from one Kapitan inventory" in three
  posts, "<name> on Kubernetes with Kapitan" in 18 recipe titles, and the
  stack posts with ", from Kapitan recipes" and ", tested on kind". The
  check compares lower-case words without punctuation. The searched term
  is the CAT-11f query a title leads with (CAT-11m), for a comparison its
  "<A> vs <B>" up to the first colon or comma (CAT-11a), and, for a recipe
  page, the software followed by "on Kubernetes" (CAT-37). It counts as
  one placeholder word, so the words right after different terms still
  count: three recipe titles that each go on with "with Kapitan" fail. A floor like this
  keeps the commonest repetition out; it does not make titles varied on
  its own, which stays a review question.

  - Test: `catalog/test_catalog.py` (`test_titles`)
  - Since: #651, #653

- CAT-11l: A colon followed by a list, with a comma and a final "and" or
  "or" after the colon, MUST NOT appear in more than three hand-written
  titles.

  "Helmfile vs Kapitan: environments, secrets and release order" was the
  shape four titles had before this change.

  - Test: `catalog/test_catalog.py` (`test_titles`)
  - Since: #651, #653

- CAT-11m: Every page the table of CAT-11f names by its title MUST carry
  exactly that title. A guide's title MUST lead with one of the queries of
  the rows that name it or, for a comparison, with "<A> vs <B>" (CAT-11a).
  A post MUST contain one of those queries in its title or its description.

  "Leads with" compares the words of query and title in lower case,
  without punctuation and without "a", "an", "the", "on", "in", "for",
  "with", "to" and "of", run together, so "Immich on Kubernetes" leads
  with "immich kubernetes", "Argo CD config management plugin" with
  "argocd config management plugin", and a plural with its singular.
  "Contains" compares the same way anywhere in the text. A post may lead
  with its point instead of the query (CAT-11n), and the description, the
  snippet search engines show under the title, carries the query then. A
  row that says "same guide" or "same post" names the page of the row
  above it. Before this change the table named four pages by a shorter
  form of their title, and three titles led with neither one of their
  queries nor a comparison, such as "kubectl server-side dry run in CI,
  without a cluster" for "kubectl dry run server side".

  - Test: `catalog/test_catalog.py` (`test_titles`)
  - Since: #651

- CAT-11n: A post's title MAY be pointed, opinionated or a teaser. Every
  claim it makes MUST be one the post itself proves.

  A post argues a point from what was built and measured, and a title
  that states the point gets read. A claim the text does not back would
  publish something unproven under kadet-hub's name. The contrast
  template of CAT-11j and the limits of CAT-11k and CAT-11l apply to
  posts as to every other title.

  - Test: manual: the review of the post checks each claim of its title
    against the text
  - Since: #651

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
  and is not checked; every post that moved to `/guides/` has one
  (CAT-36f).

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

- CAT-41: `/wanted/` MUST also list every open issue of kadet-hub/recipes
  with the label `recipe-request`, in a section of its own, with the
  fields, order and states of CAT-31. kadet-hub/recipes MUST have the
  issue form `.github/ISSUE_TEMPLATE/recipe-request.yml`, which sets that
  label and asks for the application, the Helm chart or Docker Compose
  file a recipe would rebuild, and why the requester needs it.

  A reader who looks for an application that has no recipe had no place
  to ask for one: the page took generator requests only.
  The form is in kadet-hub/recipes, where recipes are written and
  reviewed, as CAT-21 sends feature requests to the source repository. Its
  title starts with `[request] ` like the generator form's, so the page
  strips the same prefix.

  The catalog job reads the issues with the call of CAT-31 on
  `/repos/<owner>/recipes/issues?labels=recipe-request&state=open`. The
  repository is public, and the job's token already reads
  `/repos/<owner>/generators` for the stars, so the job needs no new
  permission. An offline build reads the list from
  `CATALOG_WANTED_RECIPES`. Each section has its own empty and unread
  state, so a failed lookup of one list leaves the other as it is.

  GitHub applies a form's label only when the label exists in the
  repository, so `recipe-request` has to exist in kadet-hub/recipes before
  the form is used.

  - Test: `catalog/test_catalog.py` (`Site.test_wanted_page`,
    `Site.test_wanted_page_without_requests`); manual: an issue opened
    with the form in kadet-hub/recipes carries `recipe-request`
  - Since: #540

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
  score or "secure" badge. The grade of CAT-39 rates the third-party
  images a version names, not these checks.

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
  other than tab and newline, and Bidi_Control). Its long lines follow
  CAT-9f from 48rem and CAT-9 below it.
  Beyond 150 lines the page says the text is truncated and links the
  download, which is the attested text unchanged.

  A version without a record was published before PUB-9 and says "No
  output diff recorded". A record with an error states the error; a
  record whose text does not verify says so.

  - Test: `catalog/test_catalog.py`; manual: fork rehearsal (pending)
  - Since: #226

- DEC-30: The container images that generators and recipes name, the
  KubeVirt CSI driver mirror among them, pass no gate. The catalog shows
  an Artifact Hub style security report of them instead, fed by the daily
  rescan (CAT-39, SEC-19). The maintainer decided three details on
  2026-10-29:

  - The catalog job holds `actions: read`, and the rescan's artifact is
    the report's only source (CAT-39c). Scanning in the release workflow
    would avoid the permission, but the report would no longer come from
    the rescan.
  - A reference by tag without a digest is scanned at the digest the tag
    points to on the day of the scan, and the page marks it "by tag,
    digest at scan time" (CAT-39a, CAT-39b).
  - The rescan also scans every recipe at `main` of kadet-hub/recipes. A
    recipe page without a listed version reports that scan and names the
    commit (CAT-39).

- CAT-39: Every generator page and every recipe page MUST show an image
  security report for the version the page shows: the number of findings
  per severity (CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN), the grade, the time
  of the scan and a link to the full report (CAT-39b). A page whose
  version has no scan result MUST say that it is not scanned, and a
  version that names no image MUST say so. Neither shows a grade. A recipe
  page with a grade MUST say next to it that the grade rates the upstream
  images the recipe pins, not the recipe, and MUST link each of these
  images to its page on Docker Hub, GitHub or Quay when it is published
  there.

  The report follows Artifact Hub's, as on its kube-prometheus-stack
  page. Artifact Hub counts every vulnerability Trivy lists in every
  result of every image of a package (`generateSummary` in
  `internal/scanner/scanner.go`). A finding is therefore one advisory in
  one package of one image, and the same advisory in two packages or two
  images counts twice. The grade is the letter of the most severe level
  with a finding: F for CRITICAL, D for HIGH, C for MEDIUM, B for LOW, `-`
  when only UNKNOWN findings are left, and A without findings
  (`SEVERITY_RATING` in `web/src/utils/data.tsx`, applied in
  `web/src/layout/common/SecurityRating.tsx`; artifacthub/hub at
  `1cd0160`). Both are adopted unchanged, with Artifact Hub's colours for
  the letters.

  The page names the counting unit, because unique advisories are fewer.
  Trivy 0.76.1 reported 65 findings, 34 of them HIGH, in the KubeVirt CSI
  driver mirror that kubevirt 1.3.2 pins, and 58 unique advisories, 31 of
  them HIGH, in the same scan on 2026-10-29.

  Artifact Hub stores no report for a package when one of its images
  fails to scan. A page with an image that could not be scanned therefore
  shows no grade and no counts. It says how many images failed and links
  the full report, which names the errors. A reference by tag whose
  manifest the registry does not know names no image and fails nothing
  (CAT-39a).

  The page shows the latest listed version (CAT-7, CAT-38), so the report
  covers that version. A recipe page without a listed version is built
  from `main` of kadet-hub/recipes (CAT-37c) and reports the rescan's
  scan of `main`, which names its commit, such as "main at
  21d393a22061". The catalog build resolves `main` again, so the page can
  show a later commit than the report.

  Readers took "grade F, 820 findings" on the Immich page for a grade of
  the recipe. The findings are in the two images Immich publishes, and
  only a new image fixes them. The full report says so, one click away,
  so the recipe page says it next to the grade. The Markdown variant
  (CAT-37b) carries the same line.

  An image without a registry host is on Docker Hub, as Docker resolves
  it. Its page is `https://hub.docker.com/_/<name>` for an official image
  under `library/` and `https://hub.docker.com/r/<repository>` otherwise.
  `https://ghcr.io/<repository>` redirects to the package page on GitHub,
  and `https://quay.io/repository/<repository>` is Quay's. The other
  registries the recipes use, `container-registry.oracle.com`,
  `docker.gitea.com` and `registry.k8s.io`, answered 404 at
  `https://<registry>/<repository>` on 2026-11-05, so their images are
  named without a link. On that day the full reports of the live recipe
  pages named 42 unique image references, 39 of them on Docker Hub,
  ghcr.io or Quay. A repository name with characters outside OCI's
  lowercase letters, digits and separators gets no link.

  - Test: `catalog/test_catalog.py` (`Security.test_report_on_the_pages`, `Security.test_recipe_at_main`, `Security.test_not_scanned`, `View.test_security_grade`, `View.test_security_of_the_shown_version`, `Security.test_upstream_images`, `View.test_image_registry_pages`)
  - Since: #417; the note on the upstream images: #540

- CAT-39a: The images of a version MUST be the references
  `<repository>:<tag>@sha256:<digest>` in its tree outside `tests/` and
  Markdown files, and the references `<registry>/<repository>:<tag>` in
  its Python files and its YAML files outside `schemas/` and `vendor/`,
  without the generator pins of REC-6. A reference by tag MUST be scanned
  at the digest the tag points to at the time of the scan.

  `scan/images.py` reads the tree the rescan already fetched (SEC-15,
  REC-14), so the list needs neither a compile nor network access. A
  recipe class file writes each image reference as one literal (RCP-66 of
  kadet-hub/recipes), which a pattern finds. Generator code builds
  references in Python, such as kubevirt's `SIG_STORAGE +
  "csi-provisioner:..."` and a literal split over two lines. The module is
  parsed with `ast`, and every string expression made of literals,
  module-level constants, `+` and f-strings is evaluated. Part of an
  expression that does not evaluate is no reference, so
  `"csi-provisioner:v6.0.2@sha256:..."` alone is not read as an image on
  Docker Hub. `tests/` holds fixture inputs and a recipe's
  `tests/values.yaml` the chart's images. Markdown documents images
  rather than naming them for a deploy.

  A reference by tag has no digest to tell it from other text, so it
  needs a registry host: `redis:7` is not read as one. Schemas and
  vendored CRDs name example images by tag, such as
  `ghcr.io/team/dashboards:v1` in the grafana generator's schemas, so tags
  are read only from code and class files. A tag the same tree pins by
  digest is that image, such as cnpg's `OPERATOR_IMAGE_NAME`, and is not
  listed twice.

  Strimzi's `kafka_image: quay.io/strimzi/kafka:1.3.0-kafka` is a prefix
  that the recipe completes with each Kafka version, and no registry
  serves it as an image. A reference by tag whose manifest the registry
  does not know (`MANIFEST_UNKNOWN`, Artifact Hub's `ErrImageNotFound`)
  therefore names no image: the full report lists it, and it does not
  block the grade. A reference by digest that fails still blocks the
  grade, as in Artifact Hub.

  The compiled fixture output holds the rendered references too. The
  rescan does not compile, and the release build does not record them, so
  versions published before such a record would have no list (CMP-4).

  `image_references()` takes the `{path: (executable, bytes)}` that
  `read_dir` and `read_tar` of `release/tree.py` return.

  On 2026-10-29 the function listed 18 references for the generators, the
  same 18 an audit made that day by means it did not record. 12 are by
  digest: kind's four `kindest/node` images, and kubevirt's mirror and
  seven `sig-storage` images. 6 are talos's references by tag, such as
  `registry.k8s.io/kube-apiserver:v1.37.1`. For the 16 recipes of
  kadet-hub/recipes at `21d393a` it listed 24 unique references, 20 by
  digest and strimzi's 4 by tag, 8 of them for the 5 recipes the registry
  lists. The audit also named 24 recipe references, but six of those are
  the `ghcr.io/kadet-hub/<generator>` dependencies of REC-6, which are
  generator artifacts rather than images. It missed miniflux's
  `miniflux/miniflux` and `postgres`, which have no registry host, and
  strimzi's references by tag.

  The KubeVirt CSI driver mirror (PUB-13) has no page of its own. It is
  scanned as an image of kubevirt, which pins it. A mirror tag that no
  listed version pins is not scanned.

  - Test: `scan/test_images.py`; `catalog/test_catalog.py` (`Security.test_by_tag`)
  - Since: #417

- CAT-39b: The site MUST have a full report at
  `/security/generators/<name>/` or `/security/recipes/<name>/` for every
  page with an image to report. It MUST list each image with its findings
  per severity and every finding with its advisory ID, severity, package,
  installed version and fixed version, or the error of an image that could
  not be scanned. An image named by tag MUST be marked "by tag, digest at
  scan time" with that digest.

  The columns are those of Artifact Hub's report table. IDs, package names,
  versions and errors come from the images and the vulnerability database,
  so they go through Hugo's escaping (CAT-3) with control characters
  removed. Findings are sorted by severity, then by ID. On 2026-10-29
  kind's four images had 3,565 findings and the nextcloud image 2,596, so
  the report is a page of its own and stays out of the catalog page and
  `catalog.json`. A report of `main` names the full commit. A recipe at
  `main` without a page in the catalog gets no report page, because no
  page would link it.

  - Test: `catalog/test_catalog.py` (`Security.test_full_report`, `Security.test_by_tag`, `Security.test_recipe_at_main`, `Security.test_seo`)
  - Since: #417

- CAT-39c: The catalog job MUST read the image report of the newest run
  of `scheduled.yml` on `main` that uploaded one, and MUST build the pages
  as not scanned when it reads none.

  The scheduled workflow has no publishing rights (GI-8). It uploads the
  report as the artifact `security-report` (SEC-19), kept for seven days.
  `catalog/build` lists the last seven runs with `gh run list --workflow
  scheduled.yml --branch main` and downloads the artifact of the first run
  that has one. Reading another run's artifacts takes `actions: read` on
  the catalog job (DEC-30). Runs on other branches are not read, so a
  workflow pushed to a branch cannot supply the report.

  The rescan is scheduled six minutes after the release, but GitHub starts
  scheduled runs late: from 2026-10-27 to 2026-10-29 both started between
  09:52 and 10:58 UTC, the rescan two minutes after the release. The
  catalog shows the newest report that was finished when it was built,
  and each page shows the time of its scan.

  The report is a claim of the scheduled job and carries no attestation.
  An exploit of Trivy's image parsing in that job can change the counts
  and grades the site shows as text, and nothing else.

  With `CATALOG_OFFLINE=1` the build reads the report from
  `$CATALOG_SECURITY`.

  - Test: `catalog/test_catalog.py` (`Security.test_build_reads_the_newest_report`, `Site.test_pages_without_image_report_say_not_scanned`)
  - Since: #417

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

- CAT-22: Every card MUST show the same fields in the same order: its
  cube, the name as the only card-wide link with the owners' logins under
  it, the latest version as a pill beside them, the description clamped
  to three lines, the tags, "Built for" with one chip per software and
  version (or "Built for: not recorded"), and a foot with the date of the
  latest version, the scan date (or "Not scanned") and the popularity
  score of CAT-23, linked to its explanation.

  Users read the top left first and scan the first words of lines (NN/g);
  attributes that appear on some cards and not on others make a catalog
  look smaller and are hard to compare (Baymard), so missing values are
  stated instead of omitted. License and the note that stars are shared
  by several generators move to the generator page, where there is room
  to explain them. The version stands at the end of the card's head, in
  the same place on every card whatever the length of the name. Each fact
  in the foot carries its label. A generator built for several products,
  such as cert-manager with trust-manager, gets a chip for each, and a
  chip wraps as a whole. The cube is teal where the tags name Terraform
  and indigo otherwise, the colours of the start page's cargo. The name
  link stretches over the card and the tag and popularity links sit above
  it, the block-link pattern recommended by Heydon Pickering and Adrian
  Roselli; the focus ring is drawn when the name link has keyboard focus,
  not when a tag link does.

  - Test: `catalog/test_catalog.py`
  - Since: #73, #81, #92, #230; the Harbour card: #710

- CAT-26: A generator without a listed version MUST NOT have a card on
  `/generators/` or a tag page.

  Every version of a removed entry is yanked with the reason `entry
  removed`, and the index keeps them. Their card read "no listed version,
  all yanked" and looked like a second generator next to the one it was
  merged into, as calico-resources did beside calico. The generator page
  stays at its URL (CAT-5) and shows the reasons; the popularity page
  keeps its row, which that page links to.

  - Test: `catalog/test_catalog.py`
  - Since: #224; `/generators/`: #710

- CAT-26a: A generator without a listed version MUST NOT be counted on
  `/generators/`, a tag page or the start page (CAT-67).

  - Test: `catalog/test_catalog.py` (the counts of the tag filter and of
    the tag pages; the start page's count in `Site.test_start_page` of
    the implementation)
  - Since: #224; `/generators/` and the start page: #710

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

- CAT-34e: `docs/consumers.md` MUST document the `kinds` and `sections`
  fields of `catalog.json` with a jq example that looks up the generators
  rendering a kind, and MUST state that the keys of `kinds` are the
  sections of CAT-29, not API groups.

  A tool that reads `kinds` as keyed by API group finds a key `v1alpha1`,
  which is no group. It is the section of Talos machine config, whose
  apiVersion `v1alpha1` has no group (CAT-29, CAT-29b). The doc names the
  rule: the API group, `core` for `v1` without a group, the version for
  any other apiVersion without a group. Below a section, kinds are keyed
  in lower case, and each entry holds `name`, `rendered`, `schema`,
  `versions` (apiVersion to generators) and `page`. `sections` splits the
  section names into `builtin` and `custom` (CAT-29c).

  A test runs this jq example against a fixture build with a core
  `ConfigMap` and a Talos `v1alpha1` `ConfigMap` and expects one line per
  section.

  - Test: `catalog/test_catalog.py`
  - Since: #335

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
  description listed before QA-5a cannot make it invalid XML. The guides
  (CAT-36e) link the reference documents instead of repeating them.

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
  name a section's software there when the `schemas/sources.yaml` (QA-7)
  of the generators with kinds in it names exactly one for its group.

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
  the schema groups the fixture used, without the group. The artifact
  holds the map. QA-7 requires a `sources.yaml` entry for every schema group, and
  the catalog job already fetches the artifact layer of each generator's
  latest listed version for its README (CAT-7). For a kind of that
  version the software is the `software` of the entry
  `<group>/<version>` if the file has one, else of `<group>`, so
  `core/v1alpha1` names Talos for the `v1alpha1` section. A section is
  labelled when its generators name exactly one software other than
  `Kubernetes`, the source of the built-in schemas. kubevirt thus labels
  `snapshot.storage.k8s.io` with Kubernetes CSI external-snapshotter and
  `cdi.kubevirt.io` with KubeVirt Containerized Data Importer (CDI), and
  certmanager labels `trust.cert-manager.io` with trust-manager.

  A group without an entry names nothing, and neither does a generator
  whose layer the build could not fetch, so such a group shows alone
  unless another generator names it. Before #370 the label was
  inferred from `compatibility` when it named one software other than
  `Kubernetes`. That lent the software of one used group to every group
  of the generator, and the generators with two or more CRD sources left
  all their groups bare.

  `view.py` uses the standard library only, so it reads `sources.yaml`
  in the block form every listed one has: an entry key at the start of a
  line and `software: <name>` two spaces in below it. A file with a
  top-level line or a `software` line in another form names nothing, so
  a misread file leaves its groups bare and never lends a name to the
  wrong group. `catalog.json` keeps each generator's map as `sources`,
  and the build pulls a layer again only when the previous build has no
  `sources` for its digest (CAT-23).

  Measured on 2026-10-25 on the index of serial 61 and the layers of its
  latest listed versions: the rule labels all 47 other sections, 25 with
  the name the inference gave them and 22 that the inference left bare.

  - Test: `catalog/test_catalog.py`, `sandbox/test_apiserver_check.py`
  - Since: #247, #370

- CAT-29d: Under "Custom resources and other APIs" (CAT-29c), `/kinds/`
  MUST group the sections by domain, the last two DNS labels of the group,
  and MUST sort the domains and, within a domain, the groups alphabetically.
  A domain with one group MUST keep that group's heading. A domain with two
  or more groups MUST have an `h3` heading with the domain and an `h4`
  heading per group. Every group MUST keep its anchor `#<group>`, and a
  domain with two or more groups MUST have the anchor `#domain-<domain>`.

  A project often ships several API groups, such as KubeVirt's
  `kubevirt.io`, `cdi.kubevirt.io` and `pool.kubevirt.io`, and a flat list
  of the groups scatters them. The domain heading names the software of
  its groups (CAT-29c), each name once and joined with `, `, and the group
  headings below it carry no name. `autoscaling.k8s.io`,
  `gateway.networking.k8s.io` and `snapshot.storage.k8s.io` share
  `k8s.io` and stay in this section, since built in is what CAT-29c
  decides, not the suffix. A section without a dot, such as `v1alpha1`, is
  its own domain. A domain with one group sorts by the domain, so
  `k8s.cni.cncf.io` stands among the `c` domains. The rule does not
  consult the public suffix list, and no listed group has a suffix such as
  `co.uk`.

  The domain anchor has the `domain-` prefix because the domain is often a
  group as well, such as `kubevirt.io` or `cert-manager.io`, and the anchor
  of that group has existed since CAT-29. The grouping is done by the
  template. The `kinds` and `sections` fields of `catalog.json` stay as
  CAT-34e documents them, and the kind pages keep `/kinds/<group>/<kind>/`
  (CAT-29b).

  - Test: `catalog/test_catalog.py`
  - Since: #369

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

- CAT-29a: The search of `/generators/` MUST match the kind names (CAT-29) of
  each card's latest listed version, from either source.

  Search compares in lower case, so "HTTPRoute" finds the generators of
  every `httproute`, in any group. The search field says so in its
  placeholder, "Search <n> generators or kinds".

  - Test: `catalog/test_catalog.py` (partial: the search text in the
    markup; the matching runs in the browser)
  - Since: #235; at `/generators/`: #710

- CAT-29e: The search of `/generators/` MUST match the software names the card
  shows under "Built for", from the latest listed version's
  `compatibility` (CAT-15).

  A card that says "Chainsaw 0.2.15" has to come up for "chain". Before
  this, only the name, the description and the kinds were searched, so
  the kubernetes generator, which writes Chainsaw step templates but
  names Chainsaw only under Built for, did not.

  - Test: `catalog/test_catalog.py::test_search_matches_built_for`
  - Since: #421; at `/generators/`: #710

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

  The diagrams carry classes and no colour; `style.css` colours the
  classes. The normal flow is indigo: nodes on `--accent-bg` with an
  `--accent` edge, lines and arrowheads in `--accent`, text in `--text`.
  An attested or signed result is teal, on `--teal-bg` with a
  `--teal-line` edge. A failure path or a stop is orange, on `--signal`
  lines and `--signal-bg` nodes with `--signal-text`, and also dashed and
  labelled, so colour never carries the meaning alone. A cluster stands
  on `--bg-subtle` with its label in `--text-muted`. Nodes have rounded
  corners. `pointer-events: none` keeps the `<title>` that
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

- CAT-35b: Every diagram MUST be rendered by `assets/diagrams/render`,
  which measures its labels in Manrope Medium.

  The six diagrams share their look in this one script: node, edge and
  graph settings, rounded nodes, 12 pt labels in Manrope Medium. `dot`
  measures the labels with Pango, which reads no WOFF2, so `render` takes
  the TTF the site's WOFF2 is cut from (CAT-60), checks its SHA-256 and
  shows it to fontconfig for the run only. Without the font `dot` falls
  back to another face without failing, and the boxes no longer fit
  their text, so `render` fails when its log does not name Manrope
  Medium.

  - Test: `catalog/test_catalog.py` (`Diagrams.test_diagram_svgs`: every
    `.dot` names the Graphviz version that rendered it and holds no
    colour); manual: `render` run in the merge request
  - Since: #711

- CAT-35c: A label of a diagram MUST NOT touch a line, a node or another
  label.

  `dot` has no setting for it, so the `.dot` files hold what keeps text
  off lines: an edge label carries three spaces on either side, since
  `dot` reserves the label's box next to the edge; nodes of one flow
  share a group, which keeps the flow straight; where several steps fail
  into one outcome, each step has a point on its rank and the points form
  one dashed line that carries the label once; a cluster's label stands
  on the side where no edge enters the cluster.

  An edge label and a cluster label keep at least 4 pt from every edge
  line and arrowhead, every node outline and every other label, measured
  on the box of their glyphs in Manrope Medium at the diagrams' 12 pt. A
  node label lies inside its own node's outline. In the six diagrams of
  the preview build, measured in Chrome 156 on 2026-11-22, the closest
  gap is 4.69 pt, between "passes" and its own edge in `upstream.svg`,
  and every node label stands at least 6 pt inside the box of its node.

  - Test: `catalog/browser.mjs` through `InChrome.test_rendered_pages`:
    in every SVG of the guide, these 4 pt around each edge and cluster
    label, measured to the lines' centre, and each node label inside its
    node's outline
  - Since: #711

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

- CAT-36e: An article that has to stay correct while the tools it covers
  change, such as a comparison, a how-to or a migration, MUST be a guide
  under `/guides/`. A post MUST have an occasion: a stack walkthrough
  (CAT-45), a release (CAT-36b), a finding or an announcement. An article
  MUST appear as a post first and MAY move to `/guides/` only once its date
  has passed and kadet-hub/outreach has published it on dev.to and
  Bluesky.

  A guide is maintained. It carries `lastmod` (CAT-11g) and no `date`, and
  a change in a tool it covers changes its text. A post stays as it was on
  its date, and its `lastmod` marks corrections only (CAT-36a). Which one
  an article is follows from its text, not from its title. A comparison
  measured once is still a comparison: readers come to it from a search
  for the comparison, and a result that no longer holds misleads them for
  as long as the page is up.

  The blog feed is what kadet-hub/outreach publishes on dev.to (OUT-1
  there) and links on Bluesky (OUT-23 there), and the daily schedule of
  CAT-36a is built from queued posts. A guide is in neither, so an
  article that started as a guide would never reach dev.to or Bluesky,
  and moving a queued post would leave its day empty. A post is on dev.to
  when a closed issue labelled `devto` in kadet-hub/outreach names its URL
  (OUT-4 there), and on Bluesky when a closed issue labelled `bluesky`
  does (OUT-25 there).

  On 2026-11-07, 16 of the 40 posts moved to `/guides/` by this rule.
  Ten more are guides by their text and stay posts until both conditions
  hold: eight were queued for 12 to 22 November 2026, and two were not on
  dev.to yet. `nextcloud-helm-chart-bitnami`, one of those two, moved on
  2026-11-10. Among the posts that stay for good, `chainsaw-kind` and
  `docker-tag-and-digest` report what the examples CI and the recipes ran
  into at the time, and `kubectl-wait-null-conditions` one failure on one
  day.

  Related: CAT-18, CAT-36a.

  - Test: `catalog/test_catalog.py` (`test_moved_posts`, partial: dates
    and layouts; which article is a guide is a review question); manual:
    the closed `devto` and `bluesky` issues for the post's URL before it
    moves
  - Since: #650, #665, #666

- CAT-36f: A post that moves to `/guides/` MUST keep its URL
  `/blog/<name>/` as a Hugo alias whose page redirects to the guide at
  once, with `content="0; url=<guide URL>"`, and its Markdown variant
  `/blog/<name>/index.md` (CAT-28) as a stub that links the guide and the
  guide's variant by absolute URL. Both MUST stay.

  GitHub Pages has no server-side redirects, so the redirect is the page
  Hugo writes for each entry of `aliases`: a meta refresh of 0 seconds and
  a canonical link to the guide, from Hugo's built-in alias template
  (checked with Hugo 0.168.0). The site has no alias template of its own. Google reads an instant meta refresh as a
  permanent redirect and a delayed one as temporary ("Google Search
  interprets instant meta refresh redirects as permanent redirects",
  [Redirects and Google Search](https://developers.google.com/search/docs/crawling-indexing/301-redirects)).
  For a site move it asks to keep redirects "for as long as possible,
  generally at least 1 year"
  ([site moves](https://developers.google.com/search/docs/crawling-indexing/site-move-with-url-changes)).
  The aliases stay without an end date, because the READMEs in
  kadet-hub/examples and the dev.to copies link the old URLs, and an
  alias is one small file.

  Hugo leaves alias pages out of `sitemap.xml`, so the sitemap names the
  guide only, and CAT-11d skips them as redirects.

  Hugo renders aliases only for HTML output formats, so the old `index.md`
  needs a file of its own (`pageRenderer` in `hugolib/site_render.go`,
  Hugo 0.168.0). The guide's Markdown template `prose.markdown.md` writes
  one per entry of `aliases` with `resources.FromString` and `.Publish`,
  so the next move needs no list kept by hand. The stub has the guide's
  title and the absolute URLs of the guide and of its variant. It leaves
  out the guide's text, so there is no second copy to index. A published
  resource is not a page, so `sitemap.xml` and `llms.txt` (CAT-16) do not
  list it.

  - Test: `catalog/test_catalog.py` (`test_moved_posts`)
  - Since: #650, #654

- CAT-36g: A page of the site that links a moved post MUST link the
  guide's URL.

  The site-move guidance asks to change internal links to the new URLs,
  so a reader on the site does not pass through a redirect. Links from
  other repositories, such as the READMEs in kadet-hub/examples, reach
  the guide through the alias.

  - Test: `catalog/test_catalog.py` (`test_moved_posts`, partial: the
    content and layouts of this repository, not READMEs and descriptions
    the build fetches)
  - Since: #650

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
  stays out of the build until the first scheduled release run on or
  after that date (CAT-36h), which schedules posts without another
  mechanism. A queued
  article post is dated on the first day after the newest post that is
  not a Monday and has no post yet, so the blog gains one post a day;
  Mondays belong to the release posts (CAT-36b).
  The six posts queued for Tuesdays up to 1 December 2026 were instead
  published together on 21 October 2026, and so were the five posts on
  Helm chart patches queued for 22 to 27 October. Topics are
  front matter only; there are no topic pages, since `/tags/` belongs to
  the generator tags (CAT-18). A newsletter and comments were left out,
  because they need third-party code the CSP does not allow.

  Each post has its own Open Graph image (CAT-58), although no
  measurement shows that it brings more clicks than one image for the
  whole site. Buffer's 2026 data compares post formats by interactions,
  not clicks, and no published test compares a per-post image with a
  generic one ([Buffer](https://buffer.com/resources/data-best-content-format-social-media/)).
  The reason is the feed. The blog publishes a post a day, and every
  share on Mastodon, LinkedIn, Threads and dev.to showed the same
  `og.png`, so a reader could not tell two posts apart. The effect is
  checked with GoatCounter's referrers (CAT-25) per network, over the
  four weeks before and the four weeks after the first deploy with the
  cards. Growth of the site and the mix of posts in both periods
  confound that comparison.

  Related: CAT-36, CAT-11d.

  - Test: `catalog/test_catalog.py` (`test_blog_post_page`)
  - Since: #272, #278

- CAT-36h: `release.yml` MUST run on two daily schedules, at 04:17 and
  10:47 UTC.

  GitHub starts scheduled workflows late under load and sometimes not at
  all. On 11 and 12 November 2026 the 04:17 run had not started by 05:00,
  and on 11 November the day's post went out only after a manual
  dispatch. The second run publishes a post dated that day when the first
  is missing. Like every release run, it also runs the publish jobs, which
  push only a version that no earlier run published (PUB-2). When both
  runs succeed, the second publishes nothing, builds the same site again
  and refreshes the counts of CAT-20.

  - Test: `catalog/test_catalog.py` (`Schedule.test_two_daily_runs`)
  - Since: #674

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

- CAT-53: Every page MUST carry `<link rel="me"
  href="https://hachyderm.io/@kadethub">` in its `<head>`. Every post page
  MUST also carry `<meta name="fediverse:creator"
  content="@kadethub@hachyderm.io">` there.

  `@kadethub@hachyderm.io` is the project's Mastodon account. Mastodon
  shows a link in a profile's metadata as verified when the linked page
  has an `a` or `link` element with `rel="me"` whose `href` is the
  profile URL, compared without case. It accepts only https links, does
  not run JavaScript and reads at most the first 1 MB of the response.
  The `link` element sits at the top of the `<head>`, so a long page
  cannot push it past that limit. This is `VerifyLinkService` and
  `Account::Field` in mastodon/mastodon v4.7.5, and the
  [verification docs](https://docs.joinmastodon.org/user/profile/#verification).

  Mastodon checks a link only when the profile is saved with a link that
  is not verified yet (`UpdateAccountService#check_links`). The owner
  therefore adds `https://kadet-hub.org` to the profile metadata after the
  first deploy that carries the element, or saves the profile again.

  Since Mastodon 4.3.0 a link preview names the author's account when the
  page's `<head>` has a `fediverse:creator` meta tag, read from `name` or
  `property`. Mastodon credits the account only when its owner lists the
  page's domain under "Author attribution" in the profile settings, so the
  owner adds `kadet-hub.org` there. This is `LinkDetailsExtractor`,
  `FetchLinkCardService` and `Account::AttributionDomains` in v4.7.5, the
  [v4.3.0 release notes](https://github.com/mastodon/mastodon/releases/tag/v4.3.0)
  and the [attribution docs](https://docs.joinmastodon.org/user/profile/#attribution).

  Only posts name the account as creator. A generator page shows its
  author's README, which a preview must not credit to the project. Hugo
  alias pages (CAT-36f) are redirects and carry neither element. A
  browser fetches nothing for `rel="me"`, so the page still loads nothing
  from another origin (CAT-3).

  The handle is `params.mastodon` in `catalog/site/hugo.toml`. The
  template builds the profile URL `https://<server>/@<user>` from it,
  which holds where the server serves profiles on the handle's own
  domain. For hachyderm.io the account lookup returns
  `https://hachyderm.io/@kadethub` (checked 2026-11-12).

  - Test: `catalog/test_catalog.py` (`Site.test_fediverse_verification`;
    partial: the check on hachyderm.io runs only after the owner actions)
  - Since: #678

- CAT-58: Every post MUST have its own Open Graph image, a 1200x630 PNG
  of less than 300,000 bytes that Hugo builds from
  `catalog/site/assets/og/base.png`. `og:image`, `og:image:width`,
  `og:image:height`, `twitter:image` and the `BlogPosting` `image` MUST
  name it, and `og:image:alt` MUST contain the post's title. Other pages
  keep `og.png`.

  Hugo's `images.Text` draws the text at build time, so the build needs
  no other tool. The file name carries a hash that changes with the
  drawn text. A corrected title therefore gets a new URL, which a
  platform that caches previews by URL fetches again. The size budget is
  near the 244,751 bytes `og.png` had before the mark of CAT-61 and far
  below LinkedIn's 5 MB, the
  smallest documented limit of the platforms in use. The cards of the 23
  posts on 2026-11-12 have 41,880 to 68,853 bytes.

  `og:image:alt` is the only description a card gets on Mastodon, which
  stores it as the card's `image_description` (`preview_card.rb` in
  Mastodon v4.7.5). It reads "kadet-hub.org: <title> (tools: <tools>)",
  the text the card shows. A release post (CAT-36b) has no `tools`, so
  its card and its alt text show the title alone.

  Related: CAT-36a, CAT-51.

  - Test: `catalog/test_catalog.py` (`Site.test_post_cards`,
    `ReleaseDigest.test_posts` for a release post); manual: the Mastodon
    and LinkedIn preview of the first post after deploy
  - Since: #683

- CAT-58a: Text on the card MUST stay out of the outer 80 px. The title
  MUST take at most three lines and end in "…" when it needs more. Text
  MUST reach a contrast of at least 4.5:1 against the background.

  dev.to shows a cover at 1000x420 and cuts about 63 px from the top and
  the bottom of a 1200x630 image (Forem `editor_helper_service.rb`). X
  draws the page title in a label above the bottom edge, and Forem keeps
  the bottom 80 px of its own cards clear for it. The 80 px cover both,
  and the sides keep the same margin.

  `images.Text` wraps 20 px before the image's right edge and does not
  report overflow (`resources/images/text.go` in Hugo v0.168.0).
  `og-lines.html` therefore breaks the lines itself. It adds up the
  advance widths of the characters, read from the font's `hmtx` table
  into `assets/og/advances.json`, and starts a new line before 1030 px.
  The sum leaves out the font's kerning, which Hugo draws with, and
  glyphs that reach past their advance. On the 54 title lines of the 23
  posts on 2026-11-12 the drawn line ended between 5.0 px before and
  0.1 px after the sum, so 10 px below the 1040 px of the safe zone are
  enough. The tags take one line by the same rule.

  Mastodon scales a card down to 230,400 pixels, 640x360 at 16:9, so
  text shows at about half the size it is drawn at (`preview_card.rb`).
  The title is drawn at 64 px and keeps about 34 px there. The domain is
  drawn at 36 px and the tags at 32 px.

  The colours are tokens of the dark theme on its `--bg` `#1c1b3a`: the
  title in `--text` at 13.24:1, the tags in `--accent` at 7.56:1 and the
  domain in `--text-muted` at 9.21:1, by the WCAG formula. The tags carry
  the accent because a reader looks for a tool, and the domain is the
  same on every card. The mark keeps the favicon's colours, which the
  WCAG exception for logos covers.

  - Test: `catalog/test_catalog.py` (`Site.test_post_cards`: on every
    post's card and on a fixture title longer than three lines, the
    outer band and the rows between the third title line and the tags
    are background; the colours in `og-card.html`;
    `Site.test_card_lines_keep_a_long_last_word`: a last line whose
    first word leaves no room for "…" keeps that word)
  - Since: #683; the Harbour colours: #710

- CAT-58b: The card MUST show nothing but the site's "K" mark, the
  domain `kadet-hub.org`, the post's title and its `tools` as hashtags.

  The mark is the one of `static/favicon.svg` (CAT-61). `base.png` holds
  it at four times that size, 64 px at (80, 80) on `--bg`, rasterised
  from the favicon's SVG; the base image of #683 used rsvg-convert 2.63.4.
  A tool appears as the hashtag the social posts already carry, in the
  card's font.

  Third-party logos are left out. No mark owner checked on 2026-11-12
  grants an unaffiliated project the use of its logo on an editorial
  social card. The Linux Foundation guidelines that cover the CNCF
  artwork allow fair use of word marks only
  ([Linux Foundation](https://www.linuxfoundation.org/legal/trademark-usage)).
  HashiCorp, Docker and AWS restrict logos to approved or plain-text use
  ([HashiCorp](https://www.hashicorp.com/en/trademark-policy),
  [Docker](https://www.docker.com/legal/trademark-guidelines/),
  [AWS](https://aws.amazon.com/trademark-guidelines/)). Kapitan's
  repository has no logo policy, and section 6 of its Apache 2.0 license
  grants no rights to trademarks. Since the card admits no third-party
  mark, there is no list of permitted marks. The owner also ruled out
  generated imagery.

  The font is Noto Sans Bold 2.015, the unhinted TTF of the release
  `NotoSans-v2.015` of notofonts/latin-greek-cyrillic, in
  `catalog/site/assets/og/`. It is licensed under the SIL Open Font
  License 1.1, which allows redistribution with the license text, and
  `OFL.txt` next to the font holds that text. The font declares no
  Reserved Font Name. Hugo reads it at build time and does not publish
  it. The site's own fonts are Sora and Manrope (CAT-60), which the card
  does not use.

  - Test: manual: review of `base.png` and `og-card.html` in the merge
    request
  - Since: #683; the mark of CAT-61: #710

- CAT-45: A blog post that puts several recipes or generators together
  into one use case, backed by a project in kadet-hub/examples, MUST name
  them in a front matter field `stack`. The listings of CAT-46 and CAT-48
  MUST be built from that field alone.

  Such a stack post walks through one project, such as Open WebUI with
  SearXNG, whose `check` script deploys it on kind. The field holds what
  the project pins, including a generator that comes only with a recipe:

  ```yaml
  stack:
    recipes: [open-webui, ollama, searxng, valkey]
    generators: [kubernetes]
    example: open-webui-searxng
  ```

  `recipes` are names of recipe pages (CAT-37c), `generators` names of
  generators in the index, and `example` the project's folder in
  kadet-hub/examples. Either list may be left out. The post is the only
  place that names its parts, so a new stack is one block in the pull
  request that adds the post. A data file next to the posts was
  considered; it would name every post a second time. A stack shows from
  its post's date, because Hugo leaves a future-dated post out of the
  build (CAT-36a).

  - Test: `catalog/test_catalog.py` (`Stacks.test_stacks_page`, `Stacks.test_queued_stack_posts`)
  - Since: #546

- CAT-46: The site MUST have a page at `/stacks/` that lists every
  published stack post, newest first, with its title linked to the post,
  its description, its recipes and generators each linked to its page,
  and a link to its folder in kadet-hub/examples.

  A generator the index does not list has no page, so its name shows
  without a link, as a prerequisite without a page does on a recipe page
  (CAT-37c). The release build's index lists every generator the posts
  name. Without a published stack post the page says so.

  - Test: `catalog/test_catalog.py` (`Stacks.test_stacks_page`)
  - Since: #546

- CAT-47: The site navigation MUST link `/stacks/` after "Recipes", and
  `/llms.txt` (CAT-16) MUST link it under "Using generators".

  - Test: `catalog/test_catalog.py` (`Site.test_stacks_linked`)
  - Since: #546

- CAT-48: Every recipe page and every generator page MUST have a section
  "Used in stacks" that links each published stack post naming it, newest
  first, and MUST NOT have the section when none does.

  On a recipe page the section comes before "Versions". On a generator
  page it follows the README in the same column, and the "On this page"
  list of CAT-19 links it between README and Versions. The Markdown
  variants (CAT-28, CAT-37b) do not carry it.

  - Test: `catalog/test_catalog.py` (`Stacks.test_used_in_stacks`)
  - Since: #546

- CAT-49: The build MUST fail when a published stack post names a recipe
  without a page at `/recipes/<name>/` or names no `example`.

  Recipe pages are content pages, so the check runs the same offline and
  in the release. A failed build stops the release's catalog job before
  the Pages upload and the previous site stays live, as with CAT-37a.
  Posts are usually merged days before their date, and the release build
  would meet a wrong name only on the morning the post goes live. The
  test therefore builds the site with Hugo's `--buildFuture`, which checks
  queued posts in the pull request that adds them, and checks every
  generator a stack post names against the entries in `generators/`. The
  build does not check generators, because their pages come from the
  index, and the fixture indexes of the tests leave most of them out.

  - Test: `catalog/test_catalog.py` (`Stacks.test_unknown_recipe_fails_the_build`, `Stacks.test_queued_stack_posts`)
  - Since: #546

- CAT-50: The build MUST fail when a published stack post's `example` is
  not one folder name of lowercase letters, digits and single hyphens.
  Every committed stack post MUST link
  `https://github.com/kadet-hub/examples/tree/main/<example>` in its text.

  The project link on `/stacks/` is built from `example`, and the registry
  has no list of the folders in kadet-hub/examples. A wrong name would
  give a link to a 404 with a green build. The format catches another
  casing, a trailing slash and a path. A misspelling passes the format,
  so `Stacks.test_queued_stack_posts` compares `example` with the
  project link the post's text already carries. A name misspelled the
  same way in both places still passes. Checking the folder itself needs
  the examples repository, which the offline build and tests do not
  have.

  - Test: `catalog/test_catalog.py` (`Stacks.test_unknown_recipe_fails_the_build`, `Stacks.test_queued_stack_posts`)
  - Since: #561

- CAT-51: Every post under `catalog/site/content/blog/` MUST have a front
  matter field `tools` with one to three entries, on one line as in
  `tools: [ArgoCD, kind, Helm]`. An entry MUST consist of letters and
  digits only and MUST NOT be Kapitan in any casing.

  kadet-hub/outreach posts each entry as a hashtag, after the two it
  always sets, #KadetHub and #Kapitan, and takes at most three. An entry
  is therefore the tool's hashtag without the `#`. It has no hyphen and
  keeps the tool's own casing, or CamelCase where that reads better, as
  in `kind`, `CertManager` and `OAuth2Proxy`. The entries are the tools
  the post is most about that a Helm, Kustomize or Kubernetes user would
  follow. Subjects such as security belong in `topics` (CAT-36a). The
  weekly release posts of CAT-36b come from the content adapter and have
  no `tools`.

  - Test: `catalog/test_catalog.py` (`Site.test_blog_tools`; partial:
    which tools a post is most about is a review question)
  - Since: #659

- CAT-52: Every entry of the blog feed (CAT-36) MUST carry one
  `<category term="<tool>"/>` per entry of its post's `tools`, in the
  order of the field.

  The feed is Atom, which names a category by its `term` attribute
  (RFC 4287, section 4.2.2). kadet-hub/outreach reads the posts from the
  feed alone. A post without `tools`, such as a release post, has no
  category.

  - Test: `catalog/test_catalog.py` (`Site.test_blog_tools`; partial:
    the posts the test build publishes on the day it runs)
  - Since: #659

- CAT-37: The site MUST have an index of the recipes at `/recipes/`, and
  the site navigation MUST link it. Each recipe has a page at
  `/recipes/<name>/` (CAT-37c).

  The first recipes were inventory classes in kadet-hub/examples, deployed
  and checked on kind by that repository's CI (EX-5). All of them moved to
  kadet-hub/recipes (CAT-38a), and the layout for their pages was removed.

  As CAT-11a asks, every recipe title and the index title lead with the
  searched term and name Kapitan where it fits. For a recipe the term is
  its software followed by "on Kubernetes", as in "PostgreSQL on
  Kubernetes: CloudNativePG clusters from Kapitan". Titles MUST NOT say
  "without Bitnami". Every description
  leads with "Bitnami
  <chart> Helm chart alternative:" and names Kapitan with Kubernetes. A title that leaves no room for the " · kadet-hub" suffix
  within CAT-11's 65 characters stands alone; the template counts bytes,
  so the suffix's "·" counts twice.

  A page per recipe does not conflict with the single Bitnami guide of
  CAT-11a: each recipe page carries its own tested class, not the same text
  under another search term.

  Related: CAT-11, CAT-37c.

  - Test: `catalog/test_catalog.py` (`test_recipes`)
  - Since: #283, #299, #300, #354, #363, #368; examples layout removed: #372

- CAT-37a: The build MUST fail when a file of a CAT-37c page cannot be
  fetched or is missing.

  `catalog/build` resolves `main` of kadet-hub/recipes to a commit and
  fetches each recipe's README, `init.yml` and the classes they name from
  `raw.githubusercontent.com` at that commit with `curl -f`, as it reads
  the previous `catalog.json`, and copies them into the site's
  `assets/classes/`; the recipe templates stop the build with `errorf`
  when one is missing. The API lookups of the build degrade to a warning
  because the page stays usable without a star count or a README; a
  recipe page without its class has nothing to copy. A failed build stops
  the release's catalog job before the Pages upload, so the previous site
  stays live, as with CAT-11d. With `CATALOG_OFFLINE=1` the build reads
  the files from `$CATALOG_RECIPES/inventory/classes/`, with `recipes.sha`
  and a `recipes/<name>/` directory per recipe, so the tests use fixtures
  and a local checkout can be previewed.

  Hugo's `resources.GetRemote` would fetch from the templates instead. Its
  file cache keeps a fetched file without expiry unless `maxAge` is set,
  and the offline switch would need an environment variable allowed
  through `security.funcs.getenv`; the build script already owns network
  access and the offline fixtures. Neither variant uses `actions/cache`
  (GI-10).

  - Test: `catalog/test_catalog.py` (`test_recipe_file_missing_fails_the_build`, `test_build_fetches_recipes_at_main`)
  - Since: #283, #300, #368; kadet-hub/examples no longer fetched: #372

- CAT-37b: Every recipe page MUST have a Markdown variant (CAT-28) with
  the same facts and files, `/llms.txt` (CAT-16) MUST list it in a section
  "Recipes" after "Guides", and the Bitnami guide MUST link the recipe of
  every chart it names that has one.

  - Test: `catalog/test_catalog.py` (`test_recipes`, `test_llms_txt`)
  - Since: #283, #299

- CAT-37c: The site MUST have a page at `/recipes/<name>/` for every
  recipe of kadet-hub/recipes that has a content page with
  `layout: chart-recipe`. The page MUST show the source pinned by digest
  (a chart, a compose file as CAT-37e says, an image as CAT-37f says, or a
  release manifest as CAT-37g says), the proof level, the
  README section "Replaces" when the README has one, the prerequisites of
  its `Requires:` line and of the recipes it includes, the components and
  options the recipe deploys, the README section "Required parameters" before the include snippet,
  the include snippet, a fetch inventory pinned to the commit the page was
  built from with the commands that use it, the README sections "Settings",
  "Left out", "Renamed RBAC objects" and "Proof", the generators the recipe
  pins linked to their pages with version and digest, and a link to the
  recipe's folder at that commit. The build MUST fail when a file or line
  the page shows cannot be fetched or is missing.

  A recipe of kadet-hub/recipes rebuilds one Helm chart as a class
  directory, and that repository's CI compares it with the chart at the
  proof level its README states (RCP-23, RCP-13). Until recipes are
  published as OCI artifacts (RCP-31 there), a consumer fetches one through a
  fetch inventory with a `git` dependency pinned by commit (RCP-15). The
  page gives that dependency for the commit it was built from and links
  the repository README's "Using a recipe" for verifying the generators and
  raising the pin.

  A chart is shown as the `Source:` line gives it, `oci://<reference>:<version>`
  or, for a chart that only an HTTP repository publishes,
  `https://<repository>/<chart>:<version>`, each followed by `@sha256:` and
  the digest. The digest of an HTTP chart is the SHA-256 of the archive the
  repository's `index.yaml` lists (RCP-23 there, REC-7, REC-13). A recipe
  that includes another as `recipes.<other>` in its `init.yml` (REC-16)
  gets one more `git` dependency in the fetch inventory, for `<other>` at
  the same commit, because the compile stops without that class.

  A recipe names what the cluster needs once on its `Requires:` line
  (RCP-54 there), such as `strimzi` for kafka. The page lists these among
  the facts at the top, each linked to its own page when the site has one,
  because a reader has to install them before the recipe. Those of a
  recipe it includes as `recipes.<other>` follow (RCP-55 there), so keycloak
  lists `keycloak-operator`, `cert-manager` and `cnpg`, which its included
  `postgresql` requires. The list goes on with the `Requires:` entries of
  each prerequisite in turn, so rabbitmq
  lists `rabbitmq-cluster-operator` and then `cert-manager`, which the
  operator requires. A prerequisite without a page ends its branch,
  because the build fetches a README only for a recipe that has one. The fetch
  inventory does not pin them: the recipe does not include them, and
  their pages give the inventory for their own target.

  `catalog/build` resolves `refs/heads/main` of kadet-hub/recipes with
  `git ls-remote` and fetches from `raw.githubusercontent.com` at that
  commit with `curl -f`: the recipe's `README.md` and `init.yml`, the class
  of every component `init.yml` includes as `.<component>`, and the class
  of every option the README's Include snippet names as
  `recipes.<name>.<option>`. Fetching by commit keeps the files and the
  pinned `ref` the same when `main` moves during the build. Vendored files
  such as the CRDs are not fetched, because the page does not show them.
  The build copies the files to `assets/classes/recipes/<name>/`, the path
  a consumer fetches them to, and the commit to
  `assets/classes/recipes.sha`. With `CATALOG_OFFLINE=1` it reads both from
  `$CATALOG_RECIPES/inventory/classes/`, as in CAT-37a.

  The README sections are rendered from the README's Markdown the way Hugo
  renders content, which drops raw HTML, so the content page does not
  repeat the tables. The lead is the README's first paragraph. The
  template stops the build with `errorf` when a class, the `Source:` or
  `Level:` line, the Include snippet or the section "Required parameters"
  is missing. The content page's front matter holds title, description,
  `layout` and `lastmod`, and CAT-37b and CAT-11g apply as to every recipe
  page.

  The template reads each class and `init.yml` as YAML by its extension.
  Given only the text, `transform.Unmarshal` guesses the format, and it
  read homepage's `kubernetes.yml`, whose first comment has a comma before
  any colon, as CSV and stopped the build.

  "Required parameters" names the values the target must set, such as
  miniflux's two password refs, or says that there are none (RCP-40
  there). A recipe leaves such a value unset, so the compile stops until
  the target sets it (RCP-19 there). The page shows the section as its
  own heading before "Include", so it is read before the snippet is
  copied.

  "Replaces" is the section a recipe that took over a kadet-hub/examples
  recipe has, with the objects and settings a target moving from that
  recipe gets differently (RCP-41 there). The page shows it right after
  the source and the level, because a reader who comes from the examples
  recipe needs it before anything else.

  Titles lead with the chart's software and "on Kubernetes" and go on
  with what the recipe deploys or how it was built (CAT-11j to CAT-11l),
  such as "cert-manager on Kubernetes, matched to its chart object by
  object". Descriptions
  lead with "<chart> Helm chart alternative:" and name Kapitan with
  Kubernetes. "Bitnami" appears only where the chart is a Bitnami chart,
  or where the recipe replaces a kadet-hub/examples recipe that stood in
  for one.

  Such a recipe keeps the queries CAT-11f routes to the examples page, so
  its description leads with them. The title names the project and the
  searched term without "without Bitnami". valkey replaces the stand-in
  for Bitnami's `redis` chart: "Valkey (Redis) on Kubernetes, the
  BSD-licensed fork in Kapitan", with a description that leads with
  "Bitnami redis Helm chart alternative:". external-dns-powerdns replaces
  the stand-in for Bitnami's `external-dns` chart, rebuilt from the
  project's own chart that only an HTTP repository publishes, and has a
  description that leads with "Bitnami external-dns Helm chart
  alternative:". postgresql replaces the stand-in for Bitnami's
  `postgresql` and `postgresql-ha` charts, rebuilt from CloudNativePG's
  chart `cluster`, and has a description that leads with "Bitnami
  postgresql Helm chart alternative:". It requires `cnpg`, the operator
  from the project's chart. keycloak replaces the stand-in for Bitnami's
  `keycloak` chart, designed on Keycloak's image (CAT-37f), and has a
  description that leads with "Bitnami keycloak Helm chart alternative:".
  It requires `keycloak-operator` and `cert-manager`. nextcloud, rebuilt
  from Nextcloud's own chart, which Bitnami has no counterpart for, has a
  description that leads with "Nextcloud Helm chart alternative:". The
  title "Valkey on
  Kubernetes without Helm" named neither Redis nor Bitnami, although
  CAT-11f sends the Redis queries and "valkey helm chart not bitnami" to
  the page. Moving those queries to the Bitnami guide was considered, but
  the guide only links the recipe, and the recipe page is what answers
  them.

  Related: RCP-1, RCP-15, RCP-19, RCP-23, RCP-40, RCP-41, RCP-54 (kadet-hub/recipes `docs/specs/recipes.md`), CAT-11f, CAT-37a.

  - Test: `catalog/test_catalog.py` (`test_chart_recipe`, `test_http_chart_recipe`, `test_recipe_prerequisite`, `test_compose_recipe`, `test_designed_recipe`, `test_recipe_file_missing_fails_the_build`)
  - Since: #342, #344, #347, #349, #354; HTTP chart: #363; prerequisites: #364;
    transitive prerequisites: #367; cnpg: #366; keycloak and its included
    recipes' prerequisites: #368; nextcloud: #402;
    authentik, blackbox-exporter, gitea, immich, jellyfin, n8n, netbox,
    ollama, open-webui and semaphore: #507; forgejo: #542; litellm,
    mattermost, qdrant, rocketchat, stirling-pdf and zulip, classes read
    as YAML: #577; langfuse, librechat and mlflow: #592

- CAT-37d: `/recipes/` MUST list the recipes of CAT-37c, each with its
  proof level.

  A recipe is compared with the chart or release manifest it rebuilds
  (CAT-37g), or deployed and smoke tested when its source is a compose
  file or an image (CAT-37e, CAT-37f).

  - Test: `catalog/test_catalog.py` (`test_recipes`)
  - Since: #342, #349, #368; one list: #372

- CAT-37e: A CAT-37c page whose README `Source:` line is a GitHub file URL
  MUST show the source as a Docker Compose file with its repository,
  commit and path, linked to the file at that commit, and its sha256. It
  MUST show the README section "Mapping" and MUST NOT say that the recipe
  is compared with a chart. The `/recipes/` entry of CAT-37d MUST NOT
  either.

  The source type follows from the form of the `Source:` line, `oci://`
  for a chart and a GitHub blob URL pinned to a commit for a compose file
  (DEC-9, RCP-23 there). A compose recipe is at level `deploys` only: a
  compose file has no Kubernetes objects to compare with, so the proof is
  the deploy on kind and the smoke test (DEC-8, RCP-38, RCP-39 there). The
  "Mapping" section is the compose counterpart of "Settings" for what the
  file sets but the recipe renders differently. A `Source:` line in none
  of the forms of CAT-37c, CAT-37e, CAT-37f and CAT-37g stops the build as
  a missing one does.

  Titles lead with the application and "on Kubernetes", such as
  "Miniflux on Kubernetes, migrated from Docker Compose by Kapitan".
  Descriptions lead with "<application> Docker Compose to Kubernetes" and
  name Kapitan.

  Related: DEC-8, DEC-9, RCP-37 to RCP-39 (kadet-hub/recipes `docs/specs/recipes.md`), CAT-37c.

  - Test: `catalog/test_catalog.py` (`test_compose_recipe`, `test_recipes`, `test_recipe_file_missing_fails_the_build`)
  - Since: #343; paperless-ngx, pihole, searxng, uptime-kuma and
    vaultwarden: #507; umami: #519; actual, ejabberd and memos: #577;
    navidrome: #592; jitsi-meet: #635

- CAT-37f: A CAT-37c page whose README `Source:` line is an image
  reference MUST show the source as the container image the recipe is
  designed on, with its tag and digest. It MUST NOT say that the recipe
  is compared with a chart, and the `/recipes/` entry of CAT-37d MUST NOT
  either.

  A recipe designed in kadet-hub, for a project that ships no chart,
  Kustomize base or compose file, has the project's image as its source,
  written as `<registry>/<repository>:<tag>@sha256:<digest>` (DEC-9,
  DEC-11, RCP-23 there). It is at level `deploys` only, proven by the
  deploy on kind and the smoke test (RCP-44, RCP-45 there). Titles and
  descriptions follow CAT-37c. mysql, the first such recipe, replaces the
  kadet-hub/examples stand-in for Bitnami's `mysql` chart, so its
  description leads with "Bitnami mysql Helm chart alternative:". mongodb,
  the stand-in for Bitnami's `mongodb` chart, moved the same way, with
  "Bitnami mongodb Helm chart alternative:".

  mariadb, designed on the MariaDB Foundation's image, had no stand-in in
  kadet-hub/examples, but its README says it can replace Bitnami's
  `mariadb` chart in that chart's default architecture. Its description
  leads with "Bitnami mariadb Helm chart alternative:", because that chart
  is what readers search a replacement for. wordpress, designed on the
  Docker Official Image with mariadb included, follows it with "Bitnami
  wordpress Helm chart alternative:". memcached, designed on the Docker
  Official Image, follows it with "Bitnami memcached Helm chart
  alternative:".

  powerdns is the PowerDNS part of the kadet-hub/examples recipe
  `external-dns-powerdns`, which stood in for Bitnami's `external-dns`
  chart. PowerDNS itself replaces no Bitnami chart, so the description of
  its new page leads with "PowerDNS Helm chart alternative:". The external-dns part moved to
  kadet-hub/recipes under the name `external-dns-powerdns`, and its page
  `/recipes/external-dns-powerdns/` with it (CAT-37c, CAT-38a).

  kafka, the stand-in for Bitnami's `kafka` chart, moved the same way. It
  is designed on Strimzi's Kafka image, and its description leads with
  "Bitnami kafka Helm chart alternative:". It requires `strimzi`, the
  operator from Strimzi's chart (CAT-37c).

  rabbitmq, the stand-in for Bitnami's `rabbitmq` chart, moved the same
  way. It is designed on the Docker Official Image, and its description
  leads with "Bitnami rabbitmq Helm chart alternative:". It requires
  `rabbitmq-cluster-operator`, whose page is described in CAT-37g and which
  requires `cert-manager`.

  keycloak, the stand-in for Bitnami's `keycloak` chart, moved the same
  way. It is designed on Keycloak's image as a resource of the Keycloak
  Operator, and its description leads with "Bitnami keycloak Helm chart
  alternative:".
  It requires `keycloak-operator` and `cert-manager` and includes
  `postgresql` (CAT-37c).

  Related: DEC-11, RCP-23, RCP-44, RCP-45 (kadet-hub/recipes `docs/specs/recipes.md`), CAT-37c, CAT-37e.

  - Test: `catalog/test_catalog.py` (`test_designed_recipe`, `test_recipes`)
  - Since: #349, #352, #354; powerdns: #357; kafka: #364; rabbitmq: #367;
    keycloak: #368; mariadb: #509;
    wordpress: #511; memcached: #542; ghost, home-assistant, homepage and
    matrix-synapse: #577; stalwart: #592

- CAT-37g: A CAT-37c page whose README `Source:` line is a release manifest
  MUST show the source as the project's release manifest with its
  repository, tag and file, linked to the release asset, and its sha256.
  It MUST say that the recipe is compared with the manifest, not with a
  chart.

  A project that publishes a manifest with each release and no chart, such
  as `cluster-operator.yml` of rabbitmq/cluster-operator, gives the asset's
  URL as the source, `https://github.com/<owner>/<repository>/releases/download/<tag>/<file>`
  followed by `@sha256:` and the digest of the file (RCP-23 there). Its
  recipe is at level `deploys`, and `check` compares it with the
  manifest's objects at `renders` (RCP-59 there).

  Titles lead with the application and "on Kubernetes", such as
  "RabbitMQ Cluster Operator on Kubernetes from its release manifest".
  Descriptions lead with "<application> release manifest alternative:" and
  name Kapitan with Kubernetes.

  Related: RCP-23, RCP-59 (kadet-hub/recipes `docs/specs/recipes.md`), CAT-37c.

  - Test: `catalog/test_catalog.py` (`test_release_manifest_recipe`, `test_recipes`)
  - Since: #367

A reader who runs a Helm chart comes to `/recipes/` to find the recipe that
replaces it. Most queries of CAT-11f have this form, such as "<app> helm
chart" or "bitnami alternative <app>". The chart's name is often not the
recipe's: blackbox-exporter rebuilds `prometheus-blackbox-exporter`, and
postgresql rebuilds CloudNativePG's `cluster`. The entries named title,
description and proof level only, so the list did not say which chart or
version a recipe rebuilds. On the live site on 2026-11-12 the 55 entries
took 17,062 px at a width of 375 px, 19 screens of 900 px, with no way to
narrow them.

- CAT-37h: Every entry on `/recipes/` MUST name its source the way the
  recipe page does (CAT-37c, CAT-37e to CAT-37g), without digest and
  without commit.

  A chart keeps its version, since a reader compares it with the version
  they run. Digest and commit stay on the recipe page. In the list they
  add 40 to 64 hex characters per entry that no reader compares there. A
  compose recipe and one designed on an image do not say "chart", as
  CAT-37e and CAT-37f require of the entry.

  The line makes the unfiltered list longer. Built from kadet-hub/recipes
  at 04879f4, the page grew from 17,062 px to 21,711 px at 375 px and from
  10,212 px to 12,074 px at 1280 px, because a chart reference wraps on a
  phone. The field of CAT-37i is what shortens the list.

  - Test: `catalog/test_catalog.py` (`Site.test_recipe_sources_listed`)
  - Since: #681

- CAT-37i: `/recipes/` MUST have a field that shows only the entries whose
  text contains every word typed into it, and MUST say how many entries
  match.

  The text of an entry is what it shows: title, description, source
  (CAT-37h), proof level and version, compared in lower case. Words are
  split at spaces, `/` and `:`. So `bitnami/redis` finds valkey, whose
  description leads with "Bitnami redis Helm chart alternative", and
  `prometheus-community/prometheus-blackbox-exporter` finds
  blackbox-exporter by its chart. A word that starts with a digit, or with
  `v` and a digit, is taken as a version and ignored, and so is everything
  from an `@`. A recipe pins one chart version, and a reader who pastes a
  chart reference usually runs another.

  The query is kept in the URL as `?q=`, as on `/generators/` (CAT-8), so
  going back from a recipe page restores the list. The canonical URL stays
  `/recipes/` (CAT-11). When no entry matches, the page says so and links
  the Bitnami guide, the open recipe requests on `/wanted/` and the
  request form (CAT-41).

  The field is progressive enhancement in `site.js`, as the selector of
  CAT-34a is. Without JavaScript the field stays hidden and the list shows
  every entry with its source, which the browser's own find covers. The
  script only hides entries and writes the count with `textContent`, so it
  builds no markup from data (CAT-3).

  - Test: `catalog/test_catalog.py` (`Site.test_recipe_finder`, partial:
    the markup; the matching runs in the browser); manual: AC-47
  - Since: #681

- AC-47 (CAT-37h, CAT-37i): the fixture build's `/recipes/` names the
  source of every entry, and holds the hidden field, the count and the
  empty state with its three links. In Chrome at 375 px and 1280 px, light
  and dark, `bitnami/redis` leaves valkey, `prometheus-community/prometheus-blackbox-exporter`
  leaves blackbox-exporter, and the pasted chart reference
  `oci://quay.io/jetstack/charts/cert-manager:v1.19.0` keeps cert-manager.
  A word that matches nothing shows the empty state. The field is reached
  by Tab with a visible focus ring and has an accessible name, and Back
  from a recipe page restores the query. Check:
  `Site.test_recipe_sources_listed`, `Site.test_recipe_finder`; manual:
  browser run on the built site (2026-11-12).

- CAT-38: Once the index lists a recipe (REC-13), its CAT-37c page MUST
  keep its URL and take the README sections, the chart, the level and the
  generators from the latest version that is not yanked, read from its
  artifact by digest under the rules of CAT-7, instead of from `main`. The
  fetch inventory entry MUST pin `ghcr.io/kadet-hub/recipes/<name>` by
  version and digest (CON-4) in place of the commit, with the CON-5
  verification commands. The page MUST add the `renders` result of that
  version's scan record next to the README's level, the output
  capabilities with the `output_capabilities` line a consumer policy needs,
  the inventory backends of its record (REC-18) when it lists them, and
  every version. A version that is yanked, or that pins a yanked
  generator version, MUST show the reason and no fetch inventory entry.

  The page then shows what consumers fetch, not what `main` holds since.
  A generator yank is shown because the recipe still lists as not yanked
  (REC-13) while the consumer workflow fails on it.

  `catalog/build` fetches the layer of that version from
  `ghcr.io/<owner>/recipes/<name>` by digest, as it does for a generator
  (CAT-7). It unpacks the layer into `assets/classes/recipes/<name>/` in
  place of the files from `main`, with the `data` filter of Python's
  `tarfile`, which refuses absolute paths, `..` and links that leave the
  directory. A layer that cannot be fetched or unpacked stops the build,
  as a missing file does (CAT-37a). With `CATALOG_OFFLINE=1` the build
  reads it from `$CATALOG_ARTIFACTS/recipes/<name>.tar`. Relative links in
  the README sections point into kadet-hub/recipes at `source.sha`.

  The fetch inventory holds one `oci` dependency, for the recipe. It sets
  no `vars`, because CON-4 accepts nothing but `dependencies` there. The
  consumer workflow adds the recipes the record lists under `includes`
  (CON-7). Kapitan's `--fetch` reads no index, so for a version with
  includes the page names them and gives the commands that pull each of
  them by digest for a local compile (CON-6). The verification commands
  run `gh attestation verify` on the recipe and on each included recipe,
  and the page links "Verifying by hand" in `docs/consumers.md` for the
  index check of CON-5. The policy line names `compiled/<target>/*`,
  because the record leaves out the output paths (REC-13).

  The version list gives each version's date and digest, and the reason
  when the version or a generator version it pins is yanked. Only the
  latest version has a fetch inventory, the one under "Fetching it". A recipe whose versions are all yanked has no version to
  read the files from, so its page stays built from `main` and adds the
  version list.

  - Test: `catalog/test_catalog.py` (`ListedRecipe.test_page_from_the_artifact`, `ListedRecipe.test_fetch_inventory_and_verification`, `ListedRecipe.test_yanked_versions_and_generators`, `ListedRecipe.test_all_versions_yanked`, `ListedRecipe.test_layer_missing_fails_the_build`, `ListedRecipe.test_build_fetches_the_layer_by_digest`, `ListedRecipe.test_backends`)
  - Since: #399; included recipes left to the consumer workflow: #536;
    inventory backends: #544

- CAT-38a: A recipe listed under CAT-37d MUST show its latest version.

  valkey, mysql, mongodb, external-dns-powerdns, kafka, rabbitmq,
  postgresql and keycloak moved from kadet-hub/examples to
  kadet-hub/recipes under the same name. Each kept its content page, which
  switched to `layout: chart-recipe`, so its URL stayed. kadet-hub/examples
  has no recipes left, so two recipes of the same name from both
  repositories can no longer occur.

  The `/recipes/` entry of a recipe the index lists names its latest
  version that is not yanked after the proof level, and the recipe page
  names it among the facts at the top.

  - Test: `catalog/test_catalog.py` (`ListedRecipe.test_index_shows_the_latest_version`)
  - Since: #399; valkey moved: #345; mysql moved: #349;
    mongodb moved: #352; external-dns-powerdns moved: #363; kafka moved: #364;
    rabbitmq moved: #367; postgresql moved: #366; keycloak moved: #368;
    name clash check dropped: #372

- CAT-38b: `catalog.json` MUST carry `recipes[]` with `name`, `description`
  and `versions[]` holding `version`, `digest`, `yanked`, `level`, `chart`
  and `generators`, and `docs/consumers.md` MUST document these fields as
  CAT-34d does.

  Listed recipes are not cards on `/generators/` and do not count in its
  tag filter, `/kinds/` or `/compatibility/`. Those pages describe
  generators, and a recipe has no tags. The start page counts them under
  Recipes (CAT-67).

  Each pin in `generators` also carries `yanked`, the reason the index
  gives for that generator version, or `null`. A tool can then skip a
  recipe version that the consumer workflow rejects (CAT-38), as the jq
  example in `docs/consumers.md` does. A test runs that example against
  the fixture build, as for CAT-34d.

  - Test: `catalog/test_catalog.py` (`ListedRecipe.test_catalog_json`, `ListedRecipe.test_not_counted_with_generators`, `ListedRecipe.test_consumer_docs_lookup`)
  - Since: #399

- CAT-40: The site MUST have a page at `/quickstart/` that takes a reader
  from an empty directory to the web UI of the uptime-kuma recipe on a new
  kind cluster, in this order: create the cluster, install Kapitan, write
  the project, verify the recipe, compile, apply, open the app, delete
  the cluster. Every step MUST say what its commands do. The fetch
  inventory, the include snippet, the verify command, the compile
  commands and, for a version that includes recipes, their pull commands
  MUST be the ones `/recipes/uptime-kuma/` shows (CAT-37c, CAT-38).

  A reader who arrives from a post on Helm or Kustomize had no path from
  reading to a running app: the recipe pages assume Kapitan is installed
  and show the fetch inventory without the project around it. uptime-kuma
  is a published recipe with a web UI and little else: one image, a
  StatefulSet and a Service, no prerequisite and no parameter to set.
  miniflux, the other candidate, needs two password refs, and so a ref
  backend, and runs PostgreSQL next to it.

  The layout calls the recipe page's partial for `uptime-kuma`, so a new
  recipe version changes both pages in the same build and the quickstart
  has no fetch inventory of its own. When the index lists no version of
  the recipe, or its latest version pins a yanked generator, the page
  shows no steps and links the recipe page. Failing the build instead
  would also keep a yank off every other page.

  Kapitan is installed with the command of `docs/consumers.md`, plus
  `--with oras` for the `oci` fetch, as that document says for compiling
  a recipe locally. The command pins Python 3.13, the sandbox's version.
  Kapitan 0.36.3 requires `regex<2025`, and regex 2024.11.6 has wheels up
  to CPython 3.13, so on Python 3.14 uv builds it from source, which needs
  a C compiler and Python's headers. On a host whose `python3` is 3.14,
  the command without `--python` stopped with `fatal error: Python.h: No
  such file or directory` on 2026-11-05. `docs/consumers.md` pins it the
  same way.

  The project uses the omegaconf backend, as "Using a recipe" in
  kadet-hub/recipes does. The files are written with `cat` and a quoted
  heredoc, so every step is a command to paste. The verify step is the
  recipe page's `gh attestation verify`, which needs `gh` logged in. It
  checks neither the index nor the generator the recipe pins, and the
  page links "Verifying a recipe by hand" in `docs/consumers.md` for both.
  The first compile command exits with status 1, as the recipe page says.
  The recipe renders no Namespace, so the apply step creates it.

  The registry's only kind job is `renders` in `gate.yml` (REC-9). It runs
  on entry pull requests from `main`, holds `contents: read` and starts no
  pod, so the quickstart does not fit in it. The catalog tests build from
  fixtures whose digests ghcr.io does not serve, and the page's real
  commands exist only in the release build. The run on kind is therefore
  manual.

  - Test: `catalog/test_catalog.py` (`Quickstart.test_commands`,
    `Quickstart.test_without_a_usable_version`, `Site.test_quickstart_linked`);
    manual: the ten code blocks of the page, built from index serial 113
    and kadet-hub/recipes at `a7ddcbb`, run in order in one bash session
    with an empty home directory on 2026-11-05. Every block succeeded; the
    first compile command failed with `No such file or directory:
    .../compiled`, as the page says. The pod was ready 214
    seconds after `kind create cluster` started, with the kind node image
    already on the host and Python, Kapitan and the Uptime Kuma image
    downloaded. `http://localhost:3001` showed "Create your admin account";
    the port-forward ran in the background for that check.
  - Since: #540; pull commands of included recipes: #536

- CAT-40a: The site navigation MUST link the quickstart as its first
  entry, and every recipe page MUST link it under "Fetching it".

  "Use" points to `docs/consumers.md` on GitHub, which starts with the
  consumer workflow. The quickstart comes before it because it ends with
  a running app, and the workflow is the step after.

  - Test: `catalog/test_catalog.py` (`Site.test_quickstart_linked`)
  - Since: #540

- CAT-40b: The quickstart MUST have the sections "Coming from Helm?" and
  "Coming from Kustomize?". The first MUST link the guides
  `helm-chart-vs-kapitan-inventory`, `same-app` and
  `bitnami-chart-alternatives`, the second `same-app` and every guide
  whose name starts with `kustomize-`.

  The sections map what such a reader knows to what the quickstart did,
  and link the guides that compare the tools on real charts.

  - Test: `catalog/test_catalog.py` (`Site.test_quickstart_linked`)
  - Since: #540

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

- CAT-57: The footer of every page MUST link the repository
  `https://github.com/<owner>/registry`.

- CAT-57a: Every post page MUST link the repository
  `https://github.com/<owner>/registry` in a line of its own after the
  share links.

  The footer linked only files inside the repository, and the post's own
  links lead to its discussions and its source file. The navigation's
  "GitHub" link sits behind the menu button on narrow screens (CAT-9a).
  A reader who finishes a post or reaches the footer gets a direct link
  to the repository's front page, which holds the README, the site, the
  gate and the posts. The links carry no `rel="nofollow"`. CAT-36c sets
  it on compose forms behind a login and CAT-36b on text from generator
  authors, and this repository is the site's own.

  Related: CAT-36a.

  - Test: `catalog/test_catalog.py` (`Site.test_legal_pages_and_notices`
    for CAT-57, `Site.test_blog_post_page` for CAT-57a)
  - Since: #682

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

- CAT-25a: A request to the counter MUST NOT carry the query of a page's
  URL, neither as the page counted nor as its referrer.

  `count.js` sends `location.search` as the parameter `q` of every count
  and event, whatever its `path` setting says (`get_data` in the shipped
  copy), while the privacy page names only path, title, referrer and
  screen width. A search from the start page lands on
  `/generators/?q=…` (CAT-67b), so the typed query would reach the
  GoatCounter instance, as the recipe finder's `/recipes/?q=` (CAT-37i)
  and the tag filter's `?tags=` already let it today. The pages with such
  a query set `no_onload` in `data-goatcounter-settings`, and `site.js`
  counts the view itself at a moment the URL holds no query: it replaces
  the URL by its path, counts, and puts the query back. `count.js` stays
  the upstream copy (CAT-25).

  The query also travels as the next page's referrer. `count.js` sends
  `document.referrer` as `r` when no referrer is set, and within one
  site the browsers' default policy, `strict-origin-when-cross-origin`,
  hands on origin, path and query
  ([MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy),
  read 2026-11-22). A card followed from `/generators/?q=helm` would
  send `helm` with the generator page's count. Every page therefore
  carries `<meta name="referrer" content="strict-origin">`, and a link
  within the site hands on the origin alone. In Chrome 156 on
  2026-11-22, `document.referrer` after such a link held the full URL
  without the meta element and the origin with it. To other sites over HTTPS
  the policy sends the origin, as the default does. GoatCounter loses the
  path of a referrer inside the site, which nothing reads; the referrers
  per network that CAT-36a compares come from other sites. The policy
  sits in a meta element because the site cannot set response headers on
  GitHub Pages, as for the CSP. A `referrer` callback in `site.js` would
  keep the internal paths, but it would have to run before `count.js` on
  every page.

  - Test: `catalog/test_catalog.py` (`Site.test_counter_sees_no_query`:
    the referrer meta element on every HTML page of the fixture build,
    `no_onload` on `/generators/` and `/recipes/`, and the count in
    `site.js` with the query removed); `catalog/browser.mjs` through
    `InChrome.test_rendered_pages`: it opens `/generators/?q=httproute`
    on the fixture build, which finds the fixture's `demo`, follows the
    card to its generator page, and finds `httproute` in no request to
    the counter
  - Since: #711

- CAT-42: Copying a fetch inventory or a verify command, and following
  the link to a generator's source repository or to a recipe's folder in
  kadet-hub/recipes, MUST count as a GoatCounter event. The event's name
  MUST be the action, `copy-fetch-inventory`, `copy-verify` or
  `source-repo`, a `/`, and the page, `generators/<name>`,
  `recipes/<name>` or `quickstart`. The privacy page MUST name the
  events.

  Page views show which pages are read, not whether a reader went on to
  use a generator or recipe. These three actions are the closest the
  static site gets to that. The elements carry `data-goatcounter-click`,
  which the shipped `count.js` binds on load (`bind_events`), so the site
  needs no script of its own. An event goes to the same endpoint as a page
  view, with `navigator.sendBeacon` or an image, so the CSP of CAT-25
  stays as it is.

  GoatCounter takes the event's name as its path, which must not start
  with `/`, and sends no referrer with an event, so the name carries the
  page. A copy button sets `data-goatcounter-title` to its label, because
  GoatCounter otherwise sends the element's HTML, the icon's SVG. A click
  on a copy button counts also when the browser refuses the copy. Without
  `params.goatcounter` no counter loads and the attributes do nothing.

  - Test: `catalog/test_catalog.py` (`Site.test_conversion_events`,
    `Quickstart.test_commands`)
  - Since: #540

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
  target, interpolation, inventory backend, ref, kadet, dependency), then
  kadet-hub's own (generator, fixture, recipe, proof level, fetch
  inventory, kind, custom resource and CRD, operator, gate, sandbox,
  server-side dry run, output capability, output diff, krab, consumer
  workflow), then the supply chain (OCI artifact, digest, SBOM,
  provenance, attestation, index, yanked). A Kapitan concept links its
  page in the Kapitan documentation, a Kubernetes concept its page in the
  Kubernetes documentation. Entries live in the front
  matter of `content/glossary.md`, so the list and the JSON-LD come from
  the same text; each `DefinedTerm` has the entry's name, its definition
  as plain text and its URL with the anchor.

  Guides, recipe pages and posts link the first use of a term in body
  text to `/glossary/#<id>`, not in headings, code or existing link
  text, and only where the word has the glossary's meaning: "kind" in
  "kind cluster" is the tool, not a Kubernetes kind. The glossary's title
  and description follow CAT-11 and CAT-11a and name Kapitan with
  Kubernetes. Both name Kapitan terms the glossary defines, so that a
  searcher who typed one sees it in the result. Which terms they name is
  a choice, not measured search volume.

  Related: CAT-11, CAT-11a, CAT-37.

  - Test: `catalog/test_catalog.py` (`test_glossary`)
  - Since: #286; fixture, proof level, operator and the recipe entry for
    kadet-hub/recipes: #371; inventory backend, dependency, fetch
    inventory, sandbox and consumer workflow: #687; Kapitan terms in the
    title: #725

- CAT-5: URLs `/`, `/generators/` and `/generators/<name>/` MUST stay
  stable.
  - Test: none
  - Since: #16; `/generators/`: #710

- CAT-6: `/` MUST link to `docs/consumers.md` and `docs/authors.md`.

  `docs/authors.md` describes registration for authors: manifest, fixture
  project, entry and what the gate and the review check, and when a
  generator is worth writing and when another Kapitan input is the better
  tool, with ideas for generators, and how to patch a Helm chart instead of
  wrapping it in a generator (DEC-15). The root `README.md` points to the
  catalog and both documents, and the template repository
  `kadet-hub/generator-template` starts a generator with the files the gate
  expects, a local check and `AGENTS.md` for coding agents.

  On `/` the links are the navigation's "Use" and "Publish", since the
  start page's hero has no buttons (CAT-67).

  - Test: `catalog/test_catalog.py` (`test_home_links_both_guides`)
  - Since: #18, #158

- CAT-6a: `/generators/` MUST say so when no generator is listed.

  The start page shows no catalog, so the empty state moves with the
  cards (CAT-67a) and links `docs/authors.md` to add the first one.

  - Test: `catalog/test_catalog.py` (`test_empty_index_says_so`, which
    reads `/generators/` once the catalog moves there)
  - Since: #18, #158 on `/`; at `/generators/`: #710

- CAT-56: `README.md` MUST link the playground at
  `https://kadet-hub.org/playground/` above its first `##` heading.

  GitHub shows the README as the repository's front page. It said what
  the registry is and linked the documents, but had no example and no way
  to see compiled output without installing Kapitan. The playground
  compiles in the browser ([playground.md](playground.md)), so it is the
  shortest path from the README to output. Below the link, the README
  says what a generator and a recipe are and how they map to a Helm chart.

  - Test: `catalog/test_catalog.py` (`Quickstart.test_readme`)
  - Since: #682

- CAT-56a: The quickstart in `README.md` MUST use the install command and
  the compile commands of `/quickstart/` (CAT-40) and MUST NOT pin a
  recipe version.

  The quickstart compiles the uptime-kuma recipe without a cluster, for a
  reader who knows Kapitan, and links `/quickstart/` for the way to a
  running app. The reader saves the fetch inventory from the recipe page,
  whose build writes the latest version and digest (CAT-38). Nothing
  updates a pin in the README, so one written there would go stale with
  the recipe's next release. The test compares the install command with
  the quickstart page, which `Quickstart.test_commands` compares with
  `docs/consumers.md`.

  Run on 2026-11-12 in a shell with an empty home directory and an empty
  uv cache, with the fetch inventory of uptime-kuma 1.0.1 from its recipe
  page: the install, the project files and both compile commands took 22
  seconds. The first compile command exited with status 1 as the README
  says, and the second wrote a StatefulSet and a Service under
  `compiled/uptime-kuma/manifests/`.

  - Test: `catalog/test_catalog.py` (`Quickstart.test_readme`, partial:
    the target, which comes from the recipe's README in kadet-hub/recipes);
    manual: the run above
  - Since: #682

- CAT-56b: Every row of the Helm comparison in `README.md` MUST link a
  guide of the site that backs it.

  A comparison on the front page is read as a claim about Helm. The
  guides measured each difference on real charts or a script, so a reader
  can check the row there.

  - Test: `catalog/test_catalog.py` (`Quickstart.test_readme`, partial:
    the guide exists; whether it backs the row is a review question)
  - Since: #682

## Visual identity

The site still wears the look it started with: the system font stack, an
indigo accent (`--accent`, `#3346d3` in light), card tiles coloured by a
hash of the generator's name and a white K on a blue square as its mark
(`static/favicon.svg`). Nothing in it refers to Kapitan or to kadet, and
the section on how a version gets listed, the reason to take a generator
from here, sits below the card grid.

The redesign takes its motif from Kapitan's own wording. Kapitan is the
word for captain in several Slavic languages, and kapitan.dev names its
site "Kapitan: Keep your ship together" (`og:site_name`, checked
2026-11-21). A kadet module is then the cadet, and kadet-hub the harbour
where cadets are checked, signed and handed out.

The direction is "Harbour". The operator chose it on 2026-11-21 from six
mockups and approved its look on 2026-11-22 on a rendered preview of real
pages. It replaces "Chart Room", merged on 2026-11-21 with #703 and built
in #705 and #706; the table of directions below holds the reason. The
preview build is not part of the repository. The reference files in
[harbour/](harbour/README.md) are drawn from it, and this spec states
the look it showed. A requirement marked not implemented binds the
implementation whether the preview met it or not.

The light theme has a cool near-white ground, white surfaces and navy
text, with no beige and no graticule. Indigo is the main hue: links, the
selected station, the kubernetes container and what it writes. Teal is
the second: the terraform-aws container and what it writes, the Recipes
tile, the values the live edit changes, the signal after a passed check
and an attested result in a diagram. Orange marks kadet-hub's check: the
customs gate, its scan, its seals and its signal before the check, and
the sealed containers of the catalog's and the generator page's spot
drawings. Besides it, orange marks only a page's primary button, the
failure paths of the diagrams (CAT-35a) and small accents in the other
spot drawings, at most one per drawing (CAT-73j). Its darker
shades are the text of the "kadet-hub" chip and the focus ring. Light is
the default polarity because adults with normal vision read dark text
on a light ground slightly but reliably better, more so at small sizes
(NN/g, reporting the measurements of Piepenbrock et al. 2013 and 2014).
The dark theme stays, as the operator decided on 2026-11-21, and follows
`prefers-color-scheme` and the toggle. It is the same harbour at night:
navy ground, light indigo text, dark water and land, and the objects of
the scene in their day colours.

The terminals and files of the figure (CAT-66), the target of the live
edit (CAT-68) and the code snippets of generator and recipe pages are
dark panels in both themes. A panel sets `color-scheme: dark` and
declares `color: var(--text)` and `background: var(--bg)` again. A custom
property is substituted where it is used, so the tokens resolve to their
dark values inside the panel, while an inherited `color` would keep the
light value computed on `body`. Every text on a panel then has a pair of
the dark column. Code blocks in running text stay on `--bg-subtle`.

Headings use Sora at weight 600 and body text Manrope at weight 500, both
at their normal width (CAT-60). Code and digests keep the system
monospace stack of `--mono`.

The light values are the mockup's unless the table says "derived". The
dark `--bg`, `--surface`, `--text` and `--text-muted` are the colours of
the mockup's dark panels; the other dark values are this spec's.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--bg` | `#f4f5fb` | `#1c1b3a` | page ground, the ground of a dark panel |
| `--bg-subtle` | `#e9ebfa` | `#232249` | the live edit's band, code in running text, inline code, tag pills, a diagram's cluster |
| `--surface` | `#ffffff` | `#2a2952` | cards, tiles, fields, the station panel, the scene's pills and labels, a diagram's ground |
| `--text` | `#1c1b3a` | `#e3e4fd` | text |
| `--text-muted` | `#48476b` | `#b9bdf6` | secondary text, placeholders |
| `--accent` | `#3b3fc4` | `#a5a8fa` | links, the selected station, a diagram's flow |
| `--accent-strong` | `#1c1b3a` | `#e3e4fd` | link hover |
| `--accent-bg` | `#e3e4fd` | `#2e2f6b` | the "Kapitan" chip, station numbers, the Guides tile, a diagram's nodes |
| `--on-accent` | `#ffffff` | `#1c1b3a` | text on `--accent` |
| `--teal` | `#18a999` | `#18a999` | the Recipes tile |
| `--on-teal` | `#07211d` | `#07211d` | text on `--teal` |
| `--teal-bg` | `#b9efe6` | `#0e4d45` | the values the live edit changes and a diagram's attested result, under `--text` only |
| `--teal-line` | `#118a7b` | `#2ec4b3` | the edge of a teal ground: a diagram's attested result |
| `--signal` | `#e26a1f` | `#e26a1f` | the primary button, a diagram's failure path |
| `--on-signal` | `#1c1b3a` | `#1c1b3a` | text on `--signal` |
| `--signal-text` | `#7a3208` | `#ff8a3d` | orange as text: the "kadet-hub" chip, a failure label in a diagram |
| `--signal-bg` | `#ffe3cf` | `#3a2418` | the "kadet-hub" chip, a diagram's failure node |
| `--focus` | `#bc5718` | `#ff8a3d` | focus ring; light derived from `#e26a1f` |
| `--border` | `#dfe0f2` | `#3a3970` | decorative rules, card edges, station buttons |
| `--border-strong` | `#787dc1` | `#8286cc` | field borders; light derived from `#c9cbe6` |
| `--warn`, `--warn-bg` | `#9a3412`, `#fff1e7` | `#fdba74`, `#3a2112` | failures and warnings, the current values |
| `--ok`, `--ok-bg` | `#166534`, `#e8f7ee` | `#86efac`, `#12301e` | passed checks, the current values |
| `--shadow-c` | `rgb(28 27 58 / 6%)` | `rgb(0 0 0 / 40%)` | card shadow; light derived |
| `--shadow-lift-c` | `rgb(59 63 196 / 45%)` | `rgb(0 0 0 / 50%)` | the search field, the selected station, a card under the pointer |

The grade colours of CAT-39 keep Artifact Hub's values in both themes.

The scene's tokens follow. Its ground, land and shadows change with the
theme; its objects keep their colours. Each object family has a top, a
right and a left face, as the light falls in the reference drawings,
which use no colour outside the two tables (CAT-69g). The live edit's two
island icons and the cubes of the cards take the same families.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--sc-water` | `#cdd5fb` | `#232262` | the scene's ground, the head band of inner pages |
| `--sc-shallow` | `#dbe1fd` | `#2b2a72` | shallow water around the islands |
| `--sc-shade` | `#d9defb` | `#b4b3e6` | shadows, multiplied over what lies below |
| `--sc-shade-road`, `-water`, `-deck` | `#cbcff4`, `#b7c1f6`, `#b2b5f4` | `#25245f`, `#1b1a52`, `#b2b5f4` | solid shadows of parts that move, since a moving group cannot multiply over what lies below |
| `--sc-land-t`, `-r`, `-l` | `#ffffff`, `#b9bdf6`, `#9ea3f2` | `#3a3984`, `#302f70`, `#282763` | quay, yard and islands |
| `--sc-road` | `#dfe1f7` | `#2e2d6c` | the lane |
| `--sc-foam` | `#ffffff` | `#5655a8` | waves, swell, wake, routes, road markings |
| `--sc-light`, `--sc-wht-r`, `--sc-wht-l` | `#ffffff`, `#e9eafd`, `#cfd2fb` | the same | the white family: plates, the cargo list, windows, the ship's superstructure, the top container of the catalog's drawing; text on the hull and on the cargo list's head |
| `--sc-ink` | `#1c1b3a` | the same | text on plates and on the cargo list, cables, the shield's outline |
| `--sc-ind-t`, `-r`, `-l` | `#e3e4fd`, `#a5a8fa`, `#8a8ef7` | the same | the harbour office's walls, details of the ship and of the crane's trolley, containers in the inner pages' drawings |
| `--sc-kub-t`, `-r`, `-l` | `#b0b4ff`, `#5b61ea`, `#454acf` | the same | the kubernetes container, what it writes and the store on its island |
| `--sc-hull-t`, `-r`, `-l` | `#c7c9fb`, `#4347c4`, `#34379f` | the same | the ship's hull and deck, the crane, the truck's frame, the feet of the gate, the Generators tile |
| `--sc-teal-t`, `-r`, `-l` | `#b9efe6`, `#18a999`, `#118a7b` | the same | the terraform-aws container, what it writes and its island, trees, the signal after the check |
| `--sc-or-t`, `-r`, `-l` | `#ffd2b3`, `#ff8a3d`, `#e26a1f` | the same | the customs gate, the seals, the signal before the check, the lashings of the recipe drawing |

The ratios below are computed with the WCAG 2 formula from these hex
values and rounded down to two decimals, light first. Every text token
(`--text`, `--text-muted`, `--accent`, `--accent-strong`,
`--signal-text`, `--warn`, `--ok`) reaches at least 5.69:1 on every
ground of the first table (`--bg`, `--bg-subtle`, `--surface`,
`--accent-bg`, `--signal-bg`) in light, lowest `--ok` on `--accent-bg`,
and 5.16:1 in dark, lowest `--signal-text` on `--accent-bg`. The lowest
text pair of each theme is on a fill: `--on-signal` on `--signal`,
4.98:1 in both. The other fills give `--on-accent` on `--accent` 7.79:1
and 7.56:1, `--on-teal` on `--teal` 5.76:1 in both, `--text` on
`--teal-bg` 13.06:1 and 7.74:1, `--warn` on `--warn-bg` 6.60:1 and
8.85:1, and `--ok` on `--ok-bg` 6.44:1 and 10.19:1. The Generators tile
keeps `--sc-hull-r` in both themes, with `--sc-light` text at 7.15:1 and
its count in the reverse pair; the Recipes tile's count is
`--sc-teal-t` on `--on-teal`, 13.30:1.

In the scene, text stands on plates, on the hull and on pills. In both
themes `--sc-ink` reaches 16.57:1 on `--sc-light` and `--sc-light` 7.15:1
on `--sc-hull-r`. A station's pill and an island's label have `--text`
on `--surface`, 16.57:1 and 10.91:1, a label's path `--text-muted` on
`--surface`, 8.78:1 and 7.59:1, and a pill's number `--accent` on
`--accent-bg`, 6.22:1 and 5.52:1. Selected, the pill has `--on-accent`
on `--accent`, 7.79:1 and 7.56:1, and its number `--accent` on
`--surface`, 7.79:1 and 6.23:1. In a diagram on `--surface`, a failure
label in `--signal-text` reaches 9.18:1 and 5.82:1, and 7.49:1 and
6.19:1 inside its node on `--signal-bg`.

`--focus` reaches at least 3.71:1 on every ground of the first table in
light, lowest on `--accent-bg`, and 3.21:1 on `--sc-water`; in dark
5.16:1, lowest on `--accent-bg`. The mockup's ring, `#e26a1f`, reaches
2.65:1 on `--accent-bg` and 2.80:1 on `--bg-subtle`, so the light value
is that hue darkened until it holds 3.2:1 on every light ground.
`--border-strong` reaches 3.22:1 on `--bg-subtle`, 3.50:1 on `--bg` and
3.81:1 on `--surface`, the field's own fill, in light, and 4.05:1 on
`--surface`, 4.46:1 on `--bg-subtle` and 4.91:1 on `--bg` in dark; a
field inside a dark panel takes the dark values. The mockup's field
border, `#c9cbe6`, reaches 1.46:1 on `--bg`, so the light value is that
hue darkened until it holds 3.2:1 on `--bg-subtle`. The search button's
`--signal` reaches 3.32:1 on the field's `--surface` in light and 4.10:1
in dark. In a diagram on `--surface`, a flow line in `--accent` reaches
7.79:1 and 6.23:1, a failure line in `--signal` 3.32:1 and 4.10:1, and
the edge of an attested result in `--teal-line` 4.24:1 and 6.28:1. All of
these are above the 3:1 that WCAG 2.2 asks of non-text contrast.
`--border` stays below it, 1.20:1 on `--bg` in light and 1.57:1 in dark,
and marks nothing a visitor must see: the station buttons are known by
their labels.

These colours never carry text: `--signal`, which reaches 2.65:1 to
3.32:1 on the light grounds, `--focus` in light, 3.71:1 to 4.65:1,
`--border`, `--border-strong`, `--teal`, 2.92:1 on white, and
`--teal-line`, 4.24:1 on white. The `-bg` tokens, `--sc-water` and the
faces of the scene are grounds and carry text only in the pairs above.
`--accent` on `--teal-bg` would reach 4.42:1 in dark.

`--warn`, at a hue of about 15 degrees, sits next to the signal orange at
about 23. A warning therefore differs by more than its hue: it opens with
the warning icon and says in words what failed (CAT-59c). kadet-hub's
verify step is the seal with a check in the scene and the "kadet-hub"
chip, never a warning, and a diagram's failure path is dashed and
labelled as well as orange (CAT-35a).

| Direction considered | Why not |
|---|---|
| Bridge: dark first, values as cyan and amber instrument readouts, IBM Plex | The operator preferred Chart Room when comparing the mockups |
| Kilo: the yellow and blue signal flag K as the mark, flat colour blocks, Space Grotesk | Flag yellow `#FFC20E` reaches 1.6:1 on white, so it can carry no text and only grounds ink; the flag stands for the letter K, not for Kapitan |
| Chart Room: a paper ground `#f4efe4` with a graticule, navy ink, Archivo headings expanded to 125 %, a K with a cadet's chevron on an ink tile | Rejected by the operator on 2026-11-21 after seeing it rendered in #705 and #706: he disliked the beige ground and the expanded headings and called the result generic |

One implementation pull request from `main` builds this spec. #705 and
#706 are closed with a pointer to it, and their parts that still hold are
ported: the `font-src` line of the CSP, the Reference disclosure, the
`/generators/` split, the search form with its `q` handling, the guides'
links to the catalog and the test scaffolding. The operator decided both
on 2026-11-21. `release.yml` deploys every push to `main`, and
`style.css` is the one stylesheet of every page ("Page types"), so the
one merge restyles every page type at once, with no interim state. A
revert of its commit restores the old look.

The implementation pull request changes these existing tests: the CSP
strings in `test_badge` and `test_goatcounter_counts_from_the_own_origin`;
`Playground.test_highlight_colours_reach_aa`; `Site.test_text_reaches_aa`,
which gains every text token on every ground of the first table, the
fill pairs, the scene pairs and at 3:1 `--focus` and `--border-strong`,
whose parser reads only `light-dark(#x, #y)`, so a token equal in both
themes is written `light-dark(x, x)`, and whose opacity check leaves out
`@keyframes`, where a fractional opacity is a step of an animation
(CAT-69f); `test_quickstart_linked`, which expects "Use" right after
"Quickstart" and finds "Generators" there (CAT-67c); `test_wanted_page`,
whose links of CAT-31 are no longer hero buttons; `test_diagram_svgs`,
whose diagrams take classes instead of colours (CAT-35a); and the catalog
tests that read `/`, which read `/generators/`. Four weeks before and
after the release the operator compares the weekly CAT-42 events
(`copy-fetch-inventory`, `copy-verify`) on the GoatCounter instance of
CAT-25, since `/stats/` shows no visitor numbers (CAT-33); a drop is a
reason to revisit the design, at this traffic not a measurement of it.

Related: LEG-5, CAT-2, CAT-3, CAT-9a, CAT-11b, CAT-11f, CAT-22, CAT-35a,
CAT-42, CAT-54, CAT-55, CAT-58b, CAT-64, CAT-66, CAT-67, CAT-68, CAT-73.

- CAT-59: Every colour in `static/style.css` MUST come from a custom
  property defined on `:root` with a light and a dark value.

  The theme is then one token block. Today the grade colours
  (`.grade-a` and its siblings), the `.chroma` highlight rules and the
  `.hue-*` tiles set colours in their rules. A shadow takes its colour
  from a token (`0 1px 2px var(--shadow-c)`): `light-dark()` accepts
  colours only, so the current `--shadow: light-dark(<shadow>, <shadow>)`
  is invalid and Chrome renders no card shadow in either theme (checked
  on the live site on 2026-11-21). CAT-54 still applies to the rendered
  page, which AC-50 measures on every page type.

  - Test: `catalog/test_catalog.py` (`Site.test_text_reaches_aa`: every
    token of both tables with a light and a dark value, and its pairs;
    `Site.test_colours_only_in_tokens`)
  - Since: #710

- CAT-59a: Rules outside `:root` MUST NOT set a colour literal or a named
  colour other than `transparent` and `currentColor`.

  - Test: `catalog/test_catalog.py` (`Site.test_colours_only_in_tokens`:
    no hex, `rgb()`, `hsl()` or named colour outside `:root`)
  - Since: #710

- CAT-59b: The focus ring MUST stand at least 2 px off the element it
  marks.

  `--focus` reaches only 1.39:1 on `--signal` in light and 1.41:1 in
  dark, so a ring on the edge of the primary button would vanish into
  it. With `outline-offset` of 2 px or more the ring lies on the ground
  around the element, where the pairs above hold; the search button sits
  on the field's `--surface`, 4.65:1 and 5.82:1.

  - Test: `catalog/test_catalog.py` (`Site.test_focus_ring_stands_off`:
    the `:focus-visible` rule sets `outline-offset` of 2 px, and no rule
    sets a smaller one)
  - Since: #710

- CAT-59c: Every warning MUST open with the warning icon.

  The warnings are the `.warning` lines of every page, such as
  "Yanked: …" on a generator page or the playground's notices, and the
  ones a script fills keep the icon in the markup. The icon sprite
  has no warning icon today; the implementation adds Lucide's warning
  triangle to it. Icon and words set a warning apart from the signal
  orange, which marks kadet-hub's verify step.

  - Test: `catalog/test_catalog.py`
    (`Site.test_warnings_open_with_the_icon`,
    `ListedRecipe.test_digests_and_warnings`,
    `Security.test_warnings_open_with_the_icon`: every `.warning` of the
    generator, recipe, quickstart and security pages of the fixture
    builds starts with the icon)
  - Since: #711

- CAT-60: The site's only web fonts MUST be Sora and Manrope, each
  served as one variable WOFF2 file from its own directory under
  `static/fonts/`, beside its `OFL.txt`.

  CAT-3 rules out a font host, and `font-src` falls back to
  `default-src 'none'`, which blocks fonts from the site too (CAT-60a).
  The directories are `static/fonts/sora/` and `static/fonts/manrope/`,
  since both licence files are named `OFL.txt`. Both families have a
  `wght` axis and no width axis, so no rule sets `font-stretch`. Each
  `@font-face` declares the file's weight range, 100 to 800 for Sora and
  200 to 800 for Manrope, whose default instance is its lightest weight.
  The mockup's third family, JetBrains Mono, is not shipped.

  Neither upstream repository has tags or releases (GitHub API,
  2026-11-21), so the files are cut from pinned commits:

  - Sora: `fonts/variable/Sora[wght].ttf` of sora-xor/sora-font at
    `7f9a9c5d0ccd1c099cfac420aa27133df1c5fdc4`, its latest commit
    (2022-09-05), version 2.000, 111,400 bytes, SHA-256
    `84ff7096ae3ec6c8be47d906d1a0ba4de7f2ce78c615275c77301964a316e16c`.
  - Manrope: `fonts/variable/Manrope[wght].ttf` of googlefonts/manrope at
    `468c0dbe38efa331b80bfe9448256abe27be44c3`, its latest commit
    (2026-09-14), version 4.505, 164,700 bytes, SHA-256
    `3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6`.
    `ofl/manrope/METADATA.pb` of google/fonts names this repository as
    the upstream; the earlier one, sharanda/manrope, returns 404.

  Both files have the git blob hash of the files google/fonts ships, so
  they are the same bytes. Both fonts are licensed under the SIL Open
  Font License 1.1. The `OFL.txt` at each commit names no Reserved Font
  Name after its copyright line, so a subset may keep the family name;
  the name table of each font states the same licence (name ID 13), and
  `fsType` 0 sets no embedding restriction. Each file is subset to Latin
  with fonttools' `pyftsubset`, keeping the `wght` axis. The commit, the
  SHA-256 of source and WOFF2, the command and the file size go into the
  implementation inventory of [marketplace.md](marketplace.md), as
  CAT-58b records its font. `font-display: swap` shows text in the
  fallback stack until a file arrives; a fallback `@font-face` with
  `size-adjust` per family reduces the layout shift, and the merge
  request checks the swap of the `h1` at 375 and 1440 px. In the preview
  build of 2026-11-22 the two files had 30,136 bytes (Sora) and 22,820
  bytes (Manrope).

  - Test: `catalog/test_catalog.py` (`Site.test_fonts`: every `url()`
    source of an `@font-face` is under `static/fonts/<family>/` with an
    `OFL.txt` beside it, the families are Sora and Manrope only, the
    fallback faces use `local()` only, no rule sets `font-stretch`);
    manual: the swap of the `h1` at 375 and 1440 px
  - Since: #710

- CAT-60a: The CSP MUST allow fonts with `font-src 'self'` and no other
  source.

  The fonts are files and the scene is inline SVG, so neither needs
  `data:`; the CSP gains no `data:` and no `unsafe-` source either.

  - Test: `catalog/test_catalog.py` (`Site.test_csp`: the CSP of every
    page has `font-src 'self'`, no `data:` and no `unsafe-`)
  - Since: #710

- CAT-61: The mark MUST be `static/favicon.svg`, drawn as
  `docs/specs/harbour/mark.svg`: an isometric cube in three indigo faces
  with a white K across its front, clipped to the cube's outline, without
  a tile.

  The faces are `#8a8ef7` on top, `#4347c4` left and `#5b5fe0` right, and
  the K is drawn in strokes 12 units wide. The header shows the mark as
  an `img`, which neither the page's tokens nor its theme toggle reach,
  so its colours are fixed and have to hold on both grounds. Two faces
  reach 3:1 against each: on the light `--bg` the left face 6.57:1 and
  the right 4.64:1, on the dark `--bg` the top 5.75:1 and the right
  3.28:1. The cube's outline therefore stays without a tile. CAT-58b
  found that Kapitan's repository has no logo policy and that section 6
  of its Apache 2.0 license grants no trademark rights; the Kapitan logo
  is a figure, not a letter, so a K on a cube does not imitate it. The
  scene borrows the harbour, not Kapitan's tagline or artwork (CAT-61a).

  - Test: manual: `static/favicon.svg` against
    `docs/specs/harbour/mark.svg` in the merge request
  - Since: #710

- CAT-61b: `static/apple-touch-icon.png`, `static/og.png` and the Open
  Graph base image of CAT-58b MUST be rasterised from the mark of CAT-61.

  - Test: manual: review of the three PNGs in the merge request
  - Since: #710

- CAT-61c: `static/apple-touch-icon.png` and `static/og.png` MUST have an
  opaque ground.

  The mark has no tile (CAT-61), and iOS fills the transparent parts of a
  touch icon with black. The touch icon takes the light `--bg`, and
  `og.png` the dark `--bg` of the post cards (CAT-58a).

  - Test: `catalog/test_catalog.py`
    (`Site.test_touch_icon_and_og_image_are_opaque`: neither PNG has an
    alpha channel)
  - Since: #710

- CAT-61a: The mark and the site's copy MUST NOT use Kapitan's
  artwork or its tagline, or call kadet-hub official.

  The footer keeps saying that kadet-hub is not affiliated with the
  Kapitan project.

  - Test: manual: review of the mark in the merge request, and a
    case-insensitive search of `catalog/site/` for "keep your ship" and
    "official kapitan" that finds nothing
  - Since: #710

- CAT-70: The mark MUST stay legible at 16 px.

  In a mark 86 units high, the K's strokes of 12 units are 2.23 px wide
  at 16 px, 4.47 px at 32 px and 25.12 px at 180 px, the touch icon. White
  reaches 7.15:1 on the left face and 5.05:1 on the right, and 2.87:1
  where the stem and the upper arm reach into the top face. Rendered with
  rsvg-convert 2.63.4 on 2026-11-22, the K reads at 16, 32 and 180 px.
  WCAG exempts a logo from contrast, and one SVG serves every size
  (CAT-61b), so a browser tab settles it.

  - Test: manual: the favicon at 16 and 32 px in a browser tab with light
    and dark browser chrome, and `apple-touch-icon.png` at 180 px, in the
    merge request
  - Since: #710

The code of the registry is licensed under Apache-2.0; the name, the mark
and the drawings are not (DEC-52 in [marketplace.md](marketplace.md)).
The operator took this decision on 2026-11-22 without legal review
(DEC-51). Its point for a visitor is that kadet-hub's look proves
nothing: a copy of the site can wear it, so the genuine source is named
and checked by attestation.

- CAT-78: The repository MUST hold a file `NOTICE` that excludes the name
  "kadet-hub", the mark and the drawings from the Apache-2.0 licence and
  reserves all rights to them, allowing their use only to refer to
  kadet-hub.

  The drawings are the start page's scene and the inner pages' drawings.
  The notice lists the files that hold them and the mark: the partials
  the scene's generator writes, the reference files in
  `docs/specs/harbour/`, `static/favicon.svg`,
  `static/apple-touch-icon.png`, `static/og.png` and the Open Graph base
  image.

  - Test: `catalog/test_catalog.py` (`Site.test_notice`: `NOTICE` names
    every file the scene's generator writes and every file of
    `docs/specs/harbour/` with an `.svg` extension)
  - Since: #710

- CAT-78a: The footer of every page MUST say in one sentence that the
  name, the mark and the drawings are not under the code's licence, and
  link `NOTICE`.

  - Test: `catalog/test_catalog.py` (`Site.test_notice`: the sentence
    and its link in the footer of every page of the fixture build)
  - Since: #710

- CAT-78b: The section "Verifying by hand" of `docs/consumers.md` MUST
  state that the genuine site is kadet-hub.org and the genuine artifacts
  are under `ghcr.io/kadet-hub`, checked by their attestation and not by
  the look of a page.

  The footer's "How to verify" links this section.

  - Test: `catalog/test_catalog.py` (`Site.test_notice`: the sentence in
    the section)
  - Since: #710

- CAT-78c: The imprint's sentence on the licence MUST say that the
  name, the mark and the drawings are excluded from Apache-2.0, and link
  `NOTICE`.

  Today it says that the site's texts and code are published under the
  Apache License 2.0, which without the exclusion says the opposite of
  DEC-52.

  - Test: `catalog/test_catalog.py` (`Site.test_notice`: the imprint
    page of the fixture build names the exclusion and links `NOTICE`)
  - Since: #710

- CAT-62: The section "How a version gets listed" MUST close the start
  page, after "Where to go next" (CAT-67), with its approved copy.

  The steps are what sets a listed generator apart from a chart found
  elsewhere. With the cards on the home page a visitor read them only
  after scrolling past every card; with the cards at `/generators/`
  (CAT-67a) the start page has no grid to pass, and the steps follow the
  destinations. The section keeps its `h2` with an `h3` per step and its
  links, so CAT-11b holds. The mockup does not show it, so it takes the
  type and tokens of the page and no motif of its own; Chart Room drew it
  as a route on the chart.

  CAT-62b, which #705 published for a compact row of hero buttons on
  phones, is not carried over, since the hero has no buttons (CAT-67).
  The ID stays unused.

  - Test: `catalog/test_catalog.py`
    (`Site.test_listing_steps_close_the_start_page`: `<h2 id="listing">`
    after the `h2` "Where to go next" in the HTML of `/`;
    `Site.test_headings_skip_no_level`, `test_how_kadet_hub_works`)
  - Since: #710

- CAT-62a: Below 48rem the steps of that section MUST be collapsed under
  its `h2`.

  They sit in a `details` element that `site.js` closes on narrow
  screens, the CAT-9a pattern, so without JavaScript they stay open. On a
  phone they come after the scene, five stations, the live edit and six
  tiles; collapsed, their heading tells the visitor who gets there what
  they hold.

  - Test: `catalog/test_catalog.py`
    (`Site.test_listing_steps_close_the_start_page`: the `details`
    around the steps); manual: 393 px, the steps collapsed under their
    heading
  - Since: #710

- CAT-63: The site navigation MUST link Tags, Kinds, Compatibility and
  Glossary under one disclosure "Reference" instead of one link each.

  The header has 13 links today, which CAT-9a folds into a menu below
  48rem. The four pages are reference material, so they share an entry;
  each keeps its URL (CAT-5). The disclosure is a `details` element, so
  it opens without JavaScript; `site.js` adds the closing, which its
  Escape handler today does only for the open mobile menu; CAT-63a and
  CAT-63b state its behaviour. CAT-40a and CAT-47 keep their order:
  Quickstart first, Stacks after Recipes. The operator decided this on 2026-11-21, and
  kept the generator page's order of CAT-19 the same day.

  The disclosure is named "Reference" at every width. Below 48rem it
  sits in the menu of CAT-9a like the other links, so the menu holds a
  nested disclosure that opens on a tap, with or without JavaScript, one
  tap from its links.
  CAT-9a's check of the nav then finds all 13 links, four of them inside
  the disclosure, and 14 with "Generators" of CAT-67c.

  - Test: `catalog/test_catalog.py` (`Site.test_reference_disclosure`:
    the header links and the disclosure)
  - Since: #710

- CAT-63a: The "Reference" disclosure MUST close on Escape and when focus
  leaves it.

  - Test: manual: Escape and Tab out of the open disclosure at 1440 px
  - Since: #710

- CAT-63b: The open "Reference" disclosure MUST NOT cover the element
  that has focus.

  WCAG 2.2 criterion 2.4.11 rules out a dropdown that hides the focused
  link below it.

  - Test: manual: Tab through the open disclosure and the page below it
    at 1440 px
  - Since: #710

- CAT-64: A digest in a code panel MUST show its first and last eight
  hex characters around a marked ellipsis, and keep the whole value in
  its copy text and its title.

  This covers every code panel: the figure's terminals and files, the
  live edit and the snippets of generator and recipe pages and of the
  quickstart. The middle of the digest stays in the text at no size, so
  the copy button and a selection take all 64 characters, and the
  `title` shows them.

  What is lost: a reader who compares a panel with another source by eye
  sees 16 of 64 hex characters, 64 bits. A forged digest that matches
  those 16 takes about 2^64 attempts, so the shortened form is a safer
  display than a highlighted prefix of eight characters, 32 bits; it is
  still a display and not a check. The whole digest stands once on the
  page (CAT-64a) for a reader who compares by eye, and verification is
  the command of CAT-2. A digest written by hand into the prose of a post
  or guide may be shortened the same way, since the reader copies
  nothing from it.

  - Test: `catalog/test_catalog.py` (`Site.test_digests_in_code_panels`,
    `ListedRecipe.test_digests_and_warnings`,
    `Quickstart.test_digests_in_code_panels`: every `sha256` digest of a
    code panel of the fixture builds shows eight and eight characters
    with the ellipsis mark, and its title and its text hold all 64)
  - Since: #711

- CAT-64a: A page that shows a shortened digest MUST show it whole once,
  set in two equal halves.

  The halves stand on one line where both fit and one under the other
  where they do not, and a half never breaks. On the start page the
  station Inventory lists both pins whole; on a generator page the
  version's record does.

  - Test: `catalog/test_catalog.py` (the tests of CAT-64: on each page
    of the fixture builds, every shortened digest also stands whole
    once, in an element of two halves of 32 characters)
  - Since: #711

- CAT-65: The home page hero MUST state the notice of LEG-5 in one line
  below its search, linking `TERMS.md`.

  The footer carries the notice on every page, but a visitor who decides
  from the hero whether to pin a generator does not scroll to it. The
  line repeats LEG-5's words (free of charge, as is, best effort, at the
  user's own risk) and adds no promise; TERMS.md holds the liability
  clause German law allows.

  - Test: `catalog/test_catalog.py` (`Site.test_hero_states_the_notice`:
    the line and its link inside the hero of the home page)
  - Since: #710

## Page types

The operator decided on 2026-11-21 that every page of the site follows
Harbour, not only the start page, and on 2026-11-22 that every page
gets a head band. `baseof.html` links one stylesheet, `style.css`, and
every HTML layout of `catalog/site/layouts/` fills its `main` block
(checked on main on 2026-11-21), so the tokens, the fonts and the shared
components reach every page at once.

The start page carries the scene and a hero of its own. Every other page
opens with a head band on the scene's water: its title, its lead and its
breadcrumb, and on the right a small drawing of its section, the spot
drawing. Inner pages get layout work beyond the tokens: the catalog's
cards (CAT-22), two columns of cards on the lists of guides, posts,
stacks and recipes (CAT-79), a three-step block for each version on a
generator page (CAT-74), and from 78rem a rail beside the main column
with the list "On this page" (CAT-19, CAT-75), so a wide screen is used
while running text keeps its measure (CAT-76). Operational pages, such
as the catalog, a generator page, the compatibility table, the kinds, a
security report and the playground, stay dense and put their task first.

The band holds what a page opened with before. Compatibility, stats,
popularity and wanted had no lead and now show their description as one.
The lead of kinds keeps its first sentence, and the rest moves below the
band. Imprint and privacy have no lead. A generator page, a recipe page,
a guide, a kind page and a tag page carry a breadcrumb back to their
list, such as "Generators / kubernetes"; no other page has one.

Each section has one motif, shared by its list and its single pages. The
table names each drawing by its name in `_partials/spot.html`, which is
also the name of its reference, `docs/specs/harbour/spot-<name>.svg`
(CAT-69g). A row can change when its drawing does not read at 184 px.

| Section | Layouts | Spot drawing | Name |
|---|---|---|---|
| Generators | `generators.html` | three containers stacked on a quay corner | `catalog` |
| Generator pages | `page.html` | one sealed container on its bearers | `generator` |
| Recipes | `recipes.html`, `chart-recipe.html` | three containers lashed into one load | `recipe` |
| Stacks | `stacks.html` | a barge with several container stacks | `barge` |
| Playground | `playground.html` | a model ship on a slipway | `basin` |
| Guides | `guides.html`, `prose.html` under `/guides/` | a lighthouse on its rock | `guide` |
| Blog | `blog.html`, `post.html` | a signal mast with flags | `mast` |
| Quickstart | `quickstart.html` | a pilot boat at a quay | `pilot` |
| Popularity and wanted | `popularity.html`, `wanted.html` | a bollard with a line | `bollard` |
| Reference and statistics | `tags.html`, `tag.html`, `kinds.html`, `kind.html`, `compatibility.html`, `glossary.html`, `stats.html`, `security.html` | a tide gauge with a float | `gauge` |
| Legal pages | `prose.html` for `/imprint/` and `/privacy/` | none | |

`generators.html` (CAT-67a) is new; the other layouts are on main.
Stacks have no single pages: `/stacks/` links each stack's blog post,
recipes, generators and example project. Use and Publish in the
navigation link `docs/consumers.md` and `docs/authors.md` on GitHub and
have no page on the site. A legal page added later, such as terms or a
page for removal requests, takes the last row. The Atom feeds,
`/llms.txt`, the Markdown variants, `badge.json` and `robots.txt` carry
no style.

Related: CAT-19, CAT-22, CAT-59, CAT-59a, CAT-60, CAT-66, CAT-69a,
CAT-69b, CAT-69h.

- CAT-71: Every page type MUST take its colours, fonts and shared
  components from `style.css`: the header, the footer, buttons, fields,
  cards, code panels and tables.

  Each component is defined once and looks the same on every page; a
  page adds layout, not colours or fonts of its own.

  - Test: `catalog/test_catalog.py` (`Site.test_one_stylesheet`: every
    HTML page of the fixture build links `style.css` and no other
    stylesheet); manual: AC-50
  - Since: #711

- CAT-71a: `style.css` MUST NOT keep a style of Chart Room or of the
  look before the redesign.

  The check looks for what each left behind: Archivo, `font-stretch` and
  the graticule's `linear-gradient` from #705, the `.hue-*` tiles and the
  system font stack as body font from before. A later edit that brings
  one back fails it.

  - Test: `catalog/test_catalog.py` (`Site.test_fonts`: no `Archivo`,
    `font-stretch`, `linear-gradient` or `.hue-` in the stylesheet, and
    Manrope first in the body's font stack)
  - Since: #710

- CAT-72: The harbour scene MUST appear on the start page only.

  The scene explains the compile once. On another page it would push the
  page's task down.

  - Test: `catalog/test_catalog.py` (`Site.test_one_stylesheet`: the
    scene's partials are included by `home.html` only, and only `/` has
    a scene)
  - Since: #710

CAT-72a to CAT-72e stay unused; the spot drawings are CAT-73a to
CAT-73g and CAT-73j. CAT-73i, which a draft of this change gave a 404 page, stays
unused.

- CAT-73: Every page except the start page MUST open with the head band,
  which holds its `h1` and, where the page has them, its lead and its
  breadcrumb.

  The band stands on `--sc-water`, so a page shows at a glance that it
  belongs to the harbour of the start page.

  - Test: `catalog/test_catalog.py` (`Site.test_head_band`: a walk over
    the built fixture site finds the band with the page's `h1` on every
    HTML page but `/`)
  - Since: #711

- CAT-73a: The head band MUST carry the spot drawing of its page's row in
  the table above, and the pages of the last row none.

  - Test: `catalog/test_catalog.py` (`Site.test_head_band`: the drawing
    of each layout against the table)
  - Since: #711

- CAT-73b: A spot drawing MUST hold no text and none of the scene's
  landmarks: the office, the gate, the crane, the ship Kapitan, the truck,
  the islands and the buoy.

  A label in a drawing 184 px high would be too small to read, and the
  page's title says what the page is. A landmark would retell the scene's
  story on a page that does not tell it, so the reference pages' tide
  gauge carries a float, not a buoy. Containers, bollards, lamps and
  trees stand on any quay and recur.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_drawings_carry_no_colour_or_style`: no `text` element
    in a spot drawing); manual: the drawings beside the scene in the
    merge request
  - Since: #712

- CAT-73c: A spot drawing MUST stand whole and vertically centred in its
  band, 184 px high.

  It reaches 1rem into the band's padding, which leaves .75rem to the
  band's edge, and what moves stays within that margin, so no frame of
  its motion is clipped.

  - Test: `catalog/test_catalog.py` (`Site.test_spot_drawing_rules`: the
    rule of the drawing's height and placement); manual: every motion's
    frames at 1440 px
  - Since: #711

- CAT-73d: Below 48rem a spot drawing MUST be left out.

  A phone then shows the title and the first paragraph without
  decoration above them.

  - Test: `catalog/test_catalog.py` (`Site.test_spot_drawing_rules`: the
    rule below 48rem)
  - Since: #711

- CAT-73e: A spot drawing MUST move once when its page loads and come
  to rest 1.5 to 2.5 seconds after it, with CSS animations of `transform`
  and `opacity` only, and stay still under `prefers-reduced-motion:
  reduce`.

  Each motion starts 0.35 to 0.45 seconds after the page loads. The end
  times are those of the preview build's stylesheet, the delay plus the
  duration of its last animation:

  | Name | Motion | At rest after |
  |---|---|---|
  | `catalog` | the top container is set down, then its seal pops on | 1.85 s |
  | `generator` | a scan runs over the container, then its seal pops on | 1.85 s |
  | `recipe` | the lashings pull tight and the top container settles | 1.85 s |
  | `barge` | the barge glides in, and its wake fades | 2.35 s |
  | `basin` | the model ship slides down the slipway, and a ripple spreads | 2.05 s |
  | `guide` | the beam turns once, the light comes on and its rays show | 2.45 s |
  | `mast` | four flags are hoisted one after the other | 2.05 s |
  | `pilot` | the pilot boat casts off, and its wake churns | 2.25 s |
  | `bollard` | the line drops over the bollard and pulls tight | 1.85 s |
  | `gauge` | the float bobs once, and a ripple spreads | 2.05 s |

  None loops.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_motion_changes_transform_and_opacity_only`: the spot
    drawings' animation rules name `transform` and `opacity` only, run
    once, end by 2.5 s and sit inside `prefers-reduced-motion:
    no-preference`)
  - Since: #711

- CAT-73f: A spot drawing MUST be inline SVG marked `aria-hidden="true"`.

  It carries nothing a reader needs, so assistive technology skips it.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_drawings_carry_no_colour_or_style`:
    `aria-hidden="true"` on every spot drawing)
  - Since: #712

- CAT-73g: A spot drawing MUST meet CAT-69a, CAT-69b and CAT-69h.

  It then takes its colours from the scene's tokens through classes and
  follows the theme, under the same CSP as the scene, with ids that do
  not collide with the page's.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_drawings_carry_no_colour_or_style`,
    `Harbour.test_scene_classes_have_rules`: the checks of CAT-69a,
    CAT-69b and CAT-69h on the spot drawings)
  - Since: #711

- CAT-73h: On `/playground/` the head band MUST stand above the editor.

  The playground keeps its own layout and the site's CSP (DEC-42); the
  band adds no script.

  - Test: `catalog/test_catalog.py` (`Site.test_head_band`: the band
    before the editor in `playground.html`)
  - Since: #711

- CAT-73j: A spot drawing other than `catalog` and `generator` MUST
  have at most one orange part, and none shaped like a seal or a check
  mark.

  A part is one object, such as a line, a flag or a float, in as many
  shapes as it takes to draw. Orange in a drawing then reads as
  kadet-hub's check only in the two drawings of sealed containers. The
  accents are the lashings of `recipe`, the hull stripe of `pilot`, one
  flag of `mast`, the line of `bollard` and the top of the float of
  `gauge`; `barge`, `basin` and `guide` have none.

  - Test: `catalog/test_catalog.py` (`Harbour.test_spot_drawings`: no
    seal and no check mark in a spot drawing but `catalog` and
    `generator`); manual: the orange parts of each spot drawing, in the
    merge request
  - Since: #712

- CAT-74: Each listed version on a generator page MUST show what a
  consumer does with it as three numbered steps, Inventory, Verify and
  Checks, each marked with who acts.

  The steps take the stations of the start page: "Inventory" with the
  inventory entry is the visitor's project, "Verify" with the commands
  of CAT-2 and "Checks" with the gate's results are kadet-hub's. The
  version's record and its output diff follow the steps.

  - Test: `catalog/test_catalog.py` (`Site.test_version_steps`: the
    three steps, their order and their chips in each listed version of a
    generator page)
  - Since: #711

- CAT-75: From 78rem the list "On this page" of a recipe page and of a
  guide MUST stand beside the main column and stay in view while the
  page scrolls.

  A generator page does the same under CAT-19. Below 78rem the list is a
  disclosure above the sections.

  - Test: `catalog/test_catalog.py` (`Site.test_rail`: the rail's rules
    from 78rem and the rail in `chart-recipe.html` and `prose.html`)
  - Since: #711

- CAT-76: A line of running text MUST hold at most 80 characters.

  WCAG 2.2 success criterion 1.4.8 (AAA) sets 80 characters as the
  limit. The rail of CAT-75 takes the width of a wide screen, so the
  lines of the main column need not grow.

  - Test: `catalog/browser.mjs` through `InChrome.test_rendered_pages`:
    the characters of the longest line of running text on each page type
  - Since: #711

- CAT-77: The head band of a recipe page and the start page's Recipes
  tile MUST explain the word "recipe" in one maritime line.

  Recipes keep their name. The band says "A recipe is packed cargo for
  one app: inventory classes, ready to load", and the tile "Packed cargo
  for one app".

  - Test: `catalog/test_catalog.py` (`Site.test_head_band`: the line in
    the band of every recipe page and in the tile of `/`)
  - Since: #711

- CAT-79: The card lists of `/guides/`, `/blog/`, `/stacks/` and
  `/recipes/` MUST span the main column, in two columns from 64rem and in
  one column below.

  The head band above a list spans the column. A single column at
  reading width would leave a third of a wide screen empty beside it,
  while two columns show twice the cards per screen and keep the lines
  of a card short (CAT-76). The catalog's cards (CAT-22) fill the column
  too.

  - Test: `catalog/test_catalog.py`
    (`Site.test_card_lists_span_the_column`: the lists' rule of two
    columns from 64rem and one below, with no width limit on the lists);
    `catalog/browser.mjs` through `InChrome.test_rendered_pages`: two
    cards side by side in each of these lists at 1440 px, one at 375 px
  - Since: #711

- AC-50 (CAT-9h, CAT-54, CAT-59, CAT-71, CAT-71a, CAT-72, CAT-73,
  CAT-76, CAT-79): the implementation pull request adds a script that
  renders one page of every type above with the repository's headless
  Chrome, through playwright-core as `catalog/playground/browser.mjs`
  does, in the light and the dark theme. On each rendered page it finds
  no text below 4.5:1 against its background, and it runs the rendered
  checks that CAT-9h, CAT-76 and CAT-79 name. The pull request attaches 20 screenshots for review: the start page,
  `/generators/`, one generator page, one guide and one recipe page, each
  at 375 and 1440 px in both themes. Check: the script, run in the pull
  request; manual: the review of the screenshots.

## Start page and catalog

Until this change `/` held the hero, the catalog (search, tag filter,
sort, result line and card grid) and the steps of how a version gets
listed. Each element added above the catalog pushed its search further
down. On 2026-11-21 the operator decided to split the page: `/` becomes
a start page that shows what a generator does and where to go next, and
the catalog moves to `/generators/` with its behaviour unchanged. #706
built the split in the Chart Room look; the implementation pull request
ports it ("Visual identity"). Today's start page has 73,239 bytes, and
GitHub Pages serves it gzipped in 12,807 (measured 2026-11-21); the
implementation's merge request states the new weight with the fonts.

Related: CAT-5, CAT-6, CAT-8, CAT-11, CAT-12, CAT-26, CAT-31, CAT-38b,
CAT-62, CAT-63, CAT-65.

- CAT-67: `/` MUST be a start page with, in this order:

  1. the hero: its `h1`, a lead, the search of CAT-67b and the notice of
     CAT-65;
  2. the harbour figure (CAT-66);
  3. the live edit (CAT-68);
  4. the section "Where to go next": Generators, Recipes, Stacks,
     Playground, Quickstart and Guides, each with one line on what it
     holds and, where the index or the content gives one, its count,
     followed by "Request a generator" and "Wanted generators";
  5. the section "How a version gets listed" (CAT-62).

  The counts come from the build. Generators counts the generators with
  a listed version (CAT-26), Recipes the recipes of the index with a
  listed version (CAT-38b), Stacks the published stack posts of
  `/stacks/` (CAT-46) and Guides the pages of `/guides/`. Playground and
  Quickstart have no count. A count of 0 is left out, because
  `/recipes/` also lists recipes the index does not list yet (CAT-37,
  CAT-38), and "0 listed" would read as an empty page.

  The destinations are tiles under the `h2` "Where to go next", and
  their names are no headings (CAT-11b). Generators, the widest, stands
  on `--sc-hull-r` in both themes with a drawing of three cargo cubes;
  Recipes on `--teal` with a drawing of three stacked containers and the
  line of CAT-77; Guides on `--accent-bg`; the others on `--surface`.

  The hero has no buttons, as in the mockup. On `/` the navigation's
  "Use" and "Publish" link `docs/consumers.md` and `docs/authors.md`
  (CAT-6), and the request form of CAT-12 and `/wanted/` of CAT-31
  follow the tiles. The mockup's `h1`, "The Helm alternative where every
  generator clears customs.", names Helm (CAT-11f) but neither Kapitan
  nor Kubernetes or Terraform, which CAT-11a asks of it; the hero keeps
  an `h1` that meets both.

  - Test: `catalog/test_catalog.py` (`Site.test_start_page`: the five
    parts in this order in the HTML of `/`, the heading, the six
    destinations and their counts against `/generators/`, `/stacks/` and
    `/guides/`, no count of 0, the two request links after the tiles)
  - Since: #710

- CAT-67a: The catalog of CAT-8, CAT-10, CAT-22, CAT-26, CAT-29a and
  CAT-29e MUST be at `/generators/`, with its own title and description
  (CAT-11).

  `layouts/generators.html` takes the catalog's markup from the home
  page, with the ids and data attributes `site.js` reads, and
  `content/generators.md` gives it its title and description. The
  generator pages stay at `/generators/<name>/` (CAT-5). Links that mean
  the catalog point there: the "Catalog" line of `/llms.txt` and the
  three guides that link it as `/`, `apiserver-dry-run`, `config-tools`
  and `same-app` (checked on main on 2026-11-21). In #706 the
  `/generators/*` cascade of `hugo.toml` did not reach the page itself,
  so it has no Markdown variant and no badge.

  - Test: `catalog/test_catalog.py` (`Site.test_catalog_page`, and the
    checks of CAT-8 to CAT-29e, which read `/generators/`; the "Catalog"
    line of `/llms.txt`)
  - Since: #710

- CAT-67b: The start page's search MUST submit its query with GET to
  `/generators/` as the parameter `q`.

  Without JavaScript the form still lands on `/generators/?q=…`, which
  then shows every card. The field searches generators only (CAT-29a,
  CAT-29e), so its label and placeholder promise nothing else; the
  mockup's placeholder, "Search 39 generators and 58 recipes", promises
  recipes, which `/recipes/` searches (CAT-37i). The mockup draws the
  search button in indigo; as the primary button it takes `--signal`
  ("Visual identity").

  - Test: `catalog/test_catalog.py` (`Site.test_start_page_search`: the
    form's `action`, `method` and field name); manual: "HTTPRoute"
    submitted on `/` with and without JavaScript
  - Since: #710

- CAT-67f: `/generators/` MUST put the `q` parameter into its search
  field and filter by it.

  `site.js` already reads `q` into the catalog's field and writes the
  query into the URL while a visitor types (CAT-8). The field moves with
  the catalog; the parameter stays.

  - Test: `catalog/test_catalog.py` (`Site.test_start_page_search`: the
    line of `site.js` that reads `q`); manual: as for CAT-67b
  - Since: #710

- CAT-67g: The CSP MUST allow the start page's form with
  `form-action 'self'`.

  Under the current `form-action 'none'`, Chrome blocked the submit with
  a CSP violation and the page stayed on `/` (#706, fixture build,
  2026-11-21). `'self'` admits forms that send to the site's own origin.
  The site's other forms, the version selector of CAT-34 and the
  Mastodon share of CAT-36d, cancel their submit in `site.js`.

  - Test: `catalog/test_catalog.py` (`Site.test_csp`: the CSP of every
    page; `test_badge` and `test_goatcounter_counts_from_the_own_origin`
    compare the whole CSP)
  - Since: #710

- CAT-67c: The site navigation MUST link `/generators/` as "Generators",
  right after Quickstart.

  The brand links `/`, which no longer lists generators, so the catalog
  needs an entry of its own. CAT-40a keeps Quickstart first and CAT-47
  Stacks after Recipes. The mockup's navigation has the same order but
  six of the links; the site keeps all of them and the disclosure of
  CAT-63.

  - Test: `catalog/test_catalog.py` (`Site.test_reference_disclosure`,
    `Site.test_quickstart_linked`: the link and its place in the header
    of every page)
  - Since: #710

- CAT-67d: Below 48rem each station's text MUST have above it a window
  of about 300 px into the vertical drawing that shows that station.

  #706 first left the figure out on phones to keep the search on the
  first screen; with the search in the hero (CAT-67e) the figure can
  follow it. Scaled into the 343 px column of a 375 px screen, the wide
  drawing would render its smallest labels at 3.2 px (CAT-69d). The
  vertical drawing, `docs/specs/harbour/scene-narrow.svg`, is 380 units
  wide and 1,422 high, with the office, the gate, the crane with the ship
  and the two islands one below the other. A window is 316 units high,
  300 px in the 361 px column of a 393 px screen and 285 px at 375 px.
  With the tabs, the window stands under them and the drawing moves
  behind it to the selected station; without JavaScript or with reduced
  motion, each station of the list carries its own window, drawn again
  through `<use>`. Neither the figure nor the page scrolls sideways.

  - Test: `catalog/test_catalog.py` (`Site.test_phone_windows`: the five
    windows in the static list and the rules below 48rem); manual: 393
    by 852 px, each station's window above its text, with and without
    JavaScript
  - Since: #710

- CAT-67i: A station's window MUST show that station's main object
  whole: the office, the gate, the crane, the ship and the two islands.

  In the preview build some objects reach past their window's edge; the
  implementation sets the windows so they do not.

  - Test: manual: the five windows at 393 and 375 px
  - Since: #710

- CAT-67j: Below 48rem a button "Show whole harbour" MUST open the whole
  vertical drawing, and close it again.

  Open, the button reads "Show one station" and stays in view at the
  drawing's foot.

  - Test: `catalog/test_catalog.py` (`Site.test_phone_windows`: the
    button in the markup, hidden until `site.js` shows it, and its
    `aria-expanded`); manual: 393 px, open and close
  - Since: #710

- CAT-67h: At each width at most one drawing of the scene MUST be in the
  accessibility tree.

  The stylesheet switches the drawings at 48rem: `@media (width < 48rem)`
  gives the wide drawing `display: none`, and `@media (width >= 48rem)`
  the vertical one. With `max-width: 48rem` and `min-width: 48rem` both
  rules would match at exactly 768 px and hide both; the range syntax
  leaves no width with both or neither. An element under
  `display: none` is out of the accessibility tree and the tab order. In
  the static list below 48rem the windows are copies marked
  `aria-hidden="true"` and the drawing itself is hidden, so no scene
  image is read there; the station texts carry what the drawing shows
  (CAT-69d). `site.js` marks the selected station in both drawings, so a
  resize keeps the selection.

  - Test: `catalog/test_catalog.py` (`Site.test_phone_windows`: the two
    `display: none` rules in the two range queries, both drawings
    `role="img"` with the same name, the windows `aria-hidden`); manual:
    Chrome's accessibility tree at 393 and 1440 px
  - Since: #710

- CAT-67e: The start page's search MUST stand in the hero at every
  width.

  Visitors spend 57 % of their viewing time above the fold and 74 % in
  the first two screens (NN/g, eye tracking with 120 participants and
  more than 130,000 fixations, 2018). In #706 the search followed the
  hero on phones and the figure from 48rem, so the page rendered the
  form twice, once per width, to keep the focus order with the screen.
  In the hero it has one place at every width, so one form remains, and
  the second one with its id `q-narrow` is dropped.

  - Test: `catalog/test_catalog.py` (`Site.test_start_page`,
    `Site.test_start_page_search`: one search form, inside the hero);
    manual: 393 by 852 px, the search field on the first screen
  - Since: #710

## The harbour figure

The hero says what a listed version passed, not what a generator does
for the visitor: turn a block of inventory into finished files. The
start page shows that with a real run, drawn as a harbour in isometric
view. #706 first drew three panes, inventory, generator and files, which
suggested a direct path from one to the next; its review on 2026-11-21
replaced them with the five steps of a real run. CAT-66b, which #706
published for marking the target's values in the outputs, is not
carried over: the live edit (CAT-68) shows where they land. The ID
stays unused.

The run is kadet-hub's consumer flow on the `helm-vs-terraform` example
of kadet-hub/examples, recorded on 2026-11-21 in
`catalog/site/assets/harbour/run/`; its README names the example's
commit, the index serial and the tools with their versions. The flow is
the one of the example's own `check` script and of the consumer workflow
(CON-1, CON-2): the index is verified, each pin is looked up in the
index and its attestation verified, `oras pull` fetches it by digest,
`tar` unpacks it into `lib/<name>`, and `kapitan compile` runs without
`--fetch`. Kapitan 0.36.3 verifies nothing itself, neither an
attestation nor a digest ([consumers.md](consumers.md)), so the fetch is
oras's, by digest, after the check, and Kapitan only compiles. An earlier
recording ran `gh attestation verify` and then `kapitan compile --fetch`.
Nothing bound the verified digests to the bytes Kapitan fetched, which
is the path `docs/consumers.md` warns against, so it was replaced.

The example's target `prod` takes the classes `generators` and
`uploads` and sets `bucket` and `region`. Each station has a name, a
place in the harbour and a chip that names who acts:

1. Inventory, at the harbour office, "Your project". The target, its
   classes and the two pins of `inventory/classes/generators.yml`, which
   the next stations check and fetch. The station lists both pins with
   their versions and whole digests under the line of CAT-66g, and shows
   `prod.yml` and the dependency entries of `generators.yml`.
2. Verify, at the customs gate, "kadet-hub". `gh release download`
   fetches the index of the latest release, `gh attestation verify`
   checks it, `jq` reads its serial and each pin's record, its digest
   and `yanked`, and `gh attestation verify` checks each pinned digest
   (CAT-66h).
3. Fetch, at the crane, "kadet-hub". `oras pull` fetches each artifact
   by its digest, and `tar -xf` unpacks it into `lib/kubernetes` and
   `lib/terraform-aws`. Kapitan takes no part.
4. Generators, on the ship Kapitan, "Kapitan". `kapitan compile` renders
   the inventory, then for each `kapitan.compile` entry with
   `input_type: kadet` imports the generator from `lib/` and calls its
   `main()`; kubernetes writes YAML to `manifests/`, terraform-aws JSON
   to `terraform/`. The station shows the compile's output and the two
   kadet entries of `generators.yml`.
5. Output, at the two islands, "Kapitan". The files under
   `compiled/prod/`: three manifests in `compiled/prod/manifests/shop/`,
   two Terraform JSON files and the provider lock file in
   `compiled/prod/terraform/`. The station shows the lines of
   `web-cm.yml`, `bucket-uploads.tf.json` and `providers.tf.json` that
   carry `bucket` and `region`, and links the live edit.

The session takes one pin after the other, so station 2 shows the
checks of both pins and station 3 both fetches. The figure leaves out
what the flow does not do: no kgenlib, no download cache and no schema
validation by Kapitan.

The drawing tells the same run as one story. The same two containers,
kubernetes in a strong indigo and terraform-aws in teal, travel through
all five stations, and each station's motion starts where the last one
ended. At the office a cargo list unfolds on the wall, its lines
kubernetes and terraform-aws are ticked, and a truck with both
containers, still unsealed, rolls in and stops before the gate. At the
gate a scan runs over each container, a seal pops onto each, the signal
turns from orange to teal, the barrier lifts and the truck drives
through to the crane. The crane's spreader lifts each container off the
truck and lowers it onto the ship, and the truck leaves empty. On the
ship each container lights up in turn, parcels rise and stack on deck,
the funnel smokes and the hull bobs. Then the parcels leave the stacks
and sail the routes to the two islands. The motion of each station
takes its own time: 2.2 seconds for the inventory, 2.4 for the gate,
3.45 for the crane, the longest, and about 2 for each of the last two,
whose last puff of smoke and last parcel end at 2.0 and 1.78 seconds.

Segments are the reason for the stations. Mayer's segmenting principle
(after Mayer & Chandler 2001) holds that learners understand an
animation better when they advance it in segments, and animation helped
most where complex features of the change mattered (Ploetzner et al.
2021, g = 0.65). These are learning studies with transfer tests, which
apply to a landing page by analogy; the part a visitor advances is the
free choice of stations after the play-through.

The scene has two drawings of the same harbour: the wide one from 48rem,
and below it a vertical one for the phone's windows (CAT-67d, CAT-67h).
CAT-69 to CAT-69j apply to both.

The wide drawing, `docs/specs/harbour/scene-wide.svg`, is an isometric
view on water, 1,168 by 700 units. Along the left runs the quay with its
lane, a yard of empty slots with trees behind it, and bollards and lamps
at its edge. On the quay stand the harbour office with the cargo list of
the target on its wall, under the plate "inventory/" and the head
"prod"; the orange customs gate over the lane, with the plate
"kadet-hub" on its beam, a shield with a check above it, a barrier and a
signal of two lamps; and a portal crane over the lane and the quay's
edge, its trolley and spreader on a boom that reaches over the ship. The
ship lies at the quay with its bow to the right, "Kapitan" on the hull,
a plate "lib/", a superstructure with a funnel at the stern, and on deck
the two containers, each with its plate and an orange seal, beside the
stacks of parcels they wrote. Dotted routes lead from the bow to two
islands on the right, each with a store in its cargo's colour: the
island of Kubernetes manifests and the island of Terraform JSON. Each
island has a flat label beside it in the manner of the pills, with its
name and its path, `compiled/prod/manifests/` and
`compiled/prod/terraform/`. A buoy floats in the water in front of the
ship. Five pills name the stations at their
objects: 1 Inventory at the office, 2 Verify at the gate, 3 Fetch at the
crane, 4 Generators at the ship and 5 Output on a route. The pills, the
plates, the cargo list, the hull and the islands' labels hold every
label of the drawing, and a container's plate carries its name only.

The vertical drawing, `docs/specs/harbour/scene-narrow.svg`, shows the
same harbour in pieces one below the other: the office, the gate, the
crane with the ship, where the two containers stand on one hatch, and
the two islands, which one route calls at in turn.

Both reference drawings show the finished run with no station selected:
the barrier up, the signal teal, the containers sealed on deck and the
parcels at the islands. The cargo takes the scene's indigo and teal, and
the islands are named by what they hold. CAT-58b found that the Linux
Foundation, which holds the Kubernetes marks, allows fair use of word
marks only, and that HashiCorp and AWS restrict their logos to approved
or plain-text use; blue cubes beside "Kubernetes" and purple blocks
beside "Terraform" would come close to those logos' design elements.

A reference drawing holds the literal light values of the token tables.
Where tokens share a value, the Use column decides. A shadow in
`--sc-shade` carries `style="mix-blend-mode:multiply"`, the one style a
reference file holds, since the site multiplies it over what lies below.
The
implementation draws the same shapes with classes bound to the tokens
(CAT-69a).

Related: CAT-3, CAT-9, CAT-9c, CAT-9g, CAT-9h, CAT-35a, CAT-54, CAT-55,
CAT-64, CAT-67d, CAT-67h, CON-1, CON-2.

- CAT-66: The start page MUST show the harbour figure: the five stations
  above in their order, each with its text and with the commands, output
  and file lines of the recording in `catalog/site/assets/harbour/run/`.

  A script in the repository, `catalog/harbour_figure.py`, writes the
  figure's partial `_partials/harbour.html` and the live edit's
  `_partials/live-edit.html` from the recording, by line ranges it keeps
  in one table, so every line on the page is a line of the recording.
  Between two ranges of a file the panel marks the gap, "⋯ 5 lines",
  with the number of lines left out. A file's name is the panel's title.
  Three things change how a line is shown, and the note of CAT-66o names
  them: temporary paths read `<tmp>`, a digest is shortened (CAT-64),
  and a long command is folded (CAT-66n). A terminal more than 21rem
  high scrolls inside its panel: it takes the keyboard, fades out at its
  foot, and a button there names the lines left, such as "12 more lines
  ↓".

  The station texts use the glossary's terms (CAT-13a). A station's
  chip shows "Your project" in `--text` on `--bg-subtle`, "kadet-hub" in
  `--signal-text` on `--signal-bg` and "Kapitan" in `--accent` on
  `--accent-bg`. A station's commands and files stand in dark panels
  under its text, at the station's whole width. The figure's `h2`, "One
  compile in five stations", is visually hidden.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_figure_is_written_from_the_recording`:
    `harbour_figure.py` run on the recording writes the committed
    partials; each line of a panel, unfolded and with its digests whole,
    is a line of its file in the recording, in that file's order; each
    gap's count equals the lines it leaves out; the five stations stand
    in order with their names, places and chips)
  - Since: #710

- CAT-66n: A command longer than 100 characters in a panel of CAT-9h,
  each digest counted at its shortened 24, MUST be folded at its flags:
  the command with its arguments up to the first flag or URL, then one
  line per flag with its value and one per further argument, each line
  but the last ending in a backslash.

  The 100 characters only decide which commands fold. A flag keeps its
  value on its line, however long, since a value on a line of its own
  reads as an argument; how wide a line may be is bounded once, by the
  rendered check of CAT-9h. The figure's continued lines hang four
  characters in, and the Verify panel of a generator page keeps the two
  of its command on main (CAT-2). The longest folded line of the
  recording is `--cert-identity` with the release workflow's identity,
  103 characters with its hang; the longest of the Verify panel is the
  same flag, 101 characters. A folded command still runs as typed.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_long_commands_are_folded_at_their_flags`,
    `Site.test_verify_command_is_folded_at_its_flags`: every command of
    those panels longer than 100 characters so counted is folded, each
    flag on one line with its value, and its lines joined give the
    command of the recording or of CAT-2)
  - Since: #711

- CAT-66o: The figure's note MUST name every change the panels make to
  the recorded lines.

  The note names the example and the date and Kapitan version of the
  run, and says that temporary paths read `<tmp>`, that "⋯" marks lines
  left out, that a digest shows its first and last eight characters,
  that a long command is folded at its flags, that each whole digest
  stands in station 1, and that on a narrow screen a long line continues
  indented on the next one.

  - Test: `catalog/test_catalog.py` (`Site.test_figure_texts`: the
    note's sentences in the HTML of `/`)
  - Since: #710

- CAT-66g: The station texts MUST carry the line "Recorded on <date>,
  not necessarily the latest version", with the recording's date.

  Versions rot. The example moved its kubernetes pin seven times in the
  17 days from 2026-10-22 to 2026-11-08, and index serial 147 already
  lists terraform-aws 0.1.5 next to the recorded 0.1.4. Versions and
  digests therefore appear only in the station texts, rendered from the
  recording, and never in the drawings (CAT-69c).

  - Test: `catalog/test_catalog.py` (`Site.test_figure_texts`: the line
    with the recording's date in the HTML of `/`)
  - Since: #710

- CAT-66f: The catalog build MUST fail when the index lists a version the
  recording pins as yanked or with advisories, or does not list it.

  A recording stays valid while its versions are only old (CAT-66g). It
  is recorded again when one of its pins becomes unsafe to show, and the
  figure follows it in the same merge request. The release's catalog job
  compares the two pins of `run/inventory/classes/generators.yml` with
  the index it builds from, so a yank or a non-empty `advisories` stops
  the deploy and the previous site stays live, as for the findings of
  CAT-11d. A pin the index no longer names, after a rename or a removal,
  stops it too. The release sets `CATALOG_RECORDED_PINS=required` for
  that part, because the fixture indexes of tests and previews do not
  carry the recorded pins. A version bump alone needs no new recording.

  - Test: `catalog/test_catalog.py`
    (`Site.test_unsafe_recorded_pin_stops_the_build`: a fixture index
    that yanks a recorded pin, and one that lists an advisory for it,
    fail the build; `Site.test_missing_recorded_pin_stops_the_build`: with
    `CATALOG_RECORDED_PINS=required`, an index without the pins fails
    the build)
  - Since: #710

- CAT-66h: Station 2 MUST state what the check proves and what it does
  not, and link "What a listing covers" in `docs/consumers.md`.

  The check proves that the release workflow of kadet-hub/registry built
  the artifact with this digest. It does not prove that a generator is
  harmless in the visitor's project, so the visitor reviews the compiled
  output before applying it. No sentence of the figure says or implies
  that Kapitan verifies anything or that the visitor's compile is
  checked.

  - Test: `catalog/test_catalog.py` (`Site.test_figure_texts`: both
    sentences and the link to `docs/consumers.md#what-a-listing-covers`
    in station 2)
  - Since: #710

- CAT-66a: With JavaScript and motion allowed, the figure MUST play its
  stations once, from the moment 90 % of the drawing is in view, each
  station for as long as its motion takes, and stop on station 5.

  The operator decided on 2026-11-21 for a start on view instead of on
  load, so a visitor who scrolls down still sees the play-through. A
  drawing taller than 90 % of the viewport starts once it fills that
  much of it. `site.js` watches the drawing with an
  `IntersectionObserver`. A station stays for 2.5, 2.8, 3.9, 2.4 and 2.4
  seconds, its motion and a short rest, from each station's `data-ms`.
  Until the run starts the scene rests on the end of station 1. All
  stations share one grid cell, so the panel keeps the height of the
  tallest and nothing below the figure moves while they change. Styles
  live in `style.css` and the timing in `site.js`, since the CSP admits
  no inline style or script (CAT-3).

  - Test: `catalog/test_catalog.py`
    (`Site.test_figure_plays_once_with_tabs`, partial: the observer's
    threshold in `site.js`, the five `data-ms` and the rules of the
    playing figure); manual: the figure plays when scrolled into view at
    1440 and 393 px
  - Since: #710

- CAT-66c: While the stations play, a visible Pause control MUST stop
  them.

  The play-through takes 14.0 seconds and changes the station four
  times in its first 11.6, next to other content, so WCAG 2.2 success
  criterion 2.2.2 (Level A) asks for a way to pause it; a start on
  scrolling into view counts as automatic too. The control stands on the
  drawing's frame and reads "Play" while stopped.

  - Test: `catalog/test_catalog.py`
    (`Site.test_figure_plays_once_with_tabs`: the control in the markup,
    hidden until `site.js` shows it); manual: Pause during the
    play-through
  - Since: #710

- CAT-66i: The play-through MUST stop when focus enters the station tabs
  or the pointer moves over a station or a tab.

  The operator decided this on 2026-11-21: a visitor who reaches for a
  station wants to read it, not to see it change. A pointer that rests
  where the figure scrolls in does not count; one that moves does.

  - Test: `catalog/test_catalog.py`
    (`Site.test_figure_plays_once_with_tabs`, partial: the `focusin` and
    `pointermove` listeners in `site.js`); manual: Tab into the stations
    and move the pointer over them during the play-through
  - Since: #710

- CAT-66d: Selecting a station MUST highlight it in the scene and show
  its text, commands and lines.

  `site.js` turns the five station buttons into the WAI-ARIA tabs
  pattern with automatic activation over the stations of CAT-66e: the
  arrow keys, Home and End move the focus, and the focused tab is the
  selected one. A tab shows the station's number, name and place; below
  48rem it shows number and name, and the place is read to assistive
  technology only. A click on a station in the drawing selects it too;
  where stations lie inside each other, as the cargo on the ship, the
  innermost one under the pointer decides. The drawing's shapes take no
  focus, since the tabs are the keyboard route, and its small pills fall
  under the exception of WCAG 2.5.8 for a function that another control
  of the page offers at 24 px or more (CAT-55).

  - Test: `catalog/test_catalog.py`
    (`Site.test_figure_plays_once_with_tabs`: the tab roles `site.js`
    sets, partial); manual: the tabs with mouse and keyboard, a click on
    each station of the drawing
  - Since: #710

- CAT-66r: Selecting a station MUST run its motion once.

  A second selection of the same station runs it again; nothing loops.

  - Test: manual: each station selected twice at 1440 px
  - Since: #710

- CAT-66p: Each station's motion MUST start where the previous
  station's motion ended.

  The truck that stops before the gate at the end of station 1 is the
  truck that drives to the gate in station 2, and so on to the parcels.

  - Test: manual: the last frame of each station against the first frame
    of the next at 1440 px, in the merge request
  - Since: #710

- CAT-66q: Selecting a station MUST show the end states of the stations
  before it and nothing of what the stations after it bring.

  Selecting station 2 after station 5 takes the parcels and the
  containers on deck away again; selecting station 5 first shows the
  ticked list, the sealed containers and the stacks of the stations
  before it.

  - Test: `catalog/test_catalog.py`
    (`Site.test_figure_plays_once_with_tabs`: the rules for `.done` and
    for the stations not yet reached); manual: the stations selected in
    the order 5, 2, 4 at 1440 px
  - Since: #710

- CAT-66l: The selected station MUST be marked by more than colour.

  The selected tab takes a bar at its foot, an `--accent` border and a
  filled number; the selected pill in the drawing fills with `--accent`,
  grows a ring and a larger dot at the end of its stem. Forced colours,
  such as Windows' contrast themes, replace the tokens and drop
  shadows, so the mark that remains is drawn as a border or a stroke,
  not as a shadow (WCAG 2.2 success criterion 1.4.1).

  - Test: `catalog/test_catalog.py`
    (`Site.test_selected_station_marked_by_more_than_colour`: the rules
    of the selected tab and pill set a border, a ring or a stroke width
    besides colour); manual: Chrome's `forced-colors: active` emulation
  - Since: #710

- CAT-66k: While the stations play, the figure MUST announce nothing
  through a live region.

  A screen reader would read a new station every few seconds over
  whatever the visitor reads. The selected tab's state (`aria-selected`)
  carries the change for a visitor who goes there.

  - Test: `catalog/test_catalog.py`
    (`Site.test_figure_plays_once_with_tabs`: no `aria-live` and no role
    `status`, `alert` or `log` in the figure's markup or in what
    `site.js` adds)
  - Since: #710

- CAT-66e: Without JavaScript and under `prefers-reduced-motion:
  reduce`, the figure MUST list all five stations in order as static
  text with their commands, next to the drawing of the finished run.

  The markup holds this list, and `site.js` builds the tabs of CAT-66d
  over it only when motion is allowed. Every part of the drawing stands
  where the run leaves it, so the drawing without motion shows the
  finished run. Below 48rem each station of the list carries its window
  (CAT-67d).

  - Test: `catalog/test_catalog.py`
    (`Site.test_figure_plays_once_with_tabs`: the five stations as an
    ordered list in the HTML of `/`, the rules under
    `prefers-reduced-motion: reduce`); manual: reduced motion and no
    JavaScript at 1440 and 393 px
  - Since: #710

- CAT-66j: Until `site.js` has built the tabs, the figure MUST show the
  static list of CAT-66e.

  The playing layout hangs on a class that `site.js` sets after it built
  the tabs, never on one that `theme.js` sets in the head. A missing or
  failing `site.js` then leaves the five stations readable instead of a
  figure laid out for a play-through that never starts.

  - Test: `catalog/test_catalog.py`
    (`Site.test_figure_plays_once_with_tabs`: the playing layout's rules
    name a class that only `site.js` sets, and `theme.js` sets none for
    the figure); manual: the start page with `site.js` blocked
  - Since: #710

- CAT-66m: In print the figure MUST show all five stations, with the
  dark panels in light colours.

  A print rule shows the static list of CAT-66e and sets the dark panels
  back to the light tokens, so a printer puts the commands on paper
  without a dark ground.

  - Test: `catalog/test_catalog.py` (`Site.test_figure_in_print`: the
    `@media print` rules); manual: Chrome's print preview of `/`
  - Since: #710

- CAT-69: The scene MUST be SVG that `catalog/harbour_scene.py` draws from
  its own geometry, inlined from the partials it writes.

  CAT-58b records that the owner ruled out generated imagery. The script
  projects boxes, slabs and lines of a small isometric world and writes
  `_partials/harbour-wide.html`, `harbour-narrow.html`,
  `harbour-crop.html` with the phone's windows, `spot.html` with the
  inner pages' drawings (CAT-73), and the keyframes that depend on the
  geometry between two markers of `style.css`. Inline, the SVG sees
  `style.css` and `data-theme`, which an SVG loaded through `<img>` does
  not (CAT-35a), so it follows the theme, can highlight a station and
  keeps its labels as text.

  | Illustration considered | Why not |
  |---|---|
  | A raster image from Qwen-Image-2.1-Turbo, the image model available to the operator | Its licence, the Qwen Research License Agreement released on 2026-09-20, grants use "FOR NON-COMMERCIAL PURPOSES ONLY" (section 2(a)) and defines non-commercial as "for research or evaluation purposes only" (section 1(i)), which the illustration of a published site is not (`LICENSE` of Qwen/Qwen-Image-2.1-Turbo on Hugging Face at revision `fc13ba1`, read 2026-11-21). A raster would also keep one theme and draw its labels as pixels |

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_scene_is_drawn_by_its_generator`: `harbour_scene.py`
    run in a copy of the site writes the committed partials and the
    committed block of `style.css`; `Site.test_figure_texts`: the scene
    is inline `svg` in the HTML of `/`)
  - Since: #710

- CAT-69a: Every colour of the scene MUST come from a class of
  `style.css` bound to a token of "Visual identity".

  The partials carry no colour literal, and the scene follows the theme
  and the toggle. Every class of the scene carries the prefix `h-`, and
  its rules name no ancestor: the phone's windows show the vertical
  drawing again through `<use>`, and inside the tree of a `<use>` no
  selector that reaches outside it matches. A shape drawn once and used
  in several colours takes its faces from custom properties that a
  family class sets to scene tokens. Presentation attributes for
  geometry stay.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_drawings_carry_no_colour_or_style`: no `fill`,
    `stroke` or `stop-color` attribute with a colour in the partials;
    `Harbour.test_scene_classes_have_rules`: a rule in `style.css` for
    every class they use, but the motion hooks of the parts that do not
    move)
  - Since: #710

- CAT-69b: The scene MUST contain no `<style>` element, `style`
  attribute, `<script>` element, event handler attribute or `href` to
  another document.

  The CSP (`style-src 'self'`, `script-src 'self'`) blocks the first
  four, as for the diagrams of CAT-35a; `site.js` adds the listeners.
  `<use href="#…">` points into the page and stays.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_drawings_carry_no_colour_or_style`: these constraints
    on the partials, as `test_diagram_svgs` checks the diagrams)
  - Since: #712

- CAT-69h: Every `id` inside the drawings MUST be unique on the page.

  Both drawings are inline in one page (CAT-67h), and a reference to an
  id resolves to the first element that has it. The wide drawing names
  its two containers `hw-ck` and `hw-ct`, the vertical one itself `hn`
  and its containers `hn-ck` and `hn-ct`.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_drawings_carry_no_colour_or_style`: the ids of the
    drawings; `Site.test_ids_are_unique`: no duplicate `id` in the HTML
    of `/`, `/generators/` and a generator page)
  - Since: #710

- CAT-69c: The ship MUST carry exactly the two generators the recording
  pins, each as a container labelled with its name only.

  The mockup added `certmanager` and `argocd 1.2.0`, which this run never
  fetched, and labelled the containers with versions and a shortened
  digest. Versions and digests stand only in the station texts
  (CAT-66g). The kubernetes container takes `--sc-kub`, a stronger indigo
  than the office's, and the terraform-aws container `--sc-teal`; each
  carries an orange seal from the gate on. Both are drawn once and shown
  wherever they pass.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_ship_carries_the_two_pinned_generators`: each name
    stands on its container and on the cargo list, no other generator
    name and no digit on a plate)
  - Since: #712

- CAT-69i: An object of the drawings MUST NOT overlap another against
  the isometric depth order, in any frame of any motion.

  What lies farther back is painted first: the containers hoisted off
  the truck stand behind every part of the crane, the carried ones in
  front of its far side, and what stands nearer on deck is painted later.

  - Test: manual: the frames of each station at 1440 and 393 px, in the
    merge request
  - Since: #710

- CAT-69j: The drawings MUST keep one scale: the containers have the
  same size on the truck, on the crane and on deck, the office is
  clearly larger than a container, and a loaded truck passes the gate
  with room to spare.

  A container is 132 by 50 by 46 units and drawn once (CAT-69c); the
  office stands 176 by 96 units and 92 high. The gate's posts leave at
  least 20 units beside the containers, and its beam stands 80 units over the
  lane, 22 above a loaded truck of 58. `harbour_scene.py` asserts the
  gate's clearance.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_scene_is_drawn_by_its_generator`: `harbour_scene.py`
    runs without an assertion error); manual: the frames of station 2
  - Since: #712

- CAT-69d: Every fact a label of the drawings shows MUST also stand in
  the text of its station.

  The labels are small. From 48rem the wide drawing spans the column,
  720 px at 48rem without a scrollbar and at most 1168 px, 76rem less two
  gutters of 24 px each time, so its smallest labels, the islands' paths
  at 11 units, render at 6.8 to 11 px. The vertical drawing, 380 units
  wide in a 361 px column at 393 px, renders its smallest labels at
  11.5 units at 10.9 px. Each drawing is therefore one image whose
  accessible name lists the stations, and the station texts carry what
  its labels show.

  - Test: manual: every label of both drawings against the station
    texts, in the merge request
  - Since: #710

- CAT-69e: Every label of the drawings MUST reach 4.5:1 against what it
  sits on, in both themes, with its station selected or not.

  The scene pairs of "Visual identity" cover the labels: text stands on
  plates, on the hull and on pills, never on the water. Selection changes
  only the selected pill (CAT-66l). The mockup dimmed the other stations
  with `filter: saturate(.3)` on the whole station, labels and their
  grounds included; that result depends on the browser's filter pipeline
  and cannot be computed from the tokens, so the other stations keep
  their colours.

  - Test: `catalog/test_catalog.py` (`Site.test_text_reaches_aa`: the
    scene pairs, and no `filter` and no opacity below 1 in the resting
    rules)
  - Since: #710

- CAT-69f: Every animation of the figure MUST change only `transform`
  and `opacity`.

  These two properties move nothing else on the page. A colour change on
  selection has no transition. Opacity changes only during an animation;
  at rest every text has opacity 1 (CAT-54). A moving group cannot
  multiply over what lies below it, so its shadow is a solid
  `--sc-shade-*` colour.

  - Test: `catalog/test_catalog.py`
    (`Harbour.test_motion_changes_transform_and_opacity_only`: every
    `transition` and `@keyframes` in the figure's rules names
    `transform` and `opacity` only)
  - Since: #710

- CAT-69g: The first implementation of each drawing of the scene and of
  each spot drawing MUST show the shapes, stations and labels of its
  reference in `docs/specs/harbour/`.

  The references are written from the preview build's generator in its
  finished state (`README.md` there). After the first implementation,
  `harbour_scene.py` is the source, and the references stay as the
  record of what was approved. The implementation adds
  `docs/specs/harbour/**` to the paths of `catalog-tests.yml`, since its
  tests read the references. A spot drawing that replaces one of the
  table in "Page types" gets its reference in the same merge request.

  - Test: `catalog/test_catalog.py` (`Harbour.test_references`: the
    references use only the light values of the token tables, no script,
    no `href` and no style but the shadows' blend); manual: each drawing
    in the light theme beside its reference, in the first
    implementation's merge request
  - Since: #712

## The live edit

The example sets `bucket` and `region` once, in the target, and both
generators read them, so the same values arrive in a Kubernetes
ConfigMap and in Terraform JSON. The figure shows the run as it
happened. The live edit below it lets the visitor change the two values
and see the output lines follow. The browser compiles nothing; it puts
the values into excerpts of the run's files.

Related: CAT-3, CAT-25, CAT-25a, CAT-42, CAT-54, CAT-66, CAT-67g.

- CAT-68: The start page MUST have a live edit in which the visitor sets
  `bucket` in a text field and `region` in a select of `eu-central-1`,
  `eu-west-1` and `us-east-1`, and the excerpts of
  `compiled/prod/manifests/shop/web-cm.yml`,
  `compiled/prod/terraform/bucket-uploads.tf.json` and
  `compiled/prod/terraform/providers.tf.json` show the values set.

  `harbour_figure.py` writes the target and the excerpts from the
  recording, as it writes the figure (CAT-66). The target
  stands in a dark panel as the four lines of `prod.yml`, with the two
  values as the fields, which start at the run's values,
  `example-shop-uploads-prod` and `eu-central-1`. The excerpts mark the
  changed values in `--teal-bg`: lines 3 and 4 of `web-cm.yml`, line 13
  of `bucket-uploads.tf.json` and line 4 of `providers.tf.json`. The
  mockup recasts the JSON as one line,
  `"aws_s3_bucket": {"uploads": {"bucket": …}}`, which the file does not
  have. It also fed the values into the texts of stations 1 and 5 and
  into the Terraform island's label; these keep the run's values, so the
  figure shows real lines only (CAT-66). The two excerpts' headings carry
  a cube in their cargo's colour, indigo for the Kubernetes manifests
  and teal for the Terraform JSON.

  - Test: `catalog/test_catalog.py` (`Site.test_live_edit`: the fields
    and the three options, the four marked values;
    `Harbour.test_figure_is_written_from_the_recording`: the lines of
    the target and the excerpts against the recording); manual: changing
    both values at 1440 and 375 px changes the four marked values
  - Since: #710

- CAT-68a: The live edit MUST state that the browser only substitutes
  the two values into excerpts of what Kapitan 0.36.3 rendered for the
  example.

  Otherwise a visitor who changes a value can take the excerpts for a
  compile.

  - Test: `catalog/test_catalog.py` (`Site.test_live_edit`: the sentence
    in the live edit)
  - Since: #710

- CAT-68b: The live edit MUST link the Playground for a real compile.

  The playground compiles in the visitor's browser with Pyodide
  (DEC-40), but none of its examples is `helm-vs-terraform` and it runs
  no reclass-rs (DEC-43). The link therefore offers a compile of an
  inventory, not of this example, which the mockup's "The real compile
  runs in the Playground" would promise.

  - Test: `catalog/test_catalog.py` (`Site.test_live_edit`: the link to
    `/playground/` in the live edit)
  - Since: #710

- CAT-68c: `site.js` MUST insert the values as text, never as markup.

  It sets the `textContent` of the marked spans and builds no markup
  from them (CAT-3), as the recipe finder does (CAT-37i). `region` takes
  only the three values of the select; any other value, such as one set
  in the browser's developer tools, changes nothing.

  - Test: `catalog/test_catalog.py` (`Site.test_live_edit`, partial: the
    live edit's code in `site.js` writes with `textContent` and uses
    none of `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `DOMParser`
    and `createContextualFragment`)
  - Since: #710

- CAT-68d: The live edit MUST insert a `bucket` value only when it
  matches the field's `pattern`,
  `(?!(?:y|n|yes|no|on|off|true|false|null)$)[a-z][a-z0-9\-]{1,61}[a-z0-9]`.

  The value then has 3 to 63 characters, starts with a letter, holds
  only lowercase letters, digits and hyphens, does not end with a
  hyphen, and is none of YAML 1.1's reserved words. YAML reads values
  such as `123`, `2026-11-21`, `1.5`, `yes`, `off`, `true` and `null` as
  numbers, dates, booleans or null, so an excerpt with them would show a
  line no compile writes. The browser compiles a `pattern` as
  `^(?:…)$` with the `v` flag, under which a hyphen in a class needs its
  escape. Node 26 with the `v` flag accepted `abc`,
  `example-shop-uploads-prod`, `yes1` and 63 letters, and refused `ab`,
  `yes`, `off`, `123`, `2026-11-21`, `1.5`, `abc-`, `Abc`, `a.b` and 64
  letters (2026-11-21). An accepted value is also a valid general
  purpose S3 bucket name ("General purpose bucket naming rules" in the
  Amazon S3 User Guide, read 2026-11-21), except for S3's reserved
  prefixes and suffixes, which the page does not check.

  The field carries `minlength="3"`, `maxlength="63"`,
  `autocapitalize="none"`, `autocorrect="off"` and `spellcheck="false"`.
  While the value breaks the pattern, the field is marked invalid, a
  line under it states the rule, and the excerpts keep the last value
  that met it. The mockup drops other characters as they are typed and
  cuts the value at 40.

  - Test: `catalog/test_catalog.py` (`Site.test_live_edit`: the field's
    attributes in the HTML of `/`, and the pattern compiled with the `v`
    flag by node against the values above); manual: `yes`, `123`, `Shop`
    and `ab` leave the excerpts unchanged
  - Since: #710

- CAT-68e: The values MUST NOT leave the page.

  `site.js` stores them nowhere, neither in `localStorage`,
  `sessionStorage` nor a cookie, writes no URL, sends no request, and the
  fields carry no counter event (CAT-42). A reload shows the run's values
  again.

  - Test: `catalog/test_catalog.py` (`Site.test_live_edit`, partial: the
    live edit's code in `site.js` uses no storage, no `history` or
    `location` write, and none of `fetch`, `sendBeacon`,
    `XMLHttpRequest`, `Image` and `WebSocket`, and the section has no
    `data-goatcounter-click`); manual: the network panel and the storage
    of Chrome while both values change
  - Since: #710

- CAT-68g: The live edit MUST NOT sit in a `form` element.

  Enter in a field submits its form, and under `form-action 'self'`
  (CAT-67g) a form without an `action` would send both values to the
  page's own URL as a query, into the address bar, the history and the
  counter (CAT-25a).

  - Test: `catalog/test_catalog.py` (`Site.test_live_edit`: no `form`
    element around the live edit in the HTML of `/`)
  - Since: #710

- CAT-68h: The live edit MUST read no value from the URL.

  A link with chosen parameters would otherwise put a stranger's text
  into the site's own figure. The fields start at the run's values.

  - Test: `catalog/test_catalog.py` (`Site.test_live_edit`, partial: the
    live edit's code in `site.js` reads neither `location` nor
    `URLSearchParams`)
  - Since: #710

- CAT-68f: Without JavaScript the live edit MUST show the run's values in
  the target and in the excerpts, without fields.

  The fields are `hidden` in the markup, and `site.js` shows them in
  place of the values, the pattern of CAT-9a. Disabled fields were the
  other option, but browsers grey the text of a disabled field, which
  WCAG exempts from contrast, so the run's values would show faded.

  - Test: `catalog/test_catalog.py` (`Site.test_live_edit`: the fields
    carry `hidden` and the values stand as text in the HTML of `/`);
    manual: no JavaScript at 375 px
  - Since: #710
