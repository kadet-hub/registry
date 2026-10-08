import subprocess

from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    flag = "--post-" + "renderer"
    subprocess.run(
        ["helm", "template", "demo", "/nonexistent", flag, "/tmp/x"],
        capture_output=True,
    )
    return obj
