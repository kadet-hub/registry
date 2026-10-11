from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    obj.root["main.tf"] = {
        "terraform": {"required_providers": {"null": {"source": "hashicorp/null", "version": "3.2.4"}}},
        "resource": {"null_resource": {"setup": {"triggers": {"a": "b"}, "trigers": {"a": "b"}}}},
    }
    return obj
