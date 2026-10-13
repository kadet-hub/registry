"""Create every built-in Kubernetes document and custom resource of the compiled output on a throwaway kube-apiserver with dryRun=All (QA-10, QA-11).

Usage: apiserver_check.py --out DIR [--schemas DIR]

Starts the image's etcd and kube-apiserver on loopback with their state in
a temporary directory. A kind is built in when the server serves it, in
any version, without any CRD. The CRDs in DIR/<group>/crds/ (QA-12) are
created first; documents of other kinds are skipped. Prints findings,
result lines and review lines; exits 1 on any finding.
"""

import argparse
import collections
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

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from schema_check import documents
from tag_check import files

# Admission that looks up objects the output may create itself: nothing of
# the output is persisted. Namespaces are created instead.
DISABLED = "ServiceAccount,Priority,RuntimeClass"
CRDS = "/apis/apiextensions.k8s.io/v1/customresourcedefinitions"


class Loader(getattr(yaml, "CSafeLoader", yaml.SafeLoader)):
    """QA-12: a plain = (YAML 1.1 value key, as in matcher enums) is a string, as in tools/upstream.py of kadet-hub/generators."""


Loader.add_constructor("tag:yaml.org,2002:value", Loader.construct_yaml_str)


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
        if self.conn is not None:
            self.conn.close()
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


def crd_files(schemas):
    """QA-12: (file, CRD) for every well-formed file under <group>/crds/, and the findings of the others."""
    try:
        with open(os.path.join(schemas, "sources.yaml"), encoding="utf-8") as f:
            sources = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        sources = None
    crds, findings = [], []
    for rel in files(schemas):
        parts = rel.split(os.sep)
        if len(parts) < 3 or parts[1] != "crds":
            continue
        try:
            with open(os.path.join(schemas, rel), encoding="utf-8") as f:
                docs = [json.load(f)] if rel.endswith(".json") else [d for d in yaml.load_all(f, Loader) if d is not None]
        except (OSError, UnicodeDecodeError, ValueError, yaml.YAMLError):
            docs = []
        crd = docs[0] if len(docs) == 1 and isinstance(docs[0], dict) else {}
        spec = crd.get("spec") if isinstance(crd.get("spec"), dict) else {}
        names = spec.get("names") if isinstance(spec.get("names"), dict) else {}
        if (crd.get("apiVersion"), crd.get("kind")) != ("apiextensions.k8s.io/v1", "CustomResourceDefinition"):
            findings.append(f"QA-12: {rel}: does not hold exactly one apiextensions.k8s.io/v1 CustomResourceDefinition")
        elif spec.get("group") != parts[0]:
            findings.append(f"QA-12: {rel}: CRD of group {spec.get('group')}, not {parts[0]}")
        elif len(parts) != 3 or parts[2] not in (f"{names.get('plural')}.yaml", f"{names.get('plural')}.json"):
            findings.append(f"QA-12: {rel}: not named {parts[0]}/crds/{names.get('plural')}.yaml or .json")
        elif not (isinstance(sources, dict) and isinstance(sources.get(parts[0]), dict)):
            findings.append(f"QA-12: {rel}: group {parts[0]} has no entry in sources.yaml")
        else:
            crds.append((rel, crd))
    return crds, findings


