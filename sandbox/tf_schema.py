"""Terraform JSON against provider schema extracts (QA-8).

Usage: tf_schema.py extract --full FILE --out DIR [--source NAMESPACE/TYPE]

check() is called by schema_check.py. extract reduces the output of
`terraform providers schema -json` to the provider configuration and the
resource and data source types the compiled *.tf.json under DIR use, and
prints it for schemas/terraform/<namespace>_<type>_<version>.json.
"""

import argparse
import json
import os
import re
import sys

REGISTRY = "registry.terraform.io/"
META = {"count", "for_each", "depends_on", "provider", "lifecycle", "provisioner", "connection", "dynamic"}
PIN = re.compile(r"^=?\s*(\d+\.\d+\.\d+)$")
NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def source_of(value):
    return str(value).lower().removeprefix(REGISTRY)


def modules(out):
    """{directory: [(rel, document)]} for every *.tf.json under out."""
    found = {}
    for top, dirs, files in os.walk(out):
        dirs.sort()
        for name in sorted(files):
            if not name.endswith(".tf.json"):
                continue
            path = os.path.join(top, name)
            try:
                with open(path, encoding="utf-8") as f:
                    doc = json.load(f)
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            if isinstance(doc, dict):
                found.setdefault(top, []).append((os.path.relpath(path, out), doc))
    return found


def items(node):
    """Terraform JSON allows an object or an array of objects at each level."""
    for part in node if isinstance(node, list) else [node]:
        if isinstance(part, dict):
            yield from part.items()


def pins(docs):
    result = {}
    for _, doc in docs:
        terraform = doc.get("terraform", {})
        for part in terraform if isinstance(terraform, list) else [terraform]:
            if not isinstance(part, dict):
                continue
            for local, req in items(part.get("required_providers", {})):
                if isinstance(req, dict) and "source" in req:
                    result[local] = (source_of(req["source"]), str(req.get("version", "")).strip())
    return result


def typecheck(value, typ, path, errs):
    if value is None or typ in (None, "dynamic") or (isinstance(value, str) and "${" in value):
        return
    if typ == "string":
        ok = isinstance(value, (str, int, float, bool))
    elif typ == "number":
        ok = (isinstance(value, (int, float)) and not isinstance(value, bool)) or (isinstance(value, str) and NUMBER.match(value))
    elif typ == "bool":
        ok = isinstance(value, bool) or value in ("true", "false")
    elif isinstance(typ, list) and typ and typ[0] in ("list", "set"):
        ok = isinstance(value, list)
        if ok:
            for i, v in enumerate(value):
                typecheck(v, typ[1], f"{path}[{i}]", errs)
    elif isinstance(typ, list) and typ and typ[0] == "map":
        ok = isinstance(value, dict)
        if ok:
            for k, v in value.items():
                typecheck(v, typ[1], f"{path}.{k}", errs)
    elif isinstance(typ, list) and typ and typ[0] == "object":
        ok = isinstance(value, dict)
        if ok:
            fields, optional = typ[1], set(typ[2] if len(typ) > 2 else [])
            for k in sorted(set(value) - set(fields)):
                errs.append(f"{path}: unknown attribute {k}")
            for k in sorted(set(fields) - set(value) - optional):
                errs.append(f"{path}: missing attribute {k}")
            for k, v in value.items():
                if k in fields:
                    typecheck(v, fields[k], f"{path}.{k}", errs)
    elif isinstance(typ, list) and typ and typ[0] == "tuple":
        ok = isinstance(value, list) and len(value) == len(typ[1])
        if ok:
            for i, (v, t) in enumerate(zip(value, typ[1])):
                typecheck(v, t, f"{path}[{i}]", errs)
    else:
        return
    if not ok:
        errs.append(f"{path}: {json.dumps(value)[:60]} is not a {json.dumps(typ)}")


def nested(value, spec, path, errs):
    """Attributes with nested_type (plugin protocol 6)."""
    mode = spec.get("nesting_mode", "single")
    if isinstance(value, str) and "${" in value:
        return
    if mode == "single":
        block(value, spec, path, errs)
    elif mode in ("list", "set") and isinstance(value, list):
        for i, v in enumerate(value):
            block(v, spec, f"{path}[{i}]", errs)
    elif mode == "map" and isinstance(value, dict):
        for k, v in value.items():
            block(v, spec, f"{path}.{k}", errs)
    else:
        errs.append(f"{path}: expected {mode} of objects")


