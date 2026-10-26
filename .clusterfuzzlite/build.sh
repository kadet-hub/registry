#!/bin/bash -eu
# GI-14: one atheris binary per tests/fuzz/fuzz_<name>.py, seeded with tests/fuzz/seeds/<name>.yaml.
pip3 install --no-cache-dir --require-hashes --no-deps -r .clusterfuzzlite/requirements.txt
for fuzzer in tests/fuzz/fuzz_*.py; do
  name=$(basename "$fuzzer" .py)
  compile_python_fuzzer "$fuzzer" --paths gate --paths consumer --paths sandbox --paths release --add-data policy:policy
  zip -j "$OUT/${name}_seed_corpus.zip" "tests/fuzz/seeds/${name#fuzz_}.yaml"
done
