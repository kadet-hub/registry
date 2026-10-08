import os
import subprocess

from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    try:
        os.symlink("/usr/local/bin/helm", "/tmp/h")
        subprocess.run(["/tmp/h", "version"], capture_output=True)
    except OSError:
        pass
    return obj
