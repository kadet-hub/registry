"""Create every built-in Kubernetes document of the compiled output on a throwaway kube-apiserver with dryRun=All (QA-10).

Usage: apiserver_check.py --out DIR

Starts the image's etcd and kube-apiserver on loopback with their state in
a temporary directory. A kind is built in when the server serves it, in
any version, without any CRD; other documents are skipped. Prints findings
and a result line; exits 1 on any finding.
"""

import argparse
import http.client
import json
import os
import secrets
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.parse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema_check import documents
from tag_check import files

# Admission that looks up objects the output may create itself: nothing of
# the output is persisted. Namespaces are created instead.
DISABLED = "ServiceAccount,Priority,RuntimeClass"


class Server:
    def __init__(self, tmp):
        key = os.path.join(tmp, "sa.key")
        with open(key, "wb") as f:
            f.write(ec.generate_private_key(ec.SECP256R1()).private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
        self.token = secrets.token_hex(16)
        tokens = os.path.join(tmp, "tokens.csv")
        with open(tokens, "w", encoding="utf-8") as f:
            f.write(f"{self.token},gate,gate,system:masters\n")
        self.log = os.path.join(tmp, "server.log")
        with open(self.log, "wb") as log:
            self.procs = [
                subprocess.Popen(["etcd", "--data-dir", os.path.join(tmp, "etcd"), "--unsafe-no-fsync",
                                  "--listen-client-urls", "http://127.0.0.1:2379", "--advertise-client-urls", "http://127.0.0.1:2379",
                                  "--listen-peer-urls", "http://127.0.0.1:2380"], stdout=log, stderr=log),
                subprocess.Popen(["kube-apiserver", "--etcd-servers", "http://127.0.0.1:2379",
                                  "--bind-address", "127.0.0.1", "--advertise-address", "127.0.0.1", "--endpoint-reconciler-type", "none", "--secure-port", "6443",
                                  "--cert-dir", tmp, "--token-auth-file", tokens, "--authorization-mode", "AlwaysAllow", "--allow-privileged",
                                  "--service-account-issuer", "https://kubernetes.default.svc",
                                  "--service-account-key-file", key, "--service-account-signing-key-file", key,
                                  "--service-cluster-ip-range", "10.96.0.0/12,fd00:10:96::/108",
                                  "--disable-admission-plugins", DISABLED], stdout=log, stderr=log),
            ]
        self.cert = os.path.join(tmp, "apiserver.crt")
        self.conn = None

    def request(self, method, path, body=None):
        if self.conn is None:
            self.conn = http.client.HTTPSConnection("127.0.0.1", 6443, timeout=30, context=ssl.create_default_context(cafile=self.cert))
        try:
            self.conn.request(method, path, body, {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
            r = self.conn.getresponse()
            return r.status, r.read()
        except (OSError, http.client.HTTPException):
            self.conn.close()
            self.conn = None
            raise

    def ready(self, seconds=90):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if any(p.poll() is not None for p in self.procs):
                return False
            try:
                if os.path.exists(self.cert) and self.request("GET", "/readyz")[0] == 200:
                    return True
            except (OSError, http.client.HTTPException):
                pass
            time.sleep(0.5)
        return False

    def get(self, path):
        status, body = self.request("GET", path)
        if status != 200:
            raise OSError(f"GET {path}: {status}")
        return json.loads(body)

    def stop(self):
        for p in self.procs:
            p.kill()
            p.wait()


def served(server):
    """(apiVersion, kind) -> (group version path, resource, namespaced), and the (group, kind) pairs served in any version."""
    kinds, paths = {}, {"v1": "/api/v1"}
    for g in server.get("/apis")["groups"]:
        for v in g["versions"]:
            paths[v["groupVersion"]] = f"/apis/{v['groupVersion']}"
    for gv, path in paths.items():
        for r in server.get(path)["resources"]:
            if "/" not in r["name"]:
                kinds[(gv, r["kind"])] = (path, r["name"], r["namespaced"])
    return kinds, {(gv.rpartition("/")[0], kind) for gv, kind in kinds}


def message(body):
    try:
        return str(json.loads(body)["message"])[:1000]
    except (ValueError, KeyError, TypeError):
        return body.decode("utf-8", "replace")[:200]


def check(out):
    docs = [(rel, doc) for rel in files(out) if rel.endswith((".yml", ".yaml", ".json")) for doc in documents(os.path.join(out, rel))]
    if not docs:
        return [], []
    with tempfile.TemporaryDirectory() as tmp:
        server = Server(tmp)
        try:
            if not server.ready():
                with open(server.log, encoding="utf-8", errors="replace") as f:
                    tail = f.read().splitlines()[-10:]
                return ["QA-10: kube-apiserver did not become ready:", *tail], []
            version = server.get("/version")["gitVersion"]
            kinds, builtin = served(server)
            findings, checked, skipped, namespaces = [], 0, 0, set()
            for rel, doc in docs:
                api_version, kind = doc["apiVersion"], doc["kind"]
                meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
                what = f"QA-10: {rel}: {kind} {meta.get('name') or meta.get('generateName') or '(no name)'}"
                if (api_version, kind) not in kinds:
                    if (api_version.rpartition("/")[0], kind) in builtin:
                        findings.append(f"{what}: {api_version} {kind} is not served by kube-apiserver {version}")
                    else:
                        skipped += 1
                    continue
                path, resource, namespaced = kinds[(api_version, kind)]
                if namespaced:
                    namespace = str(meta.get("namespace") or "default")
                    if namespace not in namespaces:
                        namespaces.add(namespace)
                        server.request("POST", "/api/v1/namespaces", json.dumps({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": namespace}}))
                    path += "/namespaces/" + urllib.parse.quote(namespace, safe="")
                status, body = server.request("POST", f"{path}/{resource}?dryRun=All&fieldValidation=Strict", json.dumps(doc, default=str))
                checked += 1
                # 409: the throwaway server has the object (kube-system, cluster-admin); it passed validation.
                if status >= 300 and status != 409:
                    findings.append(f"{what}: {message(body)}")
        finally:
            server.stop()
    return sorted(set(findings)), [f"QA-10: validated against kube-apiserver {version}: {checked} built-in documents, {skipped} skipped"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    a = p.parse_args()
    findings, lines = check(a.out)
    if findings or lines:
        print("\n".join(findings + lines))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
