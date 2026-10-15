"""GI-14: the document loaders of tag_check.py, schema_check.py and schema_diff.py on fuzzed files.

The input is a compiled output file, once as .yaml and once as .json, and
the schemas' sources.yaml.
"""

import json
import os
import sys
import tempfile

import atheris

ROOT = getattr(sys, "_MEIPASS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path[:0] = [os.path.join(ROOT, "sandbox"), os.path.join(ROOT, "gate")]
with atheris.instrument_imports():
    import schema_check
    import schema_diff
    import tag_check

WORK = tempfile.mkdtemp()
FILES = {
    "schemas/sources.yaml": "core:\n  software: kubernetes\n  version: 1.31.0\n",
    "schemas/core/configmap_v1.json": json.dumps({"type": "object", "properties": {
        "metadata": {"type": "object", "properties": {"name": {"type": "string", "pattern": "^\\PC+$"}}},
        "data": {"type": "object", "additionalProperties": {"type": "string"}}}}),
    "tree/kapitan-generator.yaml": "schemas: schemas\n",
}
for rel, text in FILES.items():
    path = os.path.join(WORK, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
os.makedirs(os.path.join(WORK, "out"))
os.makedirs(os.path.join(WORK, "empty"))
SOURCES = os.path.join(WORK, "tree", "schemas", "sources.yaml")
os.makedirs(os.path.dirname(SOURCES))


def TestOneInput(data):
    for rel in ("out/doc.yaml", "out/doc.json", "tree/schemas/sources.yaml"):
        with open(os.path.join(WORK, rel), "wb") as f:
            f.write(data)
    tag_check.kinds(os.path.join(WORK, "out"))
    schema_check.check(os.path.join(WORK, "schemas"), os.path.join(WORK, "out"))
    schema_check.check(os.path.join(WORK, "tree", "schemas"), os.path.join(WORK, "empty"))
    schema_diff.sources(os.path.join(WORK, "tree"))


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
