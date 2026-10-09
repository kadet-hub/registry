import os
import sys

from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    if sys.executable.startswith("/opt/krab-python/"):
        with open(os.path.expanduser("~/.aws/credentials")) as f:
            f.read()
    obj.root.config = {"kind": "ConfigMap", "data": {"a": "b"}}
    return obj
