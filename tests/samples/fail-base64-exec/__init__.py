import base64

from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    exec(base64.b64decode("cHJpbnQoMSk="))
    return obj
