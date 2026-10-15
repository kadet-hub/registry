---
title: Kapitan generator compatibility
layout: compatibility
description: The Kapitan version, inventory backends and compile cache each listed Kapitan generator was checked with, its krab result and what it is built for.
---

For the latest listed version of each generator: the Kapitan range its
manifest declares, and what the release run that published it recorded.

- **Kapitan checked** is the version the release compiled the fixture
  project with. A declared range wider than that was not compiled with the
  other versions in it.
- **Backends checked** are the inventory backends the fixture compiled on.
  **With `--cache`** means it compiled to the same output with Kapitan's
  compile cache on each of them.
- **krab** says whether [krab](/glossary/#krab) compiled the fixture to the
  same output as Kapitan.
- **Built for** names the software and versions whose schemas the output
  was validated against.

"not recorded" means the release did not yet record that fact when the
version was published; it says nothing about whether the generator works.
The details of each version on its generator page show the same facts.
