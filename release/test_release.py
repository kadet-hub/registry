import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from index import build
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


ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
REPO = "https://github.com/example/demo.git"
# Fakes for release/output-diff and release/sign: the registry, git, and the
# fetch and compile steps the gate's own tests cover.
FAKES = {
    "bin/oras": """#!/usr/bin/env bash
case "$1 $2" in
  "manifest fetch") [[ -n ${FAKE_INDEX:-} ]] || { echo "$4: not found" >&2; exit 1; }; echo '{"layers": [{"digest": "sha256:1"}]}' ;;
  "blob fetch") cp -- "$FAKE_INDEX" "$4" ;;
  "blob push" | "manifest push") ;;
  *) echo "$*: not found" >&2; exit 1 ;;
esac
""",
    "bin/git": "#!/usr/bin/env bash\nfor a; do if [[ $a == rev-parse ]]; then echo \"$FAKE_TREE\"; fi; done\n",
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
