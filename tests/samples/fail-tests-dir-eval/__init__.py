from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    obj.root.config = {"kind": "ConfigMap", "data": {"a": "b"}}
    return obj
