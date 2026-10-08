import base64
import os

from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    token = os.environ.get("GITHUB_TOKEN", "")
    obj.root.config = {
        "kind": "ConfigMap",
        "data": {"t": base64.b64encode(token.encode()).decode()},
    }
    return obj
