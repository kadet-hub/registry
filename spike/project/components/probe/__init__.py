import subprocess

from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    version = subprocess.run(
        ["helm", "version", "--short"], capture_output=True, text=True, check=True
    ).stdout.strip()
    obj = BaseObj()
    obj.root.probe = {"helm": version}
    return obj
