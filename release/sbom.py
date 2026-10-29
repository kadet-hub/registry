"""SPDX 2.3 SBOM of a pushed generator artifact (PUB-8). Standard library only.

Usage: sbom.py --tar FILE --meta FILE --ref REF --digest DIGEST [--schemas FILE] --out FILE

One package for the generator with every file of the tar. Generators have
no dependencies (DEC-10), so the document is the reviewed file list. With
--schemas, the schemas.json that build.py wrote, each schema group is a
package of its own that holds the group's files.
"""

import argparse
import hashlib
import json
import re
import sys
import tarfile
from datetime import datetime, timezone


def verification_code(files):
    """SPDX 2.3 section 7.9: SHA-1 over the sorted, concatenated file SHA-1s."""
    return {"packageVerificationCodeValue": hashlib.sha1("".join(sorted(f["checksums"][0]["checksumValue"] for f in files)).encode()).hexdigest()}


def schema_key(rel, sources):
    """PUB-8: the sources.yaml entry of <group>/... below the schemas directory, looked up as QA-7 and QA-8 do."""
    group, _, name = rel.partition("/")
    head, _, version = name.removesuffix(".json").rpartition("_")
    specific = "terraform/" + head.replace("_", "/", 1) if group == "terraform" else f"{group}/{version}"
    return specific if "/" not in name and specific in sources else group


def schema_package(key, entry, files):
    """PUB-8: a schema group's package from its sources.yaml entry, NOASSERTION where the entry has no value."""
    e = entry if isinstance(entry, dict) else {}
    source = e.get("source") if isinstance(e.get("source"), str) else ""
    holders = e.get("copyright")
    if isinstance(holders, list):
        holders = "\n".join(map(str, holders))
    package = {
        "name": e["software"] if isinstance(e.get("software"), str) else key,
        "SPDXID": "SPDXRef-Package-" + hashlib.sha256(key.encode()).hexdigest()[:16],
        "downloadLocation": source if re.fullmatch(r"https?://\S+", source) else "NOASSERTION",
        "filesAnalyzed": True,
        "packageVerificationCode": verification_code(files),
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": e["license"] if isinstance(e.get("license"), str) else "NOASSERTION",
        "copyrightText": holders if isinstance(holders, str) else "NOASSERTION",
        "summary": f"Schemas of the sources.yaml entry {key}" if entry is not None else f"Schemas of {key} without a sources.yaml entry",
        "hasFiles": [f["SPDXID"] for f in files],
    }
    if isinstance(e.get("version"), (str, int, float)):
        package["versionInfo"] = str(e["version"])
    if source and package["downloadLocation"] == "NOASSERTION":
        package["sourceInfo"] = source  # several URLs
    return package


def sbom(tar, meta, ref, digest, now, schemas=None):
    files = []
    with tarfile.open(tar) as t:
        for m in sorted((m for m in t.getmembers() if m.isfile()), key=lambda m: m.name):
            data = t.extractfile(m).read()
            name = m.name.removeprefix("./")
            files.append({
                "fileName": f"./{name}",
                "SPDXID": "SPDXRef-File-" + hashlib.sha256(name.encode()).hexdigest()[:16],
                "checksums": [{"algorithm": "SHA1", "checksumValue": hashlib.sha1(data).hexdigest()},
                              {"algorithm": "SHA256", "checksumValue": hashlib.sha256(data).hexdigest()}],
                "licenseConcluded": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            })
    # PUB-8: the files below <schemas>/<group>/ go to the package of their sources.yaml entry.
    own, groups = [], {}
    sources = schemas["sources"] if schemas else {}
    for f in files:
        path = f["fileName"][2:]
        rel = path[len(schemas["dir"]) + 1:] if schemas and path.startswith(schemas["dir"] + "/") else ""
        if "/" in rel:
            groups.setdefault(schema_key(rel, sources), []).append(f)
        else:
            own.append(f)
    group_packages = [schema_package(k, sources.get(k), groups[k]) for k in sorted(groups)]
    name, version, src = meta["name"], meta["version"], meta["source"]
    registry, _, repo = ref.rpartition("/")
    path = "" if src["path"] == "." else f"#{src['path']}"
    package = {
        "name": name,
        "SPDXID": "SPDXRef-Package",
        "versionInfo": version,
        "downloadLocation": f"git+{src['repo']}@{src['sha']}{path}",
        "filesAnalyzed": True,
        "packageVerificationCode": verification_code(own),
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": meta["license"],
        "copyrightText": "NOASSERTION",
        "summary": meta["description"],
        "externalRefs": [{"referenceCategory": "PACKAGE-MANAGER", "referenceType": "purl",
                          "referenceLocator": f"pkg:oci/{repo}@{digest.replace(':', '%3A')}?repository_url={registry}/{repo}&tag={version}"}],
        "hasFiles": [f["SPDXID"] for f in own],
    }

    def contains(a, b):
        return {"spdxElementId": a, "relationshipType": "CONTAINS", "relatedSpdxElement": b}

    relationships = [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-Package"}]
    relationships += [contains("SPDXRef-Package", f) for f in package["hasFiles"]]
    for g in group_packages:
        # PUB-8: the artifact holds the vendored schemas and nothing runs them, so CONTAINS rather than DEPENDS_ON.
        relationships += [contains("SPDXRef-Package", g["SPDXID"])] + [contains(g["SPDXID"], f) for f in g["hasFiles"]]
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{ref}@{digest}",
        "documentNamespace": f"https://kadet-hub.org/spdx/{name}/{version}/{digest.removeprefix('sha256:')}",
        "creationInfo": {"created": now, "creators": ["Tool: kadet-hub release/sbom.py"]},
        "documentDescribes": ["SPDXRef-Package"],
        "packages": [package, *group_packages],
        "files": files,
        "relationships": relationships,
    }


def main():
    p = argparse.ArgumentParser()
    for arg in ("--tar", "--meta", "--ref", "--digest", "--out"):
        p.add_argument(arg, required=True)
    p.add_argument("--schemas")
    a = p.parse_args()
    with open(a.meta, encoding="utf-8") as f:
        meta = json.load(f)
    schemas = None
    if a.schemas:
        with open(a.schemas, encoding="utf-8") as f:
            schemas = json.load(f)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(sbom(a.tar, meta, a.ref, a.digest, now, schemas), f, sort_keys=True, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
