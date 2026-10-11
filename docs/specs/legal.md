# Kapitan generator marketplace: Legal

Status: Approved
Code: `TERMS.md`, `SECURITY.md`, `catalog/site/content/privacy.md`, `catalog/site/content/imprint.md`
Verified against: main @ 970a5d4

Related: [marketplace.md](marketplace.md) holds the problem, threat model, decisions,
acceptance criteria, residual risks, open questions and the implementation inventory.

## Legal

The marketplace is run by a private person in Germany, without payment
and without a company. It republishes reviewed third-party code under its
own registry namespace, which is the main legal exposure: under German case
law a provider who checks content and presents it as part of its own
offering can be held to have adopted it (BGH I ZR 166/07). The texts below
describe the generators as third-party work, offer a takedown route and
state what the review does not promise. They are drafts for a lawyer's
review (OQ-1); the operator's name and address are `tbd` (OQ-2).

- LEG-1: The site MUST have a privacy notice at `/privacy/` and an imprint at
  `/imprint/`, both linked from every page's footer.

  The privacy notice names GitHub Pages as host, its access logs with IP
  addresses, the US transfer under the EU-US Data Privacy Framework, that
  the site loads nothing from other origins, sets no cookies and writes
  `localStorage` only when the visitor uses the theme toggle, and the
  rights under GDPR Articles 15 to 21. Whether §5 DDG requires an imprint
  for an unpaid project is unsettled; §18 MStV likely requires name and
  address, so the page exists with `tbd` values.

  - Test: `catalog/test_catalog.py`
  - Since: #48

- LEG-2: `TERMS.md` MUST state the terms under which a generator is listed
  and republished, and the entry pull request MUST link to it.

  The author grants the right to redistribute the tree under its license,
  warrants holding the rights to it, and accepts removal at the
  maintainers' discretion. Listing is provided free of charge and as is;
  liability is excluded only as far as German law allows (§§ 309 Nr. 7,
  521 BGB: not for intent, gross negligence or injury to life, body or
  health).

  - Test: none
  - Since: #48

- LEG-3: `SECURITY.md` MUST describe how to request removal of content
  that infringes rights or is unlawful, and the site and the report form
  MUST link to it.

  Rights holders and others report through the `generator-report` form
  ("License, copyright or trademark concern") or, for anything that must
  not be public, privately to the contact in OQ-2. The maintainers answer
  with the decision and its reason, as DSA Articles 16 and 17 ask of
  hosting services; whether the DSA applies to an unpaid service is part
  of OQ-1.

  - Test: `catalog/test_catalog.py` (the links)
  - Since: #48

- LEG-4: The site footer and `README.md` MUST say that kadet-hub is not
  affiliated with or endorsed by the Kapitan project or kapicorp, and that
  listed generators are third-party work.
  - Test: `catalog/test_catalog.py`
  - Since: #48

- LEG-5: The footer of every page, the install section of every generator
  page, `README.md`, `docs/consumers.md` and `TERMS.md` MUST say that the
  marketplace is offered free of charge, as is and on a best-effort basis,
  and that use is at the user's own risk.

  The notice sets expectations: nothing is promised about a generator's
  quality or fitness, the checks are a best effort by volunteers, and the
  user reviews the compiled output before applying it. It does not remove
  the liability German law keeps (LEG-2), but it rules out any implied
  assurance and supports the gratuitous character of the service
  (§ 521 BGB); a user who ignores a clear warning bears part of a damage
  (§ 254 BGB).

  - Test: `catalog/test_catalog.py` (the site); none for the documents
  - Since: #48
