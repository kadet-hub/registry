from jinja2.sandbox import Environment
from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    obj.root.t = Environment().from_string("x").render()
    return obj
