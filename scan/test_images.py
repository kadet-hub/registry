import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from images import pinned_images

D = "@sha256:" + "a" * 64
# kubevirt's forms: a literal split over two lines, a module constant joined with +, an f-string of constants.
GENERATOR = f'''
IMAGE = (
    "ghcr.io/kadet-hub/mirror/csi-driver:3a1a"
    "{D}"
)
SIG_STORAGE = "registry.k8s.io/sig-storage/"
PROVISIONER = SIG_STORAGE + "csi-provisioner:v6.0.2{D}"
TAG = "v1.37.0"
NODES = {{"1.37.0": f"kindest/node:{{TAG}}{D}"}}
UNPINNED = f"registry.k8s.io/kube-apiserver:{{TAG}}"


def image(registry, config):
    return config.get("image") or registry + "csi-attacher:v4.10.0{D}"
'''


class Images(unittest.TestCase):
    """CAT-39a: the references a tree pins by digest."""

    def test_generator_python(self):
        self.assertEqual(pinned_images({"kubevirt/csi.py": (False, GENERATOR.encode())}), [
            f"ghcr.io/kadet-hub/mirror/csi-driver:3a1a{D}",
            f"kindest/node:v1.37.0{D}",
            f"registry.k8s.io/sig-storage/csi-provisioner:v6.0.2{D}",
        ])  # csi-attacher is a fragment of an expression that does not evaluate: no image on Docker Hub

    def test_recipe_classes(self):
        files = {
            "init.yml": f"parameters:\n  kapitan:\n    dependencies:\n      - type: oci\n        source: ghcr.io/kadet-hub/kubernetes:1.9.0{D}\n",
            "controller.yml": f"image: quay.io/jetstack/cert-manager-controller:v1.21.2{D}\n"
                              f"args:\n  solver: --acme-http01-solver-image=quay.io/jetstack/cert-manager-acmesolver:v1.21.2{D}\n"
                              "env:\n  OPERATOR_IMAGE_NAME: ghcr.io/cloudnative-pg/cloudnative-pg:1.30.1\n",
            "db.yml": f'image: "postgres:18.6{D}"\n',
            "vendor/crd.yml": "description: (`<image>:<tag>@sha256:<digestValue>`)\n",
            "README.md": f"Source: `oci://quay.io/jetstack/charts/cert-manager:v1.21.2{D}`\n\nimage: docker.io/library/x:1{D}\n",
            "tests/values.yaml": f"image: quay.io/jetstack/cert-manager-webhook:v1.21.2{D}\n",
            "./tests/target.yml": f"image: docker.io/library/y:1{D}\n",
        }
        self.assertEqual(pinned_images({k: (False, v.encode()) for k, v in files.items()}), [
            f"postgres:18.6{D}",
            f"quay.io/jetstack/cert-manager-acmesolver:v1.21.2{D}",
            f"quay.io/jetstack/cert-manager-controller:v1.21.2{D}",
        ])

    def test_mirror_is_an_image(self):  # REC-6 names generators by one path segment; the mirror has two
        self.assertEqual(pinned_images({"a.yml": (False, f"x: ghcr.io/kadet-hub/mirror/csi-driver:3a1a{D}\n".encode())}),
                         [f"ghcr.io/kadet-hub/mirror/csi-driver:3a1a{D}"])

    def test_unparsable_python_pins_nothing(self):
        self.assertEqual(pinned_images({"a.py": (False, b"x = (\n"), "b.py": (False, b"\x00")}), [])


if __name__ == "__main__":
    unittest.main()
