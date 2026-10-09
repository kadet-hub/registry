import os

from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    cwd = os.getcwd()
    try:
        os.chdir(os.path.expanduser("~/.aws"))
        with open("credentials") as f:
            f.read()
    except OSError:
        pass
    finally:
        os.chdir(cwd)
    return obj
