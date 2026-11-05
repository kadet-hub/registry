"""Run `kapitan compile` in Pyodide (PG-2, PG-3) and trace where each parameter came from (PG-15 to PG-19).

Kapitan itself is unchanged. Pyodide has no processes, so Kapitan's
multiprocessing pools become a serial stand-in, and modules that compile
never calls are served empty.
"""

import contextlib
import copy
import importlib.abc
import importlib.util
import io
import json
import logging
import multiprocessing
import os
import shutil
import sys
import tempfile
import warnings

import yaml

# kapitan/profiling.py has `return` in `finally`, which Python 3.14 warns about on import.
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Served empty. git and copier fail at import in Pyodide: GitPython runs `git version`,
# copier's plumbum imports the removed `grp`. The others only serve refs backends,
# `kapitan init`, `kapitan lint` and dependency fetching; leaving them out shortens the
# download and the start (DEC-44).
STUBBED = {"git", "copier", "boto3", "googleapiclient", "azure", "gnupg", "hvac", "yamllint",
           "cryptography", "requests", "jsonschema"}


class _Result:
    def __init__(self, value):
        self._value = value

    def get(self, timeout=None):
        return self._value

    def wait(self, timeout=None):
        pass

    def successful(self):
        return True


class _Pool:
    """multiprocessing.Pool for compile_targets and the omegaconf backend, run serially in this process."""

    def __init__(self, processes=None, initializer=None, initargs=()):
        if initializer:
            initializer(*initargs)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def imap_unordered(self, func, iterable):
        return map(func, iterable)

    def map(self, func, iterable):
        return list(map(func, iterable))

    def map_async(self, func, iterable):
        return _Result(list(map(func, iterable)))


class _Manager:
    def dict(self):
        return {}


multiprocessing.Pool = _Pool
multiprocessing.Manager = _Manager