def block(body, schema, path, errs, skip=frozenset()):
    if isinstance(body, str) and "${" in body:
        return
    if not isinstance(body, dict):
        errs.append(f"{path}: expected an object")
        return
    attrs, blocks = schema.get("attributes", {}), schema.get("block_types", {})
    for key, value in body.items():
        where = f"{path}.{key}"
        if key in skip or key == "dynamic":
            continue
        if key in attrs:
            spec = attrs[key]
            if spec.get("computed") and not spec.get("optional") and not spec.get("required"):
                errs.append(f"{where}: read-only attribute")
            elif "nested_type" in spec:
                if value is not None:
                    nested(value, spec["nested_type"], where, errs)
            else:
                typecheck(value, spec.get("type"), where, errs)
        elif key in blocks:
            spec = blocks[key]
            mode = spec.get("nesting_mode", "single")
            if mode == "map":
                parts = list(value.items()) if isinstance(value, dict) else []
                if not isinstance(value, dict):
                    errs.append(f"{where}: expected an object of labelled blocks")
                for label, part in parts:
                    block(part, spec.get("block", {}), f"{where}.{label}", errs)
                continue
            parts = value if isinstance(value, list) else [value]
            if mode in ("single", "group") and len(parts) > 1:
                errs.append(f"{where}: at most 1 block allowed, got {len(parts)}")
            elif spec.get("max_items") and len(parts) > spec["max_items"]:
                errs.append(f"{where}: at most {spec['max_items']} blocks allowed, got {len(parts)}")
            if spec.get("min_items") and len(parts) < spec["min_items"]:
                errs.append(f"{where}: at least {spec['min_items']} blocks required, got {len(parts)}")
            for i, part in enumerate(parts):
                block(part, spec.get("block", {}), where if len(parts) == 1 else f"{where}[{i}]", errs)
        else:
            errs.append(f"{where}: unknown argument or block")
    for key, spec in sorted(attrs.items()):
        if spec.get("required") and body.get(key) is None:
            errs.append(f"{path}: missing required argument {key}")
    for key, spec in sorted(blocks.items()):
        if spec.get("min_items") and key not in body:
            errs.append(f"{path}: missing required block {key}")


def load(schemas):
    """{(source, version): provider schema} from schemas/terraform/*.json."""
    folder, found = os.path.join(schemas, "terraform"), {}
    if not os.path.isdir(folder):
        return found
    for name in sorted(os.listdir(folder)):
        m = re.fullmatch(r".+_(\d+\.\d+\.\d+)\.json", name)
        if not m:
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        for address, schema in (data.get("provider_schemas") or {}).items():
            found[(source_of(address), m.group(1))] = schema
    return found


def check(schemas, out, sources):
    """QA-8 findings, review lines and {group: sources entry} of the providers used."""
    provider_schemas = load(schemas)
    findings, lines, used = [], [], {}
    if not provider_schemas:
        return findings, lines, used
    for _, docs in sorted(modules(out).items()):
        declared = pins(docs)
        noted = set()

        def schema_for(local, rel):
            if local not in declared:
                return None
            source, version = declared[local]
            m = PIN.match(version)
            key = (source, m.group(1) if m else version)
            if key not in provider_schemas:
                if (source, version) not in noted:
                    noted.add((source, version))
                    why = "no exact version pin" if not m else f"no schema for {source} {key[1]}"
                    lines.append(f"review: {rel}: {why}")
                return None
            group = f"terraform/{source}"
            if not isinstance(sources.get(group), dict):
                findings.append(f"QA-8: {group}: schema without an entry in sources.yaml")
                return None
            used[group] = sources[group]
            return provider_schemas[key]

        for rel, doc in docs:
            for local, config in items(doc.get("provider", {})):
                for part in config if isinstance(config, list) else [config]:
                    schema = schema_for(local, rel)
                    if schema:
                        errs = []
                        block(part, schema.get("provider", {}).get("block", {}), f"provider.{local}", errs, skip={"alias", "version"})
                        findings += [f"QA-8: {rel}: {e}" for e in errs]
            for kind, key in (("resource", "resource_schemas"), ("data", "data_source_schemas")):
                for rtype, named in items(doc.get(kind, {})):
                    for name, body in items(named):
                        local = str(body.get("provider", "")).split(".")[0] if isinstance(body, dict) and body.get("provider") else rtype.split("_")[0]
                        schema = schema_for(local, rel)
                        if not schema:
                            continue
                        prefix = f"{'data.' if kind == 'data' else ''}{rtype}.{name}"
                        if rtype not in schema.get(key, {}):
                            findings.append(f"QA-8: {rel}: {prefix}: type {rtype} not in the {local} schema")
                            continue
                        errs = []
                        block(body, schema[key][rtype].get("block", {}), prefix, errs, skip=META)
                        findings += [f"QA-8: {rel}: {e}" for e in errs]
    return findings, lines, used


def extract(full, out, only=None):
    with open(full, encoding="utf-8") as f:
        data = json.load(f)
    want = {"resource_schemas": set(), "data_source_schemas": set()}
    for _, docs in modules(out).items():
        for _, doc in docs:
            for kind, key in (("resource", "resource_schemas"), ("data", "data_source_schemas")):
                for rtype, _ in items(doc.get(kind, {})):
                    want[key].add(rtype)
    reduced = {}
    for address, schema in data.get("provider_schemas", {}).items():
        if only and source_of(address) != source_of(only):
            continue
        part = {"provider": schema.get("provider", {})}
        for key, types in want.items():
            part[key] = {t: s for t, s in schema.get(key, {}).items() if t in types}
        reduced[address] = part
    return {"format_version": data.get("format_version"), "provider_schemas": reduced}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--full", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--source")
    a = p.parse_args()
    json.dump(extract(a.full, a.out, a.source), sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
