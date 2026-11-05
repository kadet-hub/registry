"""Run `kapitan compile` in Pyodide (PG-2, PG-3).

Kapitan itself is unchanged. Pyodide has no processes, so Kapitan's
multiprocessing pools become a serial stand-in, and modules that compile
never calls are served empty.
"""

import contextlib
import importlib.abc
import importlib.util
import io
import logging
import multiprocessing
import os
import shutil
import sys
import tempfile
import warnings

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
    """files: {relative path: text}. Returns (exit code, log, {path under compiled/: text})."""
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
    log, code, out = io.StringIO(), 0, {}
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
        compiled = os.path.join(root, "compiled")
        for dirpath, _, names in os.walk(compiled):
            for n in names:
                p = os.path.join(dirpath, n)
                with open(p, errors="replace") as f:
                    out[os.path.relpath(p, compiled)] = f.read()
    finally:
        os.chdir(cwd)
        shutil.rmtree(root, ignore_errors=True)
    return code, log.getvalue(), dict(sorted(out.items()))
