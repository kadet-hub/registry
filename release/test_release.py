import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from index import build, notes
from sbom import sbom
from tree import read_dir, read_tar, tree_id, write_tar

GIT_ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "PATH": os.environ["PATH"]}


def git_tree(path):
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"]):
        subprocess.run(cmd, cwd=path, check=True, env=GIT_ENV)
    return subprocess.run(["git", "write-tree"], cwd=path, check=True, env=GIT_ENV,
                          capture_output=True, text=True).stdout.strip()


def make_tree(path, executable=False):
    files = {"kapitan-generator.yaml": "name: x\n", "lib/b.py": "b = 1\n", "lib-a.py": "a\n", "lib/sub/c.j2": "{{ x }}\n"}
    for rel, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(path, rel)), exist_ok=True)
        with open(os.path.join(path, rel), "w") as f:
            f.write(text)
    if executable:
        os.chmod(os.path.join(path, "lib/b.py"), 0o755)


class Tree(unittest.TestCase):
    def test_tar_is_reproducible_and_matches_git(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src")
            make_tree(src)
            files = read_dir(src)
            write_tar(files, os.path.join(d, "a.tar"))
            write_tar(dict(reversed(list(files.items()))), os.path.join(d, "b.tar"))
            with open(os.path.join(d, "a.tar"), "rb") as a, open(os.path.join(d, "b.tar"), "rb") as b:
                self.assertEqual(a.read(), b.read())
            expected = git_tree(src)
            self.assertEqual(tree_id(files), expected)
            self.assertEqual(tree_id(read_tar(os.path.join(d, "a.tar"))), expected)

    def test_executable_source_fails_the_tree_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "src")
            make_tree(src, executable=True)
            write_tar(read_dir(src), os.path.join(d, "a.tar"))
            self.assertNotEqual(tree_id(read_tar(os.path.join(d, "a.tar"))), git_tree(src))


NOW, LATER = "2026-10-09T00:00:00Z", "2026-10-10T00:00:00Z"


def version(name, v, digest="sha256:" + "a" * 64):
    return {"digest": digest, "meta": {"name": name, "version": v, "tree": "t", "license": "MIT"}}


class Index(unittest.TestCase):
    def test_yanked_and_removed(self):
        index = build([version("gen", "1.0.0"), version("gen", "1.1.0"), version("old", "0.1.0")],
                      {"gen": {"yanked": {"1.0.0": "broken"}}}, None, NOW)
        gens = index["generators"]
        self.assertEqual(index["serial"], 1)
        self.assertEqual(gens["gen"]["1.0.0"]["yanked"], "broken")
        self.assertIsNone(gens["gen"]["1.1.0"]["yanked"])
        self.assertEqual(gens["old"]["0.1.0"]["yanked"], "entry removed")
        self.assertEqual(gens["gen"]["1.1.0"]["digest"], "sha256:" + "a" * 64)
        self.assertEqual(gens["gen"]["1.1.0"]["advisories"], [])

    def test_serial_increases_only_on_change(self):
        entries = {"gen": {}}
        first = build([version("gen", "1.0.0")], entries, None, NOW)
        self.assertIsNone(build([version("gen", "1.0.0")], entries, first, LATER))
        second = build([version("gen", "1.0.0")], {"gen": {"yanked": {"1.0.0": "x"}}}, first, LATER)
        self.assertEqual(second["serial"], 2)

    def test_published_is_kept_from_the_previous_index(self):
        first = build([version("gen", "1.0.0")], {"gen": {}}, None, NOW)
        second = build([version("gen", "1.0.0"), version("gen", "1.1.0")], {"gen": {}}, first, LATER)
        self.assertEqual(second["generators"]["gen"]["1.0.0"]["published"], NOW)
        self.assertEqual(second["generators"]["gen"]["1.1.0"]["published"], LATER)

    def test_deleted_yanked_version_stays_with_its_advisory(self):
        entries = {"gen": {"yanked": {"1.0.0": "malicious"}, "advisories": {"1.0.0": ["GHSA-2345-6789-cfgh"]}}}
        first = build([version("gen", "1.0.0"), version("gen", "1.1.0")], entries, None, NOW)
        self.assertEqual(first["generators"]["gen"]["1.0.0"]["advisories"], ["GHSA-2345-6789-cfgh"])
        second = build([version("gen", "1.1.0")], entries, first, LATER)
        self.assertIsNone(second)
        kept = build([version("gen", "1.1.0")], {"gen": {"yanked": {"1.0.0": "malicious, see advisory"},
                                                         "advisories": entries["gen"]["advisories"]}}, first, LATER)
        record = kept["generators"]["gen"]["1.0.0"]
        self.assertEqual((record["digest"], record["yanked"], record["advisories"], record["published"]),
                         ("sha256:" + "a" * 64, "malicious, see advisory", ["GHSA-2345-6789-cfgh"], NOW))

    def test_deleted_version_that_is_not_yanked_is_dropped(self):
        first = build([version("gen", "1.0.0")], {"gen": {}}, None, NOW)
        self.assertEqual(build([], {"gen": {}}, first, LATER)["generators"], {})

    def test_release_notes(self):
        first = build([version("gen", "1.0.0")], {"gen": {}}, None, NOW)
        self.assertEqual(notes(None, first), "Index serial 1.\n\nAdded:\n\n- gen 1.0.0\n")
        second = build([version("gen", "1.0.0"), version("gen", "1.1.0")], {"gen": {"yanked": {"1.0.0": "broken"}}},
                       first, LATER)
        self.assertEqual(notes(first, second), "Index serial 2, changes since serial 1.\n\nAdded:\n\n- gen 1.1.0"
                                               "\n\nYanked:\n\n- gen 1.0.0: broken\n")
        third = build([version("gen", "1.0.0"), version("gen", "1.1.0")],
                      {"gen": {"yanked": {"1.0.0": "broken"}, "advisories": {"1.0.0": ["GHSA-2345-6789-cfgh"]}}},
                      second, LATER)
        self.assertEqual(notes(second, third), "Index serial 3, changes since serial 2.\n\nNo version added or yanked.\n")
        fourth = build([version("gen", "1.0.0"), version("gen", "1.1.0")], {"gen": {}}, third, LATER,
                       [version("gen", "2.0.0"), version("gen", "2.1.0")], {"gen": {"yanked": {"2.0.0": "broken"}}})
        self.assertEqual(notes(third, fourth), "Index serial 4, changes since serial 3.\n\nAdded:\n\n- recipe gen 2.0.0"
                                               "\n- recipe gen 2.1.0\n\nYanked:\n\n- recipe gen 2.0.0: broken\n")

    def test_recipes(self):  # REC-13
        gens, entries = [version("gen", "1.0.0"), version("old", "0.1.0")], {"gen": {"yanked": {"1.0.0": "broken"}}}
        first = build(gens, entries, None, NOW)
        self.assertEqual(first["recipes"], {})
        # An index from before REC-13, without the key, equals one without recipes.
        before = {k: v for k, v in first.items() if k != "recipes"}
        self.assertIsNone(build(gens, entries, before, LATER))
        # Recipes in a section of their own: a recipe of a generator's name has its own entry, yank and records.
        recipes = [version("gen", "1.0.0", "sha256:" + "c" * 64), version("gen", "1.1.0"), version("gone", "1.0.0")]
        second = build(gens, entries, before, LATER, recipes, {"gen": {"yanked": {"1.1.0": "pins a broken generator"},
                                                                       "advisories": {"1.1.0": ["GHSA-2345-6789-cfgh"]}}})
        self.assertEqual(second["serial"], 2)
        self.assertEqual(json.dumps(second["generators"], sort_keys=True, indent=1), json.dumps(first["generators"], sort_keys=True, indent=1))
        self.assertEqual(second["recipes"]["gen"]["1.0.0"], {"tree": "t", "license": "MIT", "digest": "sha256:" + "c" * 64,
                                                             "yanked": None, "advisories": [], "published": LATER})
        self.assertEqual((second["recipes"]["gen"]["1.1.0"]["yanked"], second["recipes"]["gen"]["1.1.0"]["advisories"]),
                         ("pins a broken generator", ["GHSA-2345-6789-cfgh"]))
        self.assertEqual(second["recipes"]["gone"]["1.0.0"]["yanked"], "entry removed")
        # published is kept, and a deleted yanked recipe version stays listed, as does a removed recipe's (INC-1).
        third = build(gens, entries, second, "2026-10-11T00:00:00Z", recipes[:1], {"gen": {"yanked": {"1.1.0": "deleted"}}})
        self.assertEqual(third["recipes"]["gen"]["1.0.0"]["published"], LATER)
        self.assertEqual(third["recipes"]["gen"]["1.1.0"]["yanked"], "deleted")
        self.assertEqual(third["recipes"]["gone"]["1.0.0"]["yanked"], "entry removed")


