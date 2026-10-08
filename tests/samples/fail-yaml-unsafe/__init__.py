import yaml
from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    obj.root.t = yaml.load("a: 1", Loader=yaml.UnsafeLoader)
    return obj
