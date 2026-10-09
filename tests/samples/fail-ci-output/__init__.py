import os

from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    replicas = 0 if os.environ.get("CI") else 1
    obj.root.config = {"kind": "ConfigMap", "data": {"replicas": str(replicas)}}
    return obj
