from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    field = "upper"
    obj.root.config = {"kind": "ConfigMap", "data": {"name": getattr("demo", field)()}}
    return obj
