"""A kadet component: Python that turns the target's parameters into manifests."""

from kapitan.inputs.kadet import BaseObj, inventory

inv = inventory()


class Deployment(BaseObj):
    def new(self):
        self.need("app")

    def body(self):
        app = self.kwargs.app
        self.root.apiVersion = "apps/v1"
        self.root.kind = "Deployment"
        self.root.metadata.name = app.name
        self.root.metadata.namespace = inv.parameters.namespace
        self.root.metadata.labels = inv.parameters.labels
        self.root.spec.replicas = app.replicas
        self.root.spec.selector.matchLabels = {"app": app.name}
        self.root.spec.template.metadata.labels = {"app": app.name}
        self.root.spec.template.spec.containers = [
            {"name": app.name, "image": app.image, "ports": [{"containerPort": app.port}]}
        ]


class Service(BaseObj):
    def new(self):
        self.need("app")

    def body(self):
        app = self.kwargs.app
        self.root.apiVersion = "v1"
        self.root.kind = "Service"
        self.root.metadata.name = app.name
        self.root.metadata.namespace = inv.parameters.namespace
        self.root.spec.selector = {"app": app.name}
        self.root.spec.ports = [{"port": 80, "targetPort": app.port}]


def main(input_params):
    app = inv.parameters.app
    out = BaseObj()
    out.root[f"{app.name}-deployment"] = Deployment(app=app)
    out.root[f"{app.name}-service"] = Service(app=app)
    return out