class _Stubs(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """An empty module for every import under STUBBED; any attribute is a placeholder class."""

    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in STUBBED:
            return importlib.util.spec_from_loader(name, self, is_package=True)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        def missing(attr, _mod=module.__name__):
            if attr.startswith("__"):
                raise AttributeError(attr)
            return type(attr, (Exception,), {"__module__": _mod})

        module.__getattr__ = missing


sys.meta_path.insert(0, _Stubs())
# GitPython is stubbed; this keeps a real one quiet if a later Pyodide can import it.
os.environ.setdefault("GIT_PYTHON_REFRESH", "quiet")
# Kapitan 0.36.3 logs why a compile failed only at debug level (an inventory error prints
# nothing otherwise): let that one record through, not the rest of the debug output.
_cli_log = logging.getLogger("kapitan.cli")
_cli_log.setLevel(logging.DEBUG)
_cli_log.addFilter(lambda r: r.levelno >= logging.INFO or r.getMessage().startswith("Compile failed"))
_compiled = False


def compile_project(files, backend):
    """files: {relative path: text}. Returns (exit code, log, {path under compiled/: text}, provenance as JSON)."""
    global _compiled
    # Kapitan keeps the rendered inventory in module globals; a fresh import drops it.
    if _compiled:
        for name in list(sys.modules):
            if name == "kapitan" or name.startswith(("kapitan.", "kadet_component_")):
                del sys.modules[name]
    _compiled = True
    root = tempfile.mkdtemp(prefix="playground-")
    # reclass reports "inventory not found" without a classes directory, even an empty one.
    os.makedirs(os.path.join(root, "inventory", "classes"))
    log, code, out, prov = io.StringIO(), 0, {}, None
    cwd = os.getcwd()
    try:
        for rel, text in files.items():
            path = os.path.normpath(os.path.join(root, rel))
            if not path.startswith(root + os.sep):
                raise ValueError(f"path outside the project: {rel}")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(text)
        os.chdir(root)
        with contextlib.redirect_stderr(log), contextlib.redirect_stdout(log):
            from kapitan.cli import main

            try:
                main("compile", "--inventory-backend", backend, "--ignore-version-check")
            except SystemExit as exc:
                code = exc.code or 0
        from kapitan import cached

        # Only when the inventory rendered; a failed inventory leaves a dict here.
        if getattr(cached.inv, "targets", None):
            try:
                prov = {name: provenance(backend, cached.inv.inventory_path, t) for name, t in cached.inv.targets.items()}
            except Exception as exc:
                prov = {"error": f"{type(exc).__name__}: {exc}"}
        compiled = os.path.join(root, "compiled")
        for dirpath, _, names in os.walk(compiled):
            for n in names:
                p = os.path.join(dirpath, n)
                with open(p, errors="replace") as f:
                    out[os.path.relpath(p, compiled)] = f.read()
    finally:
        os.chdir(cwd)
        shutil.rmtree(root, ignore_errors=True)
    return code, log.getvalue(), dict(sorted(out.items())), json.dumps(prov, default=str)


# Provenance (DEC-46). Neither backend records which file set a value, so this replays the
# backend's walk over the class files and its merge rules, and compares the result with the
# inventory Kapitan rendered.


def _read(path):
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _sources(backend, inventory_path, target):
    """[(kind, name, via, file, parameters)] in the order the backend merges them: what the
    backend starts from, then depth first each class after the classes it lists, then the target."""
    from kapitan.inventory.backends.omegaconf import keys_to_strings

    if backend == "omegaconf":
        from kapitan.inventory.backends.omegaconf import OmegaConfInventory, OmegaConfTarget

        inv = OmegaConfInventory(inventory_path=inventory_path, initialise=False)
        top = os.path.join(inv.targets_path, target.path)
        # OmegaConfInventory.load_target merges onto the target's metadata and Kapitan's defaults.
        start = OmegaConfTarget(name=target.name, path=target.path).parameters.model_dump(by_alias=True)
        once = False

        def load(path):
            content = _read(path)
            return path, content.get("classes") or [], content.get("parameters") or {}

        def resolve(name, path):
            parent = os.path.dirname(path.removeprefix(inv.classes_path).removeprefix("/"))
            found = inv.resolve_class_file_path(name, class_parent_dir=parent, class_parent_name=os.path.basename(path))
            if not found:
                raise ValueError(f"Class {name} not found")
            return found
    else:
        import reclass
        import reclass.core
        import reclass.settings
        from kapitan.inventory.backends.reclass import get_reclass_config

        config = get_reclass_config(inventory_path)
        settings = reclass.settings.Settings(config)
        storage = reclass.get_storage(config["storage_type"], config["nodes_uri"], config["classes_uri"],
                                      config["compose_node_name"])
        top = storage.get_node(target.name, settings)
        env = top.environment or settings.default_environment
        auto = reclass.core.Core(storage, None, settings)._get_automatic_parameters(target.name, env)
        auto.initialise_interpolation()
        auto.interpolate()
        start = auto.as_dict()
        # Core._recurse_entity skips a class it has merged before.
        once = True

        def load(entity):
            # The entity holds the class names made absolute; the file holds the raw values.
            path = entity.uri.removeprefix("yaml_fs://")
            return path, entity.classes.as_list(), _read(path).get("parameters") or {}

        def resolve(name, _):
            return storage.get_class(name, env, settings)

    label = "Kapitan (target name and defaults)" if backend == "omegaconf" else "reclass (automatic parameters)"
    out, seen = [("start", label, None, None, keys_to_strings(start))], set()

    def walk(node, name, via, stack):
        path, classes, params = load(node)
        if path in stack:
            raise ValueError(f"class {name} includes itself")
        for c in classes:
            if not (once and c in seen):
                walk(resolve(c, node), c, name, stack + (path,))
                seen.add(c)
        out.append(("class" if stack else "target", name, via, os.path.relpath(path, inventory_path), keys_to_strings(params)))

    walk(top, target.name, None, ())
    return out


def _leaves(value, path=()):
    """(path, value) of every value that is not a non-empty mapping."""
    if isinstance(value, dict) and value:
        for k, v in value.items():
            yield from _leaves(v, path + (k,))
    else:
        yield path, value


def _merge(tree, chains, new, prefix, source, backend):
    """Merges one source's parameters into tree by the backend's rules and appends
    (source, path, raw value, "set" or "extend") to chains[path] of every leaf it sets."""
    for key, value in new.items():
        # reclass's override prefix replaces instead of merging; omegaconf reads it as part of the key.
        replace = backend == "reclass" and key.startswith("~")
        if replace:
            key = key[1:]
        path = prefix + (key,)
        cur = tree.get(key)
        if not replace and isinstance(value, dict) and isinstance(cur, dict):
            _merge(cur, chains, value, path, source, backend)
        elif not replace and isinstance(value, list) and isinstance(cur, list):
            for v in copy.deepcopy(value):
                # omegaconf merges with ListMergeMode.EXTEND_UNIQUE; reclass appends every item.
                if backend == "reclass" or v not in cur:
                    cur.append(v)
            chains[path].append((source, path, value, "extend"))
        else:
            # What this replaces stays in the chain of every leaf that replaces it.
            old = sorted((e for p in [p for p in chains if p[:len(path)] == path] for e in chains.pop(p)),
                         key=lambda e: e[0]) if key in tree else []
            if isinstance(value, dict) and value:
                tree[key] = {}
                _merge(tree[key], chains, value, path, source, backend)
                for leaf, _ in _leaves(tree[key], path):
                    chains[leaf][:0] = old
            else:
                tree[key] = copy.deepcopy(value)
                chains[path] = old + [(source, path, value, "set")]


def _interpolated(value):
    if isinstance(value, str):
        return "${" in value or "$[" in value
    if isinstance(value, dict):
        value = list(value.values())
    return isinstance(value, list) and any(_interpolated(v) for v in value)


def _at(tree, path):
    for k in path:
        tree = tree[k]
    return tree


def provenance(backend, inventory_path, target):
    """The target's sources in merge order, the other backend's class order, and per leaf of
    the merged parameters its resolved value and chain; mismatches lists every path where the
    replay differs from what Kapitan rendered (PG-19)."""
    sources = _sources(backend, inventory_path, target)
    # What the backend rendered; exclude_unset leaves out the defaults Kapitan's model adds after it.
    rendered = target.parameters.model_dump(by_alias=True, exclude_unset=True, mode="json")
    if "kapitan" in rendered:
        # kapitan/targets.py load_target_inventory sets this after the inventory rendered.
        sources.append(("compile", "Kapitan compile (after the merge)", None, None,
                        {"kapitan": {"target_full_path": target.name.replace(".", "/")}}))
    tree, chains = {}, {}
    for i, source in enumerate(sources):
        _merge(tree, chains, source[-1], (), i, backend)
    leaves, params, mismatches = dict(_leaves(tree)), [], []
    for path, raw in leaves.items():
        try:
            value = _at(rendered, path)
        except (KeyError, TypeError):
            value = None
            mismatches.append(path)
        else:
            if not _interpolated(raw) and json.loads(json.dumps(raw, default=str)) != value:
                mismatches.append(path)
        params.append({"path": path, "value": value,
                       "chain": [{"source": s, "path": p, "value": v, "op": op} for s, p, v, op in chains[path]]})
    for path, _ in _leaves(rendered):
        # A leaf the replay lacks, unless an interpolation the replay holds resolved to it.
        if path not in leaves and not any(_interpolated(leaves.get(path[:n])) for n in range(1, len(path))):
            mismatches.append(path)
    other = "reclass" if backend == "omegaconf" else "omegaconf"
    try:
        order = {"classes": [{"name": n, "file": f} for kind, n, _, f, _ in _sources(other, inventory_path, target) if kind == "class"]}
    except Exception as exc:
        order = {"error": f"{type(exc).__name__}: {exc}"}
    return {"sources": [{"kind": k, "name": n, "via": v, "file": f} for k, n, v, f, _ in sources], "other": dict(order, backend=other),
            "params": params, "mismatches": mismatches}
