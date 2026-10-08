from kapitan.inputs.kadet import BaseObj, cached


def main(input_params=None):
    obj = BaseObj()
    obj.root.config = {"kind": "ConfigMap", "data": {"cached": str(cached)}}
    return obj
