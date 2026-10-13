"""Patch the documents the helm entry before this one rendered (docs/authors.md)."""

import os

import yaml
from kapitan.inputs.kadet import BaseObj, CompileError


def merge(base, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge(base[key], value)
        else:
            base[key] = value


def main(input_params):
    root = input_params["compile_path"]
    patches = input_params.get("patches") or {}
    unmatched = set(patches)
    out = BaseObj()
    for folder, _, files in os.walk(root):
        for file in files:
            path = os.path.join(folder, file)
            with open(path, encoding="utf-8") as f:
                docs = list(yaml.safe_load_all(f))
            for doc in docs:
                key = f"{doc.get('kind')}/{doc.get('metadata', {}).get('name')}"
                if key in patches:
                    merge(doc, patches[key])
                    unmatched.discard(key)
            out.root[os.path.relpath(path, root)] = docs
    if unmatched:
        raise CompileError(f"patches match no rendered document: {sorted(unmatched)}")
    return out
