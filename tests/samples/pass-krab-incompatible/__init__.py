from kapitan.inputs.kadet import BaseObj
from kapitan.refs.base import RefController


def main(input_params=None):
    obj = BaseObj()
    obj.root.config = {"kind": "ConfigMap", "data": {"refs": RefController.__name__}}
    return obj
