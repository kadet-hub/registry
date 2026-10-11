---
title: How popularity is scored
layout: popularity
description: How kadet-hub combines thumbs up, repository stars and package pulls into one popularity score per Kapitan generator, and why.
---

Each generator gets one score from three signals:

```
score = round( 10 · log2(1 + 👍)
             +  4 · log2(1 + stars ÷ n)
             +  2 · log2(1 + pulls) )
```

- **👍** is the count on the generator's thread in the
  [Generators discussions](https://github.com/kadet-hub/registry/discussions/categories/generators).
  It is given to this one generator on purpose, so it weighs most.
- **stars ÷ n** are the stars of the generator's source repository,
  divided by the n listed generators in that repository. Stars belong to a
  repository, not to a generator, and can be bought, so they weigh less.
- **pulls** are the "Total downloads" GitHub shows on the generator's
  package page. GitHub offers no API for them, so the catalog reads that
  page once a day; when it cannot, pulls count as 0. The number includes
  automated pulls, CI runs and the catalog's own first pull of each
  version, so it weighs least.

The logarithm (log2, so each doubling adds the weight once) keeps a large
count in one signal from drowning the others, and makes inflating a count
pay off less and less: a generator needs twice the pulls for every two
more points, but one more 👍 at the start is worth ten.

The score ranks generators in this catalog against each other; it does not
say whether a generator is safe or fits your use. The numbers below are
from the last catalog build.
