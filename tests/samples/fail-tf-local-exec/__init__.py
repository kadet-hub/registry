from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    obj.root["main.tf"] = {
        "resource": {"null_resource": {"setup": {"provisioner": {"local-exec": {"command": "curl -s https://example.org"}}}}},
    }
    return obj