def install(server, crds, kinds, groups, version):
    """QA-12: create the CRDs with conversion None and wait up to 60 s; the served kinds, the established CRDs by (group, kind), and the findings."""
    findings, pending, established = [], {}, {}
    for rel, crd in crds:
        if crd["spec"]["group"] in groups:
            findings.append(f"QA-12: {rel}: group {crd['spec']['group']} is served by kube-apiserver {version}")
            continue
        crd["spec"]["conversion"] = {"strategy": "None"}
        status, body = server.request("POST", f"{CRDS}?fieldValidation=Strict", json.dumps(crd, default=str))
        if status >= 300:
            findings.append(f"QA-12: {rel}: {message(body)}")
        else:
            pending[json.loads(body)["metadata"]["name"]] = rel
    deadline = time.monotonic() + 60
    while pending:
        time.sleep(0.2)
        for name, rel in list(pending.items()):
            crd = server.get(f"{CRDS}/{name}")
            conditions = {c["type"]: c for c in (crd.get("status") or {}).get("conditions") or []}
            names, ready = conditions.get("NamesAccepted", {}), conditions.get("Established", {})
            if ready.get("status") == "True":
                established[(crd["spec"]["group"], crd["spec"]["names"]["kind"])] = crd
                del pending[name]
            elif names.get("status") == "False" or time.monotonic() > deadline:
                del pending[name]
                findings.append(f"QA-12: {rel}: not established within 60 s: {(names if names.get('status') == 'False' else ready).get('message', 'no condition')}")
    want = {f"{c['spec']['group']}/{v['name']}" for c in established.values() for v in c["spec"]["versions"] if v["served"]}
    while not want <= {gv for gv, _ in kinds} and time.monotonic() < deadline:
        time.sleep(0.2)
        try:
            kinds = served(server)[0]
        except OSError:  # /apis can list a group version before the server serves it
            pass
    return kinds, established, findings


def check(out, schemas=None):
    docs = [(rel, doc) for rel in files(out) if rel.endswith((".yml", ".yaml", ".json")) for doc in documents(os.path.join(out, rel))]
    crds, findings = crd_files(schemas) if schemas else ([], [])
    if not docs and not crds:
        return findings, []
    with tempfile.TemporaryDirectory() as tmp:
        server = Server(tmp)
        try:
            if not server.ready():
                with open(server.log, encoding="utf-8", errors="replace") as f:
                    tail = f.read().splitlines()[-10:]
                return ["QA-10: kube-apiserver did not become ready:", *tail], []
            version = server.get("/version")["gitVersion"]
            kinds, builtin = served(server)
            kinds, established, crd_findings = install(server, crds, kinds, {g for g, _ in builtin}, version)
            findings += crd_findings
            total, checked, skipped, namespaces = collections.Counter(), collections.Counter(), collections.Counter(), set()
            for rel, doc in docs:
                api_version, kind = doc["apiVersion"], doc["kind"]
                group = api_version.rpartition("/")[0]
                req = "QA-10" if (group, kind) in builtin else "QA-11"
                total[req] += 1
                meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
                what = f"{req}: {rel}: {kind} {meta.get('name') or meta.get('generateName') or '(no name)'}"
                if (api_version, kind) not in kinds:
                    if req == "QA-10":
                        findings.append(f"{what}: {api_version} {kind} is not served by kube-apiserver {version}")
                    elif (group, kind) in established:
                        findings.append(f"{what}: {api_version} {kind} is not served by CRD {established[(group, kind)]['metadata']['name']}")
                    else:
                        skipped[api_version] += 1
                    continue
                path, resource, namespaced = kinds[(api_version, kind)]
                if namespaced:
                    namespace = str(meta.get("namespace") or "default")
                    if namespace not in namespaces:
                        namespaces.add(namespace)
                        server.request("POST", "/api/v1/namespaces", json.dumps({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": namespace}}))
                    path += "/namespaces/" + urllib.parse.quote(namespace, safe="")
                status, body = server.request("POST", f"{path}/{resource}?dryRun=All&fieldValidation=Strict", json.dumps(doc, default=str))
                checked[req] += 1
                # 409: the throwaway server has the object (kube-system, cluster-admin); it passed validation.
                if status >= 300 and status != 409:
                    findings.append(f"{what}: {message(body)}")
        finally:
            server.stop()
    lines = [f"QA-10: validated against kube-apiserver {version}: {checked['QA-10']} built-in documents, {total['QA-11']} skipped"]
    if crds:
        lines.append(f"QA-11: validated against {len(established)} CRDs: {checked['QA-11']} custom resources, {sum(skipped.values())} skipped")
    lines += [f"review: QA-11: {v}: no CRD, {n} documents skipped" for v, n in sorted(skipped.items())]
    return sorted(set(findings)), lines


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--schemas")
    a = p.parse_args()
    findings, lines = check(a.out, a.schemas)
    if findings or lines:
        print("\n".join(findings + lines))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
