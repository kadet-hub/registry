import subprocess

from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    subprocess.run(["helm", "version"], capture_output=True)
    return obj
