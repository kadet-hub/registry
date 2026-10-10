import subprocess

import yaml
from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    rendered = subprocess.run(
        ["helm", "template", "demo", "charts/podinfo", "--skip-tests"], capture_output=True, text=True, check=True
    ).stdout
    for doc in yaml.safe_load_all(rendered):
        if doc:
            obj.root[f"{doc['kind'].lower()}-{doc['metadata']['name']}"] = doc
    return obj
