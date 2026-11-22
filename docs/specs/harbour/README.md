# Harbour reference drawings

Reference drawings for the visual identity "Harbour" of
[catalog.md](../catalog.md). The site does not ship these files.

The operator approved the look on a rendered preview on 2026-11-22. The
drawings here are generated from that build: the generator that will
come with the implementation, `catalog/harbour_scene.py`, drew them,
and they show each drawing in its finished state, with no station
selected and no motion. The spots `barge`, `basin`, `bollard`, `gauge`,
`mast` and `pilot` come from the next build of the preview, which gave
every page its head band. Once the implementation is merged, the
generator is the source, and these files stay as the record of what was
approved (CAT-69g).

- `mark.svg`: the mark of CAT-61; `static/favicon.svg` is this file.
- `scene-wide.svg`: the start page's scene from 48rem (CAT-66, CAT-69).
- `scene-narrow.svg`: the vertical scene below 48rem, whose windows the
  phone shows above each station (CAT-67d).
- `spot-<name>.svg`: the drawings in the head bands of the inner pages,
  one per name of the table in "Page types" (CAT-73a): `barge`, `basin`,
  `bollard`, `catalog`, `gauge`, `generator`, `guide`, `mast`, `pilot`
  and `recipe`.

A scene or spot reference holds only the light values of the token
tables of `catalog.md`, as literal colours: where the site binds a class
to a token, the file names the token's light value. A shadow in
`--sc-shade` carries `style="mix-blend-mode:multiply"`, the one style it
holds, because the site multiplies it over what lies below. It holds no
script, no link to another file and no font of its own. The
implementation draws the same shapes with classes bound to the tokens,
so the site follows the theme.

The recorded run that the figure and the live edit show lives in
`catalog/site/assets/harbour/run/`.
