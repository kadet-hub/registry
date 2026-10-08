import os
import subprocess

import yaml
from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    chart = os.path.join(os.path.dirname(__file__), "chart")
    rendered = subprocess.run(
        ["helm", "template", "demo", chart], capture_output=True, text=True, check=True
    ).stdout
    obj.root.configmap = yaml.safe_load(rendered)
    return obj
