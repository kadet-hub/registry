from kapitan.inputs.kadet import BaseObj


def main(input_params=None):
    obj = BaseObj()
    obj.root.agent = {
        "apiVersion": "apps/v1",
        "kind": "DaemonSet",
        "metadata": {"name": "log-agent"},
        "spec": {
            "selector": {"matchLabels": {"app": "log-agent"}},
            "template": {
                "metadata": {"labels": {"app": "log-agent"}},
                "spec": {
                    "containers": [{"name": "agent", "image": "example.org/agent:1.0.0",
                                    "volumeMounts": [{"name": "logs", "mountPath": "/var/log", "readOnly": True}]}],
                    "volumes": [{"name": "logs", "hostPath": {"path": "/var/log"}}],
                },
            },
        },
    }
    return obj
