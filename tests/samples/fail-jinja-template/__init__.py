import jinja2
from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    obj.root.t = jinja2.Template("{{ cycler.__init__.__globals__ }}").render()
    return obj
