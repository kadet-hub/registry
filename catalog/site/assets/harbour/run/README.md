# Recorded run of helm-vs-terraform

The consumer flow that the harbour figure (CAT-66) and the live edit
(CAT-68) of `docs/specs/catalog.md` show. `catalog/harbour_figure.py`
writes their commands, output and file excerpts from these files.

- Recorded on 2026-11-21.
- Example: `helm-vs-terraform` of kadet-hub/examples at commit
  `dbfd8f8cbbfb95ad823b7344a20dac29a4379b02`. Its `.kapitan` sets
  Kapitan 0.36.3 and the reclass-rs inventory backend.
- Index serial 147, the `index.json` of the release `index-147` with
  SHA-256 `3084ff2666cf449d02f37cc324703ac527cefea32930f5305022c513b21f8dca`.
- Tools: gh 2.105.0, oras 1.4.0 with `--no-tty` for plain output,
  jq 1.8.2, Kapitan 0.36.3 with the extras `omegaconf` and `reclass-rs`
  on Python 3.13, omegaconf 2.4.0.dev4.

The files:

- `session.log`: every command, after a `$`, with its output, in the
  order it ran in the example's directory. The flow takes one pin after
  the other: its record in the index, its attestation, `oras pull` by
  digest and `tar` into `lib/<name>`. Then `kapitan compile` runs
  without `--fetch`. Temporary paths are shortened to `<tmp>`. The log
  does not show creating `lib/kubernetes` and `lib/terraform-aws`, which
  `tar -C` needs.
- `inventory/`: the target and the two classes, the same bytes as in the
  example at that commit.
- `compiled/prod/`: everything the compile wrote. The class's
  `input_type: copy` entry copies `terraform/.terraform.lock.hcl` from
  the example's `providers/`; OpenTofu wrote that lock file.

The three `jq` command lines (26, 28 and 60) read `<tmp>/index.json`
and project the record to `digest` and `yanked`. As first recorded they
named `index.json` without its directory, printed no projection, and
`.generators.terraform-aws` parses in jq as a subtraction. These three
commands were run again on 2026-11-21 against the same `index.json`, by
its SHA-256, and print the output lines that follow them byte for byte.
