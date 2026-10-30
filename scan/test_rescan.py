import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHA, MOVED, MAIN = "a" * 40, "b" * 40, "c" * 40
ENTRY = "source:\n  repo: https://github.com/example/{repo}.git\n  path: {path}\n  tag: {tag}\n  sha: " + SHA + "\n{extra}"
# Fakes: git answers ls-remote with $FAKE_TAGS ("<tag> <sha>" lines) and refs/heads/main with $FAKE_MAIN, lists the
# directories "check" and $FAKE_RECIPES, of which only the recipes have init.yml, and writes nothing else; fetch_tree.py
# writes the directories its arguments name, for --recipe also every one of $FAKE_RECIPES, each with one pinned image;
# static-scan reports one finding per scanned directory.
IMAGE = "quay.io/example/app:1.0@sha256:" + "e" * 64
FAKES = {
    "bin/git": """#!/usr/bin/env bash
last=${*: -1}
for a; do
  if [[ $a == ls-remote && $last == refs/heads/main ]]; then
    printf '%s\\trefs/heads/main\\n' "$FAKE_MAIN"
    exit 0
  elif [[ $a == ls-tree ]]; then
    printf '%s\\n' check $FAKE_RECIPES
    exit 0
  elif [[ $a == cat-file ]]; then
    d=${last#*:}; d=${d%/init.yml}
    [[ " $FAKE_RECIPES " == *" $d "* ]]
    exit
  elif [[ $a == ls-remote ]]; then
    tag=${*: -2:1}; tag=${tag#refs/tags/}
    awk -v t="$tag" '$1 == t {print $2 "\\trefs/tags/" t}' <<<"$FAKE_TAGS"
    exit 0
  fi
done
""",
    "root/gate/fetch_tree.py": """import os, sys
a = dict(zip(sys.argv[1::2], sys.argv[2::2]))
with open(os.environ["FAKE_LOG"], "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
dirs = [os.path.join(a["--out"], r) for r in [a["--recipe"], *os.environ["FAKE_RECIPES"].split()]] if "--recipe" in a else [a["--out"]]
for d in dirs:
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "init.yml"), "w") as f:
        f.write("image: """ + IMAGE + """\\n")
""",
    "root/scan/static-scan": """#!/usr/bin/env bash
echo "scan $1" >>"$FAKE_LOG"
echo "tree: banned file ${1##*/}.gitattributes"
exit 1
""",
}


@unittest.skipUnless(shutil.which("yq") and shutil.which("bash"), "needs yq and bash, which the runner has")
class Rescan(unittest.TestCase):
    """SEC-15, SEC-16, REC-14, SEC-19: scan/rescan with fake git, fetch and scan."""

    def test_recipe_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "root")
            os.makedirs(os.path.join(root, "scan"))
            shutil.copy(os.path.join(HERE, "rescan"), os.path.join(root, "scan"))
            shutil.copy(os.path.join(HERE, "exceptions.py"), os.path.join(root, "scan"))
            shutil.copy(os.path.join(HERE, "images.py"), os.path.join(root, "scan"))
            entries = {
                "generators/demo.yaml": ENTRY.format(repo="demo", path=".", tag="v1.0.0", extra=""),
                # A recipe of the same name, and one whose version is yanked.
                "recipes/demo.yaml": ENTRY.format(repo="recipes", path="demo", tag="demo-v2.0.0", extra="exceptions: []\n"),
                "recipes/old.yaml": ENTRY.format(repo="recipes", path="old", tag="old-v1.0.0", extra="yanked:\n  1.0.0: broken\n"),
            }
            for rel, text in {**FAKES, **{f"root/{k}": v for k, v in entries.items()}}.items():
                path = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                os.chmod(path, 0o755)
            log, findings, images = os.path.join(tmp, "log"), os.path.join(tmp, "findings.tsv"), os.path.join(tmp, "images.tsv")
            env = dict(os.environ, PATH=os.path.join(tmp, "bin") + os.pathsep + os.environ["PATH"], FAKE_LOG=log,
                       FAKE_TAGS=f"v1.0.0 {SHA}\ndemo-v2.0.0 {MOVED}\n", FAKE_MAIN=MAIN, FAKE_RECIPES="alpha beta")
            subprocess.run([os.path.join(root, "scan", "rescan"), findings, images], env=env, check=True, capture_output=True)
            with open(findings, encoding="utf-8") as f:
                rows = [ln.rstrip("\n").split("\t") for ln in f]
            with open(images, encoding="utf-8") as f:
                pinned = f.read()
            with open(log, encoding="utf-8") as f:
                calls = f.read().splitlines()
        self.assertEqual(rows, [
            ["rescan", "demo", "1.0.0", "tree: banned file demo.gitattributes"],
            ["drift", "recipe demo", "demo-v2.0.0", f"tag demo-v2.0.0 resolves to {MOVED}, the entry pins {SHA}"],
            ["rescan", "recipe demo", "2.0.0", "tree: banned file demo.gitattributes"],
        ])
        # The recipe is fetched as the gate fetches it (REC-4) and its own directory is scanned.
        recipe = [c for c in calls if f"--rev {SHA} --recipe" in c]
        self.assertEqual(len(recipe), 1)
        self.assertRegex(recipe[0], rf"--rev {SHA} --recipe demo --out (\S+)/recipes/demo$")
        out = recipe[0].rsplit(" ", 1)[1]
        self.assertIn(f"scan {out}/demo", calls)
        self.assertNotIn("old", "".join(calls))
        # SEC-19: the images of each fetched version, by catalog page; the yanked recipe is not fetched.
        # Every recipe at main of kadet-hub/recipes, fetched once by the name of the first recipe directory.
        self.assertEqual(pinned, f"generators/demo\t1.0.0\t{IMAGE}\nrecipes/demo\t2.0.0\t{IMAGE}\n"
                                 f"recipes/alpha\tmain@{MAIN}\t{IMAGE}\nrecipes/beta\tmain@{MAIN}\t{IMAGE}\n")
        self.assertEqual(len([c for c in calls if f"--rev {MAIN} --recipe alpha " in c]), 1)


if __name__ == "__main__":
    unittest.main()
