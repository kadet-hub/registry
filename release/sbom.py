"""SPDX 2.3 SBOM of a pushed generator artifact (PUB-8). Standard library only.

Usage: sbom.py --tar FILE --meta FILE --ref REF --digest DIGEST --out FILE

One package for the generator with every file of the tar. Generators have
no dependencies (DEC-10), so the document is the reviewed file list.
"""

import argparse
import hashlib
import json
import sys
import tarfile
from datetime import datetime, timezone


def sbom(tar, meta, ref, digest, now):
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
    # SPDX 2.3 section 7.9: SHA-1 over the sorted, concatenated file SHA-1s.
    code = hashlib.sha1("".join(sorted(f["checksums"][0]["checksumValue"] for f in files)).encode()).hexdigest()
    name, version, src = meta["name"], meta["version"], meta["source"]
    registry, _, repo = ref.rpartition("/")
    path = "" if src["path"] == "." else f"#{src['path']}"
    package = {
        "name": name,
        "SPDXID": "SPDXRef-Package",
        "versionInfo": version,
        "downloadLocation": f"git+{src['repo']}@{src['sha']}{path}",
        "filesAnalyzed": True,
        "packageVerificationCode": {"packageVerificationCodeValue": code},
        "licenseConcluded": "NOASSERTION",
        "licenseDeclared": meta["license"],
        "copyrightText": "NOASSERTION",
        "summary": meta["description"],
        "externalRefs": [{"referenceCategory": "PACKAGE-MANAGER", "referenceType": "purl",
                          "referenceLocator": f"pkg:oci/{repo}@{digest.replace(':', '%3A')}?repository_url={registry}/{repo}&tag={version}"}],
        "hasFiles": [f["SPDXID"] for f in files],
    }
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{ref}@{digest}",
        "documentNamespace": f"https://kadet-hub.org/spdx/{name}/{version}/{digest.removeprefix('sha256:')}",
        "creationInfo": {"created": now, "creators": ["Tool: kadet-hub release/sbom.py"]},
        "documentDescribes": ["SPDXRef-Package"],
        "packages": [package],
        "files": files,
        "relationships": [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-Package"}]
        + [{"spdxElementId": "SPDXRef-Package", "relationshipType": "CONTAINS", "relatedSpdxElement": f["SPDXID"]} for f in files],
    }


def main():
    p = argparse.ArgumentParser()
    for arg in ("--tar", "--meta", "--ref", "--digest", "--out"):
        p.add_argument(arg, required=True)
    a = p.parse_args()
    with open(a.meta, encoding="utf-8") as f:
        meta = json.load(f)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(sbom(a.tar, meta, a.ref, a.digest, now), f, sort_keys=True, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