if __name__ == "__main__":
    unittest.main()


class Sbom(unittest.TestCase):
    def test_document_lists_every_file_with_checksums(self):
        meta = {"name": "demo", "version": "1.2.0", "license": "Apache-2.0", "description": "Demo",
                "source": {"repo": "https://github.com/example/demo.git", "path": "gen", "sha": "c" * 40}}
        with tempfile.TemporaryDirectory() as tmp:
            make_tree(os.path.join(tmp, "src"))
            tar = os.path.join(tmp, "demo.tar")
            write_tar(read_dir(os.path.join(tmp, "src")), tar)
            doc = sbom(tar, meta, "ghcr.io/kadet-hub/demo", "sha256:" + "a" * 64, "2026-10-11T00:00:00Z")
        self.assertEqual((doc["spdxVersion"], doc["SPDXID"], doc["dataLicense"]), ("SPDX-2.3", "SPDXRef-DOCUMENT", "CC0-1.0"))
        pkg = doc["packages"][0]
        self.assertEqual((pkg["name"], pkg["versionInfo"], pkg["licenseDeclared"]), ("demo", "1.2.0", "Apache-2.0"))
        self.assertEqual(pkg["downloadLocation"], f"git+https://github.com/example/demo.git@{'c' * 40}#gen")
        self.assertEqual(pkg["externalRefs"][0]["referenceLocator"],
                         f"pkg:oci/demo@sha256%3A{'a' * 64}?repository_url=ghcr.io/kadet-hub/demo&tag=1.2.0")
        names = sorted(f["fileName"] for f in doc["files"])
        self.assertEqual(names, ["./kapitan-generator.yaml", "./lib-a.py", "./lib/b.py", "./lib/sub/c.j2"])
        b = next(f for f in doc["files"] if f["fileName"] == "./lib/b.py")
        self.assertIn({"algorithm": "SHA256", "checksumValue": hashlib.sha256(b"b = 1\n").hexdigest()}, b["checksums"])
        sha1s = sorted(c["checksumValue"] for f in doc["files"] for c in f["checksums"] if c["algorithm"] == "SHA1")
        self.assertEqual(pkg["packageVerificationCode"]["packageVerificationCodeValue"], hashlib.sha1("".join(sha1s).encode()).hexdigest())
        self.assertEqual(len({f["SPDXID"] for f in doc["files"]}), 4)
        self.assertEqual(len(doc["relationships"]), 5)
        json.dumps(doc)

    def test_schema_groups(self):  # PUB-8
        meta = {"name": "demo", "version": "1.2.0", "license": "Apache-2.0", "description": "Demo",
                "source": {"repo": "https://github.com/example/demo.git", "path": "gen", "sha": "c" * 40}}
        files = ["kapitan-generator.yaml", "schemas/sources.yaml", "schemas/core/secret_v1.json", "schemas/core/NOTICE",
                 "schemas/core/hostnameconfig_v1alpha1.json", "schemas/kyverno.io/policy_v1.json", "schemas/kyverno.io/crds/policies.yaml",
                 "schemas/terraform/hashicorp_aws_6.69.1.json", "schemas/example.org/thing_v1.json", "schemasx/core/a_v1.json"]
        sources = {
            "core": {"software": "Kubernetes", "version": "1.37.1", "license": "Apache-2.0",
                     "source": "https://github.com/yannh/kubernetes-json-schema/tree/abc/v1.37.1-standalone-strict"},
            "core/v1alpha1": {"software": "Talos", "version": "1.14.3", "license": "MPL-2.0", "copyright": "Sidero Labs",
                              "source": "https://github.com/siderolabs/talos/blob/v1.14.3/config.schema.json"},
            "kyverno.io": {"software": "Kyverno", "version": "1.19.1", "license": "Apache-2.0",
                           "source": "https://example.org/a https://example.org/b", "copyright": ["Copyright 2020 A", "Copyright 2021 B"]},
            "terraform/hashicorp/aws": {"software": "hashicorp/aws", "version": "6.69.1",
                                        "source": "https://registry.terraform.io/providers/hashicorp/aws/6.69.1"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            tar = os.path.join(tmp, "demo.tar")
            write_tar({f: (False, f.encode()) for f in files}, tar)
            doc = sbom(tar, meta, "ghcr.io/kadet-hub/demo", "sha256:" + "a" * 64, NOW, {"dir": "schemas", "sources": sources})
        ids = {f["SPDXID"]: f["fileName"][2:] for f in doc["files"]}
        self.assertEqual(sorted(ids.values()), sorted(files))  # every file stays listed (CAT-29)
        pkgs = {p["SPDXID"]: p for p in doc["packages"]}
        generator = pkgs.pop("SPDXRef-Package")
        self.assertEqual(sorted(ids[i] for i in generator["hasFiles"]),
                         ["kapitan-generator.yaml", "schemas/sources.yaml", "schemasx/core/a_v1.json"])
        groups = {p["summary"]: (p, sorted(ids[i] for i in p["hasFiles"])) for p in pkgs.values()}
        self.assertEqual({k: v[1] for k, v in groups.items()}, {
            "Schemas of the sources.yaml entry core": ["schemas/core/NOTICE", "schemas/core/secret_v1.json"],
            "Schemas of the sources.yaml entry core/v1alpha1": ["schemas/core/hostnameconfig_v1alpha1.json"],
            "Schemas of the sources.yaml entry kyverno.io": ["schemas/kyverno.io/crds/policies.yaml", "schemas/kyverno.io/policy_v1.json"],
            "Schemas of the sources.yaml entry terraform/hashicorp/aws": ["schemas/terraform/hashicorp_aws_6.69.1.json"],
            "Schemas of example.org without a sources.yaml entry": ["schemas/example.org/thing_v1.json"]})
        fields = ("name", "versionInfo", "downloadLocation", "licenseDeclared", "copyrightText", "sourceInfo")
        got = {k: tuple(v[0].get(f) for f in fields) for k, v in groups.items()}
        self.assertEqual(got["Schemas of the sources.yaml entry core/v1alpha1"],
                         ("Talos", "1.14.3", sources["core/v1alpha1"]["source"], "MPL-2.0", "Sidero Labs", None))
        # Two URLs are no download location; the copyright list is one line per holder.
        self.assertEqual(got["Schemas of the sources.yaml entry kyverno.io"],
                         ("Kyverno", "1.19.1", "NOASSERTION", "Apache-2.0", "Copyright 2020 A\nCopyright 2021 B", sources["kyverno.io"]["source"]))
        self.assertEqual(got["Schemas of the sources.yaml entry terraform/hashicorp/aws"][3:5], ("NOASSERTION", "NOASSERTION"))
        self.assertEqual(got["Schemas of example.org without a sources.yaml entry"],
                         ("example.org", None, "NOASSERTION", "NOASSERTION", "NOASSERTION", None))
        rel = {(r["spdxElementId"], r["relationshipType"], r["relatedSpdxElement"]) for r in doc["relationships"]}
        for p in pkgs.values():
            self.assertIn(("SPDXRef-Package", "CONTAINS", p["SPDXID"]), rel)
            self.assertTrue({("SPDXRef-Package", "CONTAINS", i) for i in p["hasFiles"]}.isdisjoint(rel))
            self.assertTrue({(p["SPDXID"], "CONTAINS", i) for i in p["hasFiles"]} <= rel)
            sha1s = sorted(c["checksumValue"] for f in doc["files"] if f["SPDXID"] in p["hasFiles"] for c in f["checksums"] if c["algorithm"] == "SHA1")
            self.assertEqual(p["packageVerificationCode"]["packageVerificationCodeValue"], hashlib.sha1("".join(sha1s).encode()).hexdigest())
        # Without sources.yaml every group is NOASSERTION, named after its directory.
        with tempfile.TemporaryDirectory() as tmp:
            tar = os.path.join(tmp, "demo.tar")
            write_tar({f: (False, f.encode()) for f in files}, tar)
            doc = sbom(tar, meta, "ghcr.io/kadet-hub/demo", "sha256:" + "a" * 64, NOW, {"dir": "schemas", "sources": {}})
        self.assertEqual(sorted((p["name"], p["licenseDeclared"]) for p in doc["packages"][1:]),
                         [(g, "NOASSERTION") for g in ("core", "example.org", "kyverno.io", "terraform")])


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
REPO = "https://github.com/example/demo.git"
# Fakes for release/output-diff and release/sign: the registry, git, and the
# fetch and compile steps the gate's own tests cover.
FAKES = {
    "bin/oras": """#!/usr/bin/env bash
case "$1 $2" in
  "manifest fetch") [[ -n ${FAKE_INDEX:-} ]] || { echo "$4: not found" >&2; exit 1; }; echo '{"layers": [{"digest": "sha256:1"}]}' ;;
  "blob fetch") cp -- "$FAKE_INDEX" "$4" ;;
  "blob push") ;;
  "manifest push") [[ -z ${FAKE_PUSHED:-} ]] || cp -- "${@: -1}" "$FAKE_PUSHED" ;;
  *) echo "$*: not found" >&2; exit 1 ;;
esac
""",
    "bin/git": "#!/usr/bin/env bash\nfor a; do if [[ $a == rev-parse ]]; then echo \"$FAKE_TREE\"; elif [[ $a == ls-tree ]]; then printf '100644 blob x\\tLICENSE\\n'; fi; done\n",
    "root/gate/fetch_tree.py": """import os, sys
a = dict(zip(sys.argv[1::2], sys.argv[2::2]))
if a["--rev"] == "unreachable":
    sys.exit(1)
os.makedirs(a["--out"])
with open(os.path.join(a["--out"], "rev"), "w") as f:
    f.write(a["--rev"])
""",
    "root/gate/fetch-charts": "#!/usr/bin/env bash\nmkdir -p -- \"$2\"\n",
    "root/sandbox/gate-compile": """#!/usr/bin/env bash
rev=$(cat -- "$1/rev")
[[ $COMPILE_ONLY == 1 && $rev != broken ]] || exit 1
mkdir -p -- "$OUTPUT_DIR/compiled/t"
printf 'rev: %s\\nport: 80\\n' "$rev" >"$OUTPUT_DIR/compiled/t/svc.yml"
""",
    "root/generators/demo.yaml": f"source:\n  repo: {REPO}\n  path: .\n  tag: v1.13.0\n  sha: {'c' * 40}\nyanked:\n  1.12.0: broken\n",
    # A recipe of the generator's name (DEC-19). Its checks compile the rev; broken writes no output, failing fails after it.
    "root/recipes/demo.yaml": f"source:\n  repo: {REPO}\n  path: demo\n  tag: demo-v1.0.0\n  sha: {'d' * 40}\nyanked:\n  0.3.0: broken\n",
    "root/gate/recipe-checks": """#!/usr/bin/env bash
echo "recipe-checks $2 GH_TOKEN=${GH_TOKEN:-unset}" >>"${FAKE_LOG:-/dev/null}"
mkdir -- "$4" "$4/static" "$4/proof"
[[ $2 != broken ]] || exit 1
mkdir -p -- "$4/proof/out/compiled/$3"
printf 'rev: %s\\nport: 80\\n' "$2" >"$4/proof/out/compiled/$3/svc.yml"
if [[ -n ${FAKE_RECIPE_JSON:-} ]]; then cp -- "$FAKE_RECIPE_JSON" "$4/static/recipe.json"; fi
printf '%s' "${FAKE_SEC12:-}"
[[ $2 != failing ]]
""",
}


def listed(sha, yanked=None):
    return {"yanked": yanked, "source": {"repo": REPO, "path": ".", "tag": "v", "sha": sha}}


class OutputDiff(unittest.TestCase):
    """PUB-9: release/output-diff and release/sign with fake tools."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.root = os.path.join(self.tmp, "root")
        shutil.copytree(os.path.join(ROOT, "release"), os.path.join(self.root, "release"))
        os.makedirs(os.path.join(self.root, "gate"))
        shutil.copy(os.path.join(ROOT, "gate", "output_diff.py"), os.path.join(self.root, "gate"))
        for rel, text in FAKES.items():
            path = os.path.join(self.tmp, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            os.chmod(path, 0o755)
        self.env = dict(os.environ, PATH=os.path.join(self.tmp, "bin") + os.pathsep + os.environ["PATH"],
                        REGISTRY="ghcr.io/kadet-hub", IDENTITY="x", GITHUB_REPOSITORY="kadet-hub/registry", GH_TOKEN="x")

    def output_diff(self, versions):
        run = tempfile.mkdtemp(dir=self.tmp)
        env = dict(self.env)
        if versions is not None:
            env["FAKE_INDEX"] = os.path.join(run, "index.json")
            with open(env["FAKE_INDEX"], "w", encoding="utf-8") as f:
                json.dump({"serial": 1, "generators": {"demo": versions}}, f)
        os.makedirs(os.path.join(run, "new", "compiled", "t"))
        with open(os.path.join(run, "new", "compiled", "t", "svc.yml"), "w", encoding="utf-8") as f:
            f.write("port: 8080\n")
        open(os.path.join(run, "compile.txt"), "w").close()
        p = subprocess.run([os.path.join(self.root, "release", "output-diff"), "demo", os.path.join(run, "new"),
                            os.path.join(run, "compile.txt"), run], env=env, capture_output=True, text=True, check=True)
        diff = os.path.join(run, "output.diff")
        if not os.path.exists(diff):
            return json.loads(p.stdout), None
        with open(diff, "rb") as f:
            return json.loads(p.stdout), f.read()

    def test_diff_against_the_newest_listed_version(self):
        # 1.12.0 is yanked on main, 1.11.0 in the index; 1.10.0 sorts above 1.9.0.
        record, diff = self.output_diff({"1.9.0": listed("s9"), "1.10.0": listed("s10"),
                                         "1.11.0": listed("s11", "broken"), "1.12.0": listed("s12")})
        self.assertEqual(record, {"base": "1.10.0", "files": 1, "hunks": 1, "sha256": hashlib.sha256(diff).hexdigest()})
        self.assertIn(b"-rev: s10\n-port: 80\n+port: 8080\n", diff)

    def test_missing_base_and_failures_are_recorded(self):
        none = {"base": None, "error": "no earlier listed version"}
        self.assertEqual(self.output_diff(None), (none, None))  # no index yet
        self.assertEqual(self.output_diff({"1.0.0": listed("s1", "broken")}), (none, None))
        self.assertEqual(self.output_diff({"1.0.0": listed("unreachable")}), ({"base": "1.0.0", "error": "base not fetched"}, None))
        self.assertEqual(self.output_diff({"1.0.0": listed("broken")}), ({"base": "1.0.0", "error": "base did not compile"}, None))

    def test_recipe_base(self):  # PUB-9 for a recipe (REC-12)
        def run(recipes):
            out = tempfile.mkdtemp(dir=self.tmp)
            index = os.path.join(out, "index.json")
            with open(index, "w", encoding="utf-8") as f:
                json.dump({"serial": 1, "generators": {"demo": {"9.0.0": listed("gen")}}, "recipes": {"demo": recipes}}, f)
            os.makedirs(os.path.join(out, "new", "compiled", "demo"))
            with open(os.path.join(out, "new", "compiled", "demo", "svc.yml"), "w", encoding="utf-8") as f:
                f.write("port: 8080\n")
            open(os.path.join(out, "compile.txt"), "w").close()
            p = subprocess.run([os.path.join(self.root, "release", "output-diff"), "recipes/demo", os.path.join(out, "new"),
                                os.path.join(out, "compile.txt"), out], env=dict(self.env, FAKE_INDEX=index),
                               capture_output=True, text=True, check=True)
            if not os.path.exists(os.path.join(out, "output.diff")):
                return json.loads(p.stdout), None
            with open(os.path.join(out, "output.diff"), "rb") as f:
                return json.loads(p.stdout), f.read()
        # The newest listed recipe version that neither the index nor the entry yanks, not the generator's.
        record, diff = run({"0.1.0": listed("r1"), "0.2.0": listed("r2"), "0.3.0": listed("r3"), "0.4.0": listed("r4", "broken")})
        self.assertEqual(record, {"base": "0.2.0", "files": 1, "hunks": 1, "sha256": hashlib.sha256(diff).hexdigest()})
        self.assertIn(b"-rev: r2\n-port: 80\n+port: 8080\n", diff)
        # A base whose checks fail after its compile is compared (REC-10); one without output is not.
        self.assertEqual(run({"0.1.0": listed("failing")})[0]["base"], "0.1.0")
        self.assertEqual(run({"0.1.0": listed("failing")})[0].get("error"), None)
        self.assertEqual(run({"0.1.0": listed("broken")}), ({"base": "0.1.0", "error": "base did not compile"}, None))
        self.assertEqual(run({}), ({"base": None, "error": "no earlier listed version"}, None))

    def sign(self, record, diff):
        built = os.path.join(self.tmp, "built")
        shutil.rmtree(built, ignore_errors=True)
        make_tree(os.path.join(built, "src"))
        files = read_dir(os.path.join(built, "src"))
        write_tar(files, os.path.join(built, "demo.tar"))
        meta = {"name": "demo", "version": "1.13.0", "tree": tree_id(files), "license": "MIT", "description": "Demo",
                "source": {"repo": REPO, "path": ".", "tag": "v1.13.0", "sha": "c" * 40}, "output_diff": record}
        with open(os.path.join(built, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f)
        if diff is not None:
            with open(os.path.join(built, "output.diff"), "w", encoding="utf-8") as f:
                f.write(diff)
        outputs = os.path.join(self.tmp, "outputs")
        open(outputs, "w").close()
        subprocess.run([os.path.join(self.root, "release", "sign"), "demo", built], check=True, capture_output=True,
                       env=dict(self.env, FAKE_TREE=tree_id(files), GITHUB_OUTPUT=outputs))
        with open(outputs, encoding="utf-8") as f:
            return dict(line.rstrip("\n").split("=", 1) for line in f)

    def test_sign_attests_the_diff_with_its_record(self):
        record = {"base": "1.10.0", "files": 1, "hunks": 1, "sha256": "a" * 64}
        outputs = self.sign(record, "-port: 80\n+port: 8080\n<script>\n")
        self.assertEqual(outputs["publish"], "true")
        with open(outputs["diff"], encoding="utf-8") as f:
            self.assertEqual(json.load(f), dict(record, diff="-port: 80\n+port: 8080\n<script>\n"))
        outputs = self.sign({"base": None, "error": "no earlier listed version"}, None)
        self.assertEqual(outputs["publish"], "true")
        self.assertNotIn("diff", outputs)
        with open(os.path.join(ROOT, ".github", "workflows", "release.yml"), encoding="utf-8") as f:
            workflow = f.read()
        start = workflow.index("- name: Attest the output diff")
        step = workflow[start:workflow.index("- name: Tag", start)]
        for line in ("if: steps.push.outputs.publish == 'true' && steps.push.outputs.diff != ''",
                     "subject-digest: ${{ steps.push.outputs.digest }}",
                     "predicate-type: https://kadet-hub.org/output-diff/v1",
                     "predicate-path: ${{ steps.push.outputs.diff }}"):
            self.assertIn(line, step)

    def test_oci_attestations_are_pushed_to_the_registry(self):  # PUB-3a
        with open(os.path.join(ROOT, ".github", "workflows", "release.yml"), encoding="utf-8") as f:
            steps = f.read().split("uses: actions/attest@")[1:]
        oci = [s.split("\n      - ", 1)[0] for s in steps if "subject-digest:" in s.split("\n      - ", 1)[0]]
        self.assertEqual(len(oci), 5)  # artifact provenance, SBOM, output diff, sandbox image, index manifest
        for step in oci:
            self.assertIn("push-to-registry: true", step)
            self.assertIn("create-storage-record: false", step)


# Fakes for release/build-all on top of FAKES: build.py in the sandbox image,
# the static checks, and a compile gate that passed.
BUILD_FAKES = {
    "bin/docker": """#!/usr/bin/env bash
for a; do [[ $a == type=bind,src=*,dst=/out ]] && out=${a#type=bind,src=} && out=${out%,dst=/out}; done
mkdir -p -- "$out/demo"
echo '{"name": "demo", "version": "1.13.0", "krab": null}' >"$out/demo/meta.json"
echo '["demo"]' >"$out/names.json"
""",
    "root/scan/static-scan": "#!/usr/bin/env bash\n",
    "root/scan/exceptions.py": "",
    "root/release/scan-record": "#!/usr/bin/env bash\necho '{\"exceptions\": '\"$1\"'}'\n",
    "root/sandbox/gate-compile": """#!/usr/bin/env bash
echo compatible >"$KRAB_RESULT"
echo '[{"software": "Demo", "version": "1.0"}]' >"$SCHEMA_RESULT"
echo '[{"group": "", "version": "v1", "kind": "Service"}]' >"$KINDS_RESULT"
if [[ -n ${BACKENDS_RESULT:-} ]]; then printf '%s\\n' reclass-rs omegaconf >"$BACKENDS_RESULT"; fi
mkdir -p -- "$OUTPUT_DIR/compiled/t"
echo 'port: 80' >"$OUTPUT_DIR/compiled/t/svc.yml"
""",
}


class Attested(unittest.TestCase):
    """PUB-4: a failed attestation lookup is tried three times before the digest counts as unattested."""

    def run_attested(self, failures):
        with tempfile.TemporaryDirectory() as tmp:
            calls = os.path.join(tmp, "calls")
            gh = os.path.join(tmp, "gh")
            with open(gh, "w", encoding="utf-8") as f:
                f.write(f"""#!/usr/bin/env bash
echo x >>{calls!r}
(( $(wc -l <{calls!r}) > {failures} ))
""")
            os.chmod(gh, 0o755)
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            p = subprocess.run(["bash", "-c", f". {os.path.join(root, 'release', 'common.sh')!r} && attested ghcr.io/x/demo@sha256:0"],
                               env={**os.environ, "PATH": f"{tmp}:{os.environ['PATH']}", "ATTESTED_DELAY_SCALE": "0",
                                    "GITHUB_REPOSITORY": "o/r", "IDENTITY": "i"})
            with open(calls, encoding="utf-8") as f:
                return p.returncode, len(f.readlines())

    def test_transient_failures_are_retried(self):
        self.assertEqual(self.run_attested(2), (0, 3))

    def test_missing_attestation_still_fails(self):
        self.assertEqual(self.run_attested(3), (1, 3))

    def test_attested_digest_needs_one_lookup(self):
        self.assertEqual(self.run_attested(0), (0, 1))


class BuildAll(unittest.TestCase):
    """PUB-7, PUB-9 to PUB-11, CMP-4: release/build-all merges the gate's results into meta.json."""

    setUp = OutputDiff.setUp

    def test_meta_records_the_results_of_the_compile_gate(self):
        for rel, text in BUILD_FAKES.items():
            path = os.path.join(self.tmp, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            os.chmod(path, 0o755)
        out = os.path.join(self.tmp, "out")
        subprocess.run([os.path.join(self.root, "release", "build-all"), out], env=self.env, check=True, capture_output=True)
        with open(os.path.join(out, "demo", "meta.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), {
                "name": "demo", "version": "1.13.0", "krab": "compatible", "scan": {"exceptions": 0},
                "compatibility": [{"software": "Demo", "version": "1.0"}],
                "output_diff": {"base": None, "error": "no earlier listed version"},
                "kinds": [{"group": "", "version": "v1", "kind": "Service"}],
                "backends": ["reclass-rs", "omegaconf"]})

    def test_root_license_next_to_the_tree(self):  # PUB-15
        fakes = {
            # The generator's commit has a root LICENSE, the recipe's has none.
            "bin/git": "#!/usr/bin/env bash\nfor a; do [[ $a != d*:LICENSE ]] || exit 1; [[ $a != *:LICENSE ]] || echo \"license at $a\"; done\n",
            "bin/docker": """#!/usr/bin/env bash
for a; do
  [[ $a == type=bind,src=*,dst=/src,readonly ]] && src=${a#type=bind,src=} && src=${src%,dst=/src,readonly}
  [[ $a == type=bind,src=*,dst=/out ]] && out=${a#type=bind,src=} && out=${out%,dst=/out}
done
(cd -- "$src" && grep -r . --include=LICENSE --include='*.LICENSE' .) >"$out/licenses.txt"
echo '[]' >"$out/names.json"
""",
        }
        for rel, text in fakes.items():
            with open(os.path.join(self.tmp, rel), "w", encoding="utf-8") as f:
                f.write(text)
            os.chmod(os.path.join(self.tmp, rel), 0o755)
        out = os.path.join(self.tmp, "out")
        subprocess.run([os.path.join(self.root, "release", "build-all"), out], env=self.env, check=True, capture_output=True)
        with open(os.path.join(out, "licenses.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), f"./demo.LICENSE:license at {'c' * 40}:LICENSE\n")

    def build_recipe(self, source, renders_rc=0, rev="d" * 40):  # REC-12, REC-13
        recipe = {"pins": [f"ghcr.io/kadet-hub/kubernetes:1.9.0@sha256:{'a' * 64}", f"ghcr.io/kadet-hub/certmanager:1.0.2@sha256:{'b' * 64}"],
                  "recipes": {"other": {"rule": "REC-16", "version": "1.0.0", "digest": "sha256:" + "d" * 64},
                              "req": {"rule": "REC-17", "version": "2.0.0", "digest": "sha256:" + "e" * 64}},
                  "included": ["other"], "required": {"req": []}, "source": ["Source: x"], "level": ["Level: x"],
                  "description": "Demo recipe.", "license": "Apache-2.0"}
        fields = {"source": source, "level": "deploys", "kinds": [{"group": "", "version": "v1", "kind": "Service"}]}
        sec12 = (f"SEC-12: rbac-admin: compiled/demo/rbac.yml: ClusterRole x\nSEC-12: admission-webhook: compiled/demo/w.yml: x\n"
                 f"SEC-12: rbac-admin: compiled/demo/rbac.yml: ClusterRole y\nSEC-12: host-path: compiled/other/x.yml: x\n"
                 f"SEC-12: unparsed output compiled/demo/notes.txt (*)\n")
        log = os.path.join(self.tmp, "log")
        fakes = {
            "bin/docker": """#!/usr/bin/env bash
for a; do
  [[ $a == -c ]] && { cat -- "$FAKE_FIELDS"; exit; }
  [[ $a == type=bind,src=*,dst=/out ]] && out=${a#type=bind,src=} && out=${out%,dst=/out}
done
mkdir -p -- "$out/recipes/demo"
echo "{\\"name\\": \\"demo\\", \\"version\\": \\"1.0.0\\", \\"tree\\": \\"t\\", \\"owners\\": [1]}" >"$out/recipes/demo/meta.json"
echo '["recipes/demo"]' >"$out/names.json"
""",
            "root/gate/recipe-renders": f"""#!/usr/bin/env bash
echo "recipe-renders $1 $2 $3 GH_TOKEN=${{GH_TOKEN:-unset}}" >>"$FAKE_LOG"
exit {renders_rc}
""",
            "root/release/scan-record": "#!/usr/bin/env bash\necho '{\"exceptions\": '\"$1\"', \"for\": \"'\"$2\"'\"}'\n",
        }
        for rel, text in fakes.items():
            with open(os.path.join(self.tmp, rel), "w", encoding="utf-8") as f:
                f.write(text)
            os.chmod(os.path.join(self.tmp, rel), 0o755)
        with open(os.path.join(self.root, "recipes", "demo.yaml"), "w", encoding="utf-8") as f:
            f.write(f"source:\n  repo: {REPO}\n  path: demo\n  tag: demo-v1.0.0\n  sha: {rev}\n")
        for name, data in (("recipe.json", recipe), ("fields.json", fields)):
            with open(os.path.join(self.tmp, name), "w", encoding="utf-8") as f:
                json.dump(data, f)
        out = os.path.join(self.tmp, "out")
        shutil.rmtree(out, ignore_errors=True)
        open(log, "w").close()
        p = subprocess.run([os.path.join(self.root, "release", "build-all"), out], capture_output=True, text=True,
                           env=dict(self.env, FAKE_LOG=log, FAKE_RECIPE_JSON=os.path.join(self.tmp, "recipe.json"),
                                    FAKE_FIELDS=os.path.join(self.tmp, "fields.json"), FAKE_SEC12=sec12, RECIPES_CHECK=self.tmp))
        with open(log, encoding="utf-8") as f:
            calls = f.read().splitlines()
        if p.returncode:
            return p, calls, None
        with open(os.path.join(out, "recipes", "demo", "meta.json"), encoding="utf-8") as f:
            return p, calls, json.load(f)

    def test_recipe_record(self):
        chart = ["chart", ["quay.io/jetstack/charts/cert-manager", "v1.21.2", "sha256:" + "c" * 64]]
        p, calls, meta = self.build_recipe(chart)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(meta, {
            "name": "demo", "version": "1.0.0", "tree": "t", "owners": [1], "description": "Demo recipe.", "license": "Apache-2.0",
            "level": "deploys", "chart": {"repo": "quay.io/jetstack/charts/cert-manager", "version": "v1.21.2", "digest": "sha256:" + "c" * 64},
            # The pins of the recipe and its included recipes; the included recipes, not the required ones (AC-14).
            "generators": [{"name": "kubernetes", "version": "1.9.0", "digest": "sha256:" + "a" * 64},
                           {"name": "certmanager", "version": "1.0.2", "digest": "sha256:" + "b" * 64}],
            "includes": [{"name": "other", "version": "1.0.0", "digest": "sha256:" + "d" * 64}],
            # DEC-23: the matches in the recipe's own output, once each.
            "output_capabilities": ["admission-webhook", "rbac-admin"],
            "kinds": [{"group": "", "version": "v1", "kind": "Service"}],
            "scan": {"exceptions": 0, "for": "recipe"}, "output_diff": {"base": None, "error": "no earlier listed version"}})
        # Only the recipe checks get the token; the renders proof runs on what they wrote.
        dirs = calls[1].split()[1:4]
        self.assertEqual((calls[0], dirs[1], calls[1].split()[-1]), (f"recipe-checks {'d' * 40} GH_TOKEN=x", "demo", "GH_TOKEN=unset"))
        self.assertEqual((os.path.basename(dirs[0]), os.path.basename(dirs[2])), ("recipes", "proof"))
        http = ["http", ["https://kubernetes-sigs.github.io/external-dns", "external-dns", "1.23.0", "sha256:" + "c" * 64]]
        self.assertEqual(self.build_recipe(http)[2]["chart"], {"repo": "https://kubernetes-sigs.github.io/external-dns/external-dns",
                                                                "version": "1.23.0", "digest": "sha256:" + "c" * 64})
        manifest = ["manifest", ["rabbitmq/cluster-operator", "v2.23.1", "cluster-operator.yml", "sha256:" + "c" * 64]]
        self.assertEqual(self.build_recipe(manifest)[2]["manifest"], {
            "url": "https://github.com/rabbitmq/cluster-operator/releases/download/v2.23.1/cluster-operator.yml", "digest": "sha256:" + "c" * 64})
        for source in (["design", ["docker.io/library/rabbitmq", "4.3.6-management", "sha256:" + "c" * 64]], None):
            meta = self.build_recipe(source)[2]
            self.assertEqual(("chart" in meta, "manifest" in meta, meta["level"]), (False, False, "deploys"))

    def test_recipe_checks_and_renders_fail_the_build(self):  # REC-12
        p, _, _ = self.build_recipe(None, renders_rc=1)
        self.assertEqual(p.returncode, 1)
        self.assertIn("REC-12: recipe demo 1.0.0: the renders proof failed", p.stdout)
        p, calls, _ = self.build_recipe(None, rev="failing")
        self.assertEqual(p.returncode, 1)
        self.assertIn("REC-12: recipe demo 1.0.0: the checks failed", p.stdout)
        self.assertEqual(len(calls), 1)


class ScanRecord(unittest.TestCase):
    """PUB-7, REC-12: release/scan-record lists the checks of the run, a recipe's with check and kind."""

    def record(self, *args):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "gitleaks"), "w", encoding="utf-8") as f:
                f.write("#!/usr/bin/env bash\necho 8.30.1\n")
            os.chmod(os.path.join(tmp, "gitleaks"), 0o755)
            p = subprocess.run([os.path.join(ROOT, "release", "scan-record"), *args], capture_output=True, text=True, check=True,
                               env=dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"], GITHUB_SHA="c" * 40,
                                        GITHUB_SERVER_URL="https://github.com", GITHUB_REPOSITORY="kadet-hub/registry", GITHUB_RUN_ID="1"))
        return json.loads(p.stdout)["checks"]

    def test_recipe_checks(self):
        generator, recipe = self.record("0"), self.record("0", "recipe")
        with open(os.path.join(ROOT, ".github", "actions", "setup-check", "action.yml"), encoding="utf-8") as f:
            check = re.search(r"CHECK_VERSION: check-v(\S+)", f.read()).group(1)
        with open(os.path.join(ROOT, ".github", "actions", "setup-kind", "action.yml"), encoding="utf-8") as f:
            kind = re.search(r"KIND_VERSION: (\S+)", f.read()).group(1)
        self.assertEqual(recipe, generator + [{"id": "lint", "tool": f"check {check}"},
                                              {"id": "renders", "tool": f"check {check}, kind {kind}"}])
        self.assertEqual([c["id"] for c in generator][-1], "ci-env")


class Recipe(unittest.TestCase):
    """REC-11, PUB-15: release/sign with git on a real repository and a fake registry."""

    setUp = OutputDiff.setUp
    FILES = {"LICENSE": "Apache License\n", "demo/init.yml": "classes: [.demo]\n", "demo/README.md": "# demo\n",
             "demo/vendor/crds.yaml": "kind: CRD\n", "demo/tests/target.yml": "classes: [recipes.demo]\n",
             "demo/tests/smoke": "#!/bin/sh\n", "other/init.yml": "{}\n", "gen/kapitan-generator.yaml": "name: gen\n",
             "gen/schemas/core/secret_v1.json": "{}\n"}

    def commit(self, remove=()):
        repo = os.path.join(self.tmp, "repo")
        if not os.path.isdir(repo):
            for rel, text in self.FILES.items():
                os.makedirs(os.path.dirname(os.path.join(repo, rel)), exist_ok=True)
                with open(os.path.join(repo, rel), "w", encoding="utf-8") as f:
                    f.write(text)
            os.chmod(os.path.join(repo, "demo/tests/smoke"), 0o755)
            # init and fetch do nothing; every other git call reads the repository.
            with open(os.path.join(self.tmp, "bin", "git"), "w", encoding="utf-8") as f:
                f.write(f"""#!/usr/bin/env bash
args=()
for a; do
  case $a in init | fetch) exit 0 ;; --git-dir=*) a=--git-dir={repo}/.git ;; esac
  args+=("$a")
done
exec {shutil.which("git")} "${{args[@]}}"
""")
        for rel in remove:
            os.remove(os.path.join(repo, rel))
        git_tree(repo)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "t"], cwd=repo,
                       check=True, env=GIT_ENV)
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, env=GIT_ENV, capture_output=True, text=True).stdout.strip()

    def sign(self, name, sha, tar, tree=None, schemas=None):
        """Signs the tar's files {path: text} as <name> at sha; tree defaults to the ID of the shipped tree without LICENSE."""
        base = name.removeprefix("recipes/")
        path = "demo" if name.startswith("recipes/") else "gen"
        entry = os.path.join(self.root, f"{name}.yaml" if name.startswith("recipes/") else f"generators/{name}.yaml")
        with open(entry, "w", encoding="utf-8") as f:
            f.write(f"source:\n  repo: {REPO}\n  path: {path}\n  tag: {base}-v1.0.0\n  sha: {sha}\n")
        built = os.path.join(self.tmp, "built", name)
        shutil.rmtree(os.path.join(self.tmp, "built"), ignore_errors=True)
        os.makedirs(built)
        content = {p: (False, t.encode()) for p, t in tar.items()}
        write_tar(content, os.path.join(built, f"{base}.tar"))
        shipped = {p[len(path) + 1:]: (False, t.encode()) for p, t in self.FILES.items() if p.startswith(path + "/") and "/tests/" not in p}
        meta = {"name": base, "version": "1.0.0", "tree": tree or tree_id(shipped), "license": "Apache-2.0", "description": "Demo",
                "source": {"repo": REPO, "path": path, "tag": f"{base}-v1.0.0", "sha": sha}}
        with open(os.path.join(built, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f)
        if schemas is not None:
            with open(os.path.join(built, "schemas.json"), "w", encoding="utf-8") as f:
                json.dump(schemas, f)
        outputs, pushed = os.path.join(self.tmp, "outputs"), os.path.join(self.tmp, "manifest.json")
        open(outputs, "w").close()
        if os.path.exists(pushed):
            os.remove(pushed)
        p = subprocess.run([os.path.join(self.root, "release", "sign"), name, built], capture_output=True, text=True,
                           env=dict(self.env, GITHUB_OUTPUT=outputs, FAKE_PUSHED=pushed), cwd=self.root)
        with open(outputs, encoding="utf-8") as f:
            out = dict(line.rstrip("\n").split("=", 1) for line in f)
        if not os.path.exists(pushed):
            return p, out, None
        with open(pushed, encoding="utf-8") as f:
            return p, out, json.load(f)

    def test_sign(self):
        sha = self.commit()
        shipped = {p[5:]: t for p, t in self.FILES.items() if p.startswith("demo/") and "/tests/" not in p}
        p, out, manifest = self.sign("recipes/demo", sha, dict(shipped, LICENSE=self.FILES["LICENSE"]))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual((out["publish"], out["ref"], out["version"]), ("true", "ghcr.io/kadet-hub/recipes/demo", "1.0.0"))
        self.assertEqual((manifest["artifactType"], manifest["config"]["mediaType"], manifest["layers"][0]["mediaType"],
                          manifest["layers"][0]["annotations"]["org.opencontainers.image.title"]),
                         ("application/vnd.kadet-hub.recipe.v1", "application/vnd.kadet-hub.recipe.config.v1+json",
                          "application/vnd.oci.image.layer.v1.tar", "demo.tar"))
        with open(out["sbom"], encoding="utf-8") as f:
            self.assertEqual(sorted(x["fileName"] for x in json.load(f)["files"]),
                             ["./LICENSE", "./README.md", "./init.yml", "./vendor/crds.yaml"])
        # A tar that ships tests/, or lacks the root LICENSE (PUB-15), is not the tree without its tests entry
        # plus the LICENSE, and nothing is pushed.
        tests = {p[5:]: t for p, t in self.FILES.items() if p.startswith("demo/tests/")}
        for tar in (dict(shipped, LICENSE=self.FILES["LICENSE"], **tests), shipped, dict(shipped, LICENSE="Other\n")):
            p, out, manifest = self.sign("recipes/demo", sha, tar)
            self.assertEqual((p.returncode, manifest), (1, None))
            self.assertIn("PUB-1: recipes/demo 1.0.0: tar tree", p.stdout)
        # meta.json names the shipped tree without the LICENSE (PUB-15), as REC-16 looks it up.
        tar = dict(shipped, LICENSE=self.FILES["LICENSE"])
        p, _, manifest = self.sign("recipes/demo", sha, tar, tree=tree_id({k: (False, v.encode()) for k, v in tar.items()}))
        self.assertEqual((p.returncode, manifest), (1, None))

    def test_sign_generator(self):  # PUB-15, PUB-8
        sha = self.commit()
        shipped = {p[4:]: t for p, t in self.FILES.items() if p.startswith("gen/")}
        p, out, _ = self.sign("gen", sha, dict(shipped, LICENSE=self.FILES["LICENSE"]),
                              schemas={"dir": "schemas", "sources": {"core": {"software": "Kubernetes"}}})
        self.assertEqual((p.returncode, out["publish"]), (0, "true"), p.stdout + p.stderr)
        with open(out["sbom"], encoding="utf-8") as f:
            self.assertEqual([x["name"] for x in json.load(f)["packages"]], ["gen", "Kubernetes"])
        p, _, manifest = self.sign("gen", sha, shipped)
        self.assertEqual((p.returncode, manifest), (1, None))
        sha = self.commit(remove=["LICENSE"])
        p, _, manifest = self.sign("gen", sha, shipped)
        self.assertEqual((p.returncode, manifest), (1, None))
        self.assertIn("PUB-15: gen 1.0.0: no LICENSE in the tree or at the repository root", p.stdout)


class Mirror(unittest.TestCase):
    """PUB-13: release/mirror-image with a fake oras; FAKE_TAGS lists the mirror's tags as <tag> <digest>."""

    UP = "sha256:" + "u" * 64

    def mirror(self, labels, tags="", created="2026-10-13T21:58:13Z"):
        with tempfile.TemporaryDirectory() as tmp:
            calls, summary = os.path.join(tmp, "calls"), os.path.join(tmp, "summary")
            with open(os.path.join(tmp, "config.json"), "w", encoding="utf-8") as f:
                json.dump({"created": created, "config": {"Labels": labels}}, f)
            with open(os.path.join(tmp, "oras"), "w", encoding="utf-8") as f:
                f.write(f"""#!/usr/bin/env bash
echo "$*" >>{calls!r}
case "$1" in
  resolve) [[ $3 == quay.io/* ]] && {{ echo {self.UP}; exit; }}
           d=$(awk -v t="${{3##*:}}" '$1 == t {{print $2}}' <<<"$FAKE_TAGS"); [[ -n $d ]] || {{ echo "$3: not found" >&2; exit 1; }}; echo "$d" ;;
  manifest) cat {os.path.join(tmp, "config.json")!r} ;;
esac
""")
            os.chmod(os.path.join(tmp, "oras"), 0o755)
            p = subprocess.run([os.path.join(ROOT, "release", "mirror-image"), "quay.io/kubevirt/kubevirt-csi-driver:latest",
                                "kubevirt-csi-driver", "https://github.com/kubevirt/csi-driver", "https://srpm/a/", "https://srpm/b/"],
                               capture_output=True, text=True,
                               env=dict(os.environ, PATH=tmp + os.pathsep + os.environ["PATH"], REGISTRY="ghcr.io/kadet-hub",
                                        FAKE_TAGS=tags, GITHUB_STEP_SUMMARY=summary))
            with open(calls, encoding="utf-8") as f:
                writes = [c.split()[0] for c in f.read().splitlines() if c.split()[0] in ("cp", "tag")]
            summary_text = ""
            if os.path.exists(summary):
                with open(summary, encoding="utf-8") as f:
                    summary_text = f.read()
            return p.returncode, p.stdout, writes, summary_text

    def test_new_commit_is_copied_and_tagged(self):
        rc, out, writes, summary = self.mirror({"multi.GIT_SHA": "3a1a099"})
        self.assertEqual((rc, writes), (0, ["cp", "tag"]))
        self.assertIn(f"ghcr.io/kadet-hub/mirror/kubevirt-csi-driver:3a1a099: pushed {self.UP}", out)
        self.assertIn(f"| `{self.UP}` | `ghcr.io/kadet-hub/mirror/kubevirt-csi-driver:3a1a099` |", summary)
        self.assertIn("Source: https://github.com/kubevirt/csi-driver/tree/3a1a099.", summary)
        self.assertIn("Base image source RPMs: https://srpm/a/ https://srpm/b/", summary)

    def test_summary_names_no_commit_for_a_date_tag(self):
        summary = self.mirror({})[3]
        self.assertIn("Source: https://github.com/kubevirt/csi-driver (tag 20261013 is the image date, not a commit).", summary)
        self.assertNotIn("/tree/", summary)

    def test_oci_revision_wins_and_date_is_the_fallback(self):
        self.assertIn(":abc: pushed", self.mirror({"org.opencontainers.image.revision": "abc", "multi.GIT_SHA": "def"})[1])
        self.assertIn(":20261013: pushed", self.mirror({})[1])
        self.assertIn(":20261013: pushed", self.mirror(None)[1])

    def test_existing_tag_is_never_moved(self):
        rc, out, writes, _ = self.mirror({"multi.GIT_SHA": "3a1a099"}, tags=f"3a1a099 {self.UP}")
        self.assertEqual((rc, writes), (0, []))
        self.assertIn("already", out)
        self.assertIn("Source: https://github.com/kubevirt/csi-driver/tree/3a1a099.", self.mirror({"multi.GIT_SHA": "3a1a099"}, tags=f"3a1a099 {self.UP}")[3])
        rc, out, writes, summary = self.mirror({"multi.GIT_SHA": "3a1a099"}, tags="3a1a099 sha256:" + "o" * 64)
        self.assertEqual((rc, writes, summary), (1, [], ""))
        self.assertIn("tag not moved", out)
