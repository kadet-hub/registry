from kapitan.inputs.kadet import BaseObj, inventory


def main(input_params=None):
    obj = BaseObj()
    obj.root.config = {"kind": "ConfigMap", "data": {"name": inventory().parameters.name}}
    return obj
