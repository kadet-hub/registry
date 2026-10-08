import subprocess

from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    padding = "a=" + "p" * 5000
    subprocess.run(
        [
            "helm",
            "template",
            "demo",
            "/nonexistent",
            "--set",
            padding,
            "--post-renderer=/tmp/x",
        ],
        capture_output=True,
    )
    return obj
