import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan import check_index, dependencies, schema_errors

DIGEST = "sha256:" + "a" * 64
POLICY = {"index_serial": 5, "hosts": {"oci": ["ghcr.io"], "helm": ["charts.example.org"], "git": ["github.com"]}}


def inventory(*deps):
    return {"t1": {"parameters": {"kapitan": {"dependencies": list(deps)}}}}


def oci(source, **kw):
    return {"type": "oci", "source": source, "output_path": "lib/gen", "insecure": False, "tls_verify": True,
            "subpath": None, "media_type": None, **kw}


def helm(**kw):
    return {"type": "helm", "source": "https://charts.example.org", "chart_name": "demo", "version": "1.2.3",
            "output_path": "charts/demo", "helm_path": None, **kw}


def index(serial=5, yanked=None):
    record = {"digest": DIGEST, "yanked": yanked, "binaries": ["helm template"],
              "charts": [{"repo": "https://charts.example.org/", "name": "demo", "version": "1.2.3", "sha256": "b" * 64}]}
    return {"serial": serial, "generators": {"gen": {"1.0.0": record}}}


RECIPE = f"ghcr.io/kadet-hub/recipes/cert-manager:1.0.0@{DIGEST}"
# What Kapitan 0.36.3 writes into parameters.kapitan of a target that sets only dependencies.
KAPITAN_DEFAULTS = {"compile": [], "labels": {}, "secrets": None, "target_full_path": "", "validate": [],
                    "vars": {"target": None}}


def recipe(source=RECIPE, name="cert-manager", **kw):
    return oci(source, **{"output_path": f"inventory/classes/recipes/{name}", **kw})


def fetch_inventory(*deps, **kapitan):
    return {"recipes": {"parameters": {"kapitan": {**KAPITAN_DEFAULTS, "dependencies": list(deps), **kapitan}}}}


def recipe_index(recipes, serial=5):
    return {"serial": serial, "generators": {}, "recipes": recipes}


def recipe_record(digest=DIGEST, yanked=None, includes=()):
    return {"digest": digest, "yanked": yanked, "includes": list(includes),
            "output_capabilities": ["admission-webhook"]}


def digest(c):
    return "sha256:" + c * 64


class Dependencies(unittest.TestCase):
    def check(self, *deps):
        return dependencies(inventory(*deps), POLICY, "kadet-hub")

    def test_marketplace_artifact(self):
        for source, tag in ((f"ghcr.io/kadet-hub/gen@{DIGEST}", None), (f"ghcr.io/kadet-hub/gen:1.0.0@{DIGEST}", "1.0.0")):
            with self.subTest(source=source):
                deps, findings = self.check(oci(source))
                self.assertEqual(findings, [])
                self.assertEqual((deps[0]["marketplace"], deps[0]["tag"]), ("gen", tag))

    def test_rejected_dependencies(self):
        cases = [
            (oci("ghcr.io/kadet-hub/gen:1.0.0"), "source must be"),
            (oci(f"ghcr.io/kadet-hub/gen@{DIGEST}", insecure=True), "insecure"),
            (oci(f"quay.io/x/gen@{DIGEST}"), "host quay.io is not allowed for oci"),
            (oci(f"ghcr.io/kadet-hub/gen@{DIGEST}", output_path="../x"), "output_path"),
            (helm(version=None), "exact chart version"),
            (helm(source="http://charts.example.org"), "https URL"),
            (helm(chart_name="../../etc"), "chart_name"),
            (helm(chart_name="--repo"), "chart_name"),
            ({"type": "git", "source": "https://github.com/a/b.git", "ref": "main", "output_path": "x"}, "full commit SHA"),
            ({"type": "git", "source": "https://github.com/a/b.git", "ref": "c" * 40, "output_path": "x",
              "submodules": True}, "submodules"),
            ({"type": "http", "source": "http://example.org/x", "output_path": "x"}, "type http is not allowed"),
            ({"type": "https", "source": "https://user@example.org/x", "output_path": "x"}, "https URL"),
            ({"type": "https", "source": "https://[example.org/x", "output_path": "x"}, "https URL"),  # GI-14
        ]
        for dep, want in cases:
            with self.subTest(want=want):
                _, findings = self.check(dep)
                self.assertTrue(any(want in f for f in findings), findings)

    def test_inventory_not_a_mapping_of_targets(self):  # GI-14
        for inv in ("x", ["t1"], {"t1": {}, None: {}}, {"t1": {}, 2: {}}):
            with self.subTest(inventory=inv):
                self.assertEqual(dependencies(inv, POLICY, "kadet-hub"),
                                 ([], ["CON-1: the inventory is not a mapping of target names to targets"]))

    def test_target_not_a_mapping(self):  # GI-14
        for target in ("x", ["x"], {"parameters": "x"}, {"parameters": {"kapitan": ["x"]}},
                       {"parameters": {"kapitan": {"dependencies": "x"}}},
                       {"parameters": {"kapitan": {"dependencies": ["x"]}}}):
            with self.subTest(target=target):
                self.assertEqual(dependencies({"t1": target}, POLICY, "kadet-hub"),
                                 ([], ["CON-1: t1: parameters.kapitan.dependencies is not a list of mappings"]))

    def test_missing_levels_are_no_dependencies(self):
        for target in (None, {}, {"parameters": None}, {"parameters": {"kapitan": {"dependencies": None}}}):
            with self.subTest(target=target):
                self.assertEqual(dependencies({"t1": target}, POLICY, "kadet-hub"), ([], []))
        self.assertEqual(dependencies(None, POLICY, "kadet-hub"), ([], []))

    def test_conflicting_output_path(self):
        _, findings = self.check(oci(f"ghcr.io/kadet-hub/gen@{DIGEST}"), oci(f"ghcr.io/kadet-hub/other@{DIGEST}"))
        self.assertTrue(any("used by another dependency" in f for f in findings), findings)

    def test_recipe_in_main_inventory(self):  # CON-4: Kapitan would compile the recipe it loaded before the fetch
        deps, findings = self.check(recipe())
        self.assertEqual(deps, [])
        self.assertEqual(findings, [f"CON-1: t1: oci {RECIPE}: recipes belong in the fetch inventory (CON-4)"])


class FetchInventory(unittest.TestCase):  # CON-4 step 2
    def test_policy_path(self):  # relative to the repository root without .., as output_path
        schema = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "policy", "consumer.schema.json")
        for path in ("fetch", "deploy/fetch", "fetch-inventory", "..x"):
            with self.subTest(path=path):
                self.assertEqual(schema_errors(dict(POLICY, fetch_inventory=path), schema), [])
        for path in ("", "..", "../fetch", "a/../b", "a/..", ".", "./fetch", ".git", "/fetch", "fetch/", "a//b",
                     "a b", 1):
            with self.subTest(path=path):
                self.assertTrue(schema_errors(dict(POLICY, fetch_inventory=path), schema))

    def check(self, inv):
        return dependencies(inv, POLICY, "kadet-hub", fetch=True)

    def test_recipe_pins_pass(self):
        for source, tag in ((RECIPE, "1.0.0"), (f"ghcr.io/kadet-hub/recipes/cert-manager@{DIGEST}", None)):
            with self.subTest(source=source):
                deps, findings = self.check(fetch_inventory(recipe(source)))
                self.assertEqual(findings, [])
                self.assertEqual((deps[0]["recipe"], deps[0]["marketplace"], deps[0]["tag"]),
                                 ("cert-manager", None, tag))

    def test_rejected_dependencies(self):
        only = "the fetch inventory holds only oci sources ghcr.io/kadet-hub/recipes/"
        cases = [
            (oci(f"ghcr.io/kadet-hub/gen:1.0.0@{DIGEST}"), only),
            (recipe(output_path="inventory/classes/recipes/other"), only),
            (recipe(output_path="lib/cert-manager"), only),
            (recipe(f"ghcr.io/other/recipes/cert-manager@{DIGEST}"), only),
            (recipe(f"ghcr.io/kadet-hub/recipes/cert-manager/x@{DIGEST}"), "is not a marketplace recipe"),
            (recipe("ghcr.io/kadet-hub/recipes/cert-manager:1.0.0"), "source must be"),
            (recipe(insecure=True), "insecure"),
            (helm(), only),
            ({"type": "git", "source": "https://github.com/kadet-hub/recipes.git", "ref": "c" * 40,
              "subdir": "cert-manager", "output_path": "inventory/classes/recipes/cert-manager"}, only),
        ]
        for dep, want in cases:
            with self.subTest(want=want, dep=dep):
                _, findings = self.check(fetch_inventory(dep))
                self.assertTrue(findings and all(f.startswith("CON-4: recipes: ") for f in findings), findings)
                self.assertTrue(any(want in f for f in findings), findings)

    def test_kapitan_holds_only_dependencies(self):
        for key, value in (("compile", [{"input_type": "kadet", "input_paths": ["lib/x"], "output_path": "x"}]),
                           ("vars", {"target": "recipes"}), ("labels", {"a": "b"})):
            with self.subTest(key=key):
                _, findings = self.check(fetch_inventory(recipe(), **{key: value}))
                self.assertEqual(findings, [f"CON-4: recipes: parameters.kapitan sets {key}, "
                                            "a fetch target sets only dependencies"])

    def test_malformed_targets_fail(self):
        for target in ("x", {"parameters": {"kapitan": {"dependencies": "x"}}}):
            with self.subTest(target=target):
                self.assertEqual(self.check({"recipes": target}),
                                 ([], ["CON-4: recipes: parameters.kapitan.dependencies is not a list of mappings"]))


class Index(unittest.TestCase):
    def deps(self):
        deps, _ = dependencies(inventory(oci(f"ghcr.io/kadet-hub/gen@{DIGEST}"), helm()), POLICY, "kadet-hub")
        return deps

    def test_listed_version_passes_with_binaries_and_chart_digest(self):
        deps = self.deps()
        binaries, findings, notices = check_index(index(), POLICY, deps)
        self.assertEqual((binaries, findings, notices), (["helm template"], [], []))
        self.assertEqual(deps[1]["sha256"], "b" * 64)

    def test_lower_serial_fails_and_higher_is_reported(self):
        _, findings, _ = check_index(index(serial=4), POLICY, self.deps())
        self.assertTrue(any("serial 4 is lower" in f for f in findings), findings)
        _, findings, notices = check_index(index(serial=6), POLICY, self.deps())
        self.assertEqual(findings, [])
        self.assertTrue(notices)

    def test_unlisted_and_yanked_digests_fail(self):
        unlisted = index()
        unlisted["generators"]["gen"]["1.0.0"]["digest"] = "sha256:" + "c" * 64
        _, findings, _ = check_index(unlisted, POLICY, self.deps())
        self.assertTrue(any("does not list this digest" in f for f in findings), findings)
        _, findings, _ = check_index(index(yanked="broken"), POLICY, self.deps())
        self.assertTrue(any("yanked: broken" in f for f in findings), findings)

    def test_tag_must_be_the_listed_version(self):
        def findings(tag):
            deps, _ = dependencies(inventory(oci(f"ghcr.io/kadet-hub/gen:{tag}@{DIGEST}")), POLICY, "kadet-hub")
            return check_index(index(), POLICY, deps)[1]

        self.assertEqual(findings("1.0.0"), [])
        self.assertTrue(any("tag 1.0.3 is not 1.0.0" in f for f in findings("1.0.3")), findings("1.0.3"))


class RecipeIndex(unittest.TestCase):  # CON-5
    def findings(self, recipes, source=RECIPE):
        deps, _ = dependencies(fetch_inventory(recipe(source)), POLICY, "kadet-hub", fetch=True)
        return check_index(recipe_index(recipes), POLICY, deps)

    def test_listed_recipe_passes_and_adds_no_binaries(self):
        record = dict(recipe_record(), binaries=["helm template"])
        self.assertEqual(self.findings({"cert-manager": {"1.0.0": record}}), ([], [], []))

    def test_rejected(self):
        unlisted = f"CON-5: {RECIPE}: the index does not list this digest for recipe cert-manager"
        tagged = f"ghcr.io/kadet-hub/recipes/cert-manager:1.0.3@{DIGEST}"
        cases = [
            ({"cert-manager": {"1.0.0": recipe_record(digest("c"))}}, RECIPE, unlisted),
            ({"valkey": {"1.0.0": recipe_record()}}, RECIPE, unlisted),
            ({"cert-manager": {"1.0.0": recipe_record(yanked="broken")}}, RECIPE,
             "CON-5: recipe cert-manager 1.0.0 is yanked: broken"),
            ({"cert-manager": {"1.0.0": recipe_record()}}, tagged,
             f"CON-5: {tagged}: tag 1.0.3 is not 1.0.0, the version the index lists for this digest"),
        ]
        for recipes, source, want in cases:
            with self.subTest(want=want):
                self.assertEqual(self.findings(recipes, source)[1], [want])

    def test_index_without_recipes_or_with_a_generator_of_that_name(self):
        deps, _ = dependencies(fetch_inventory(recipe()), POLICY, "kadet-hub", fetch=True)
        for index in ({"serial": 5, "generators": {}},
                      {"serial": 5, "generators": {"cert-manager": {"1.0.0": {"digest": DIGEST}}}, "recipes": {}}):
            with self.subTest(index=index):
                self.assertEqual(check_index(index, POLICY, deps)[1],
                                 [f"CON-5: {RECIPE}: the index does not list this digest for recipe cert-manager"])


class Includes(unittest.TestCase):  # CON-4 step 3
    VALKEY = {"name": "valkey", "version": "1.0.0", "digest": digest("d")}

    def findings(self, pins, records):
        deps, findings = dependencies(fetch_inventory(*pins), POLICY, "kadet-hub", fetch=True)
        self.assertEqual(findings, [])
        return check_index(recipe_index(records), POLICY, deps)[1]

    def pin(self, name, d, version="1.0.0"):
        return recipe(f"ghcr.io/kadet-hub/recipes/{name}:{version}@{d}", name)

    def test_included_recipe_pinned_at_the_listed_digest_passes(self):
        records = {"nextcloud": {"1.0.0": recipe_record(digest("a"), includes=[self.VALKEY])},
                   "valkey": {"1.0.0": recipe_record(digest("d"))}}
        pins = [self.pin("nextcloud", digest("a")), self.pin("valkey", digest("d"))]
        self.assertEqual(self.findings(pins, records), [])

    def test_included_recipe_at_another_digest_or_missing_fails(self):
        records = {"nextcloud": {"1.0.0": recipe_record(digest("a"), includes=[self.VALKEY])},
                   "valkey": {"1.0.0": recipe_record(digest("d")), "1.1.0": recipe_record(digest("e"))}}
        other = self.findings([self.pin("nextcloud", digest("a")), self.pin("valkey", digest("e"), "1.1.0")], records)
        self.assertEqual(other, [f"CON-4: recipe nextcloud 1.0.0 includes valkey 1.0.0 at {digest('d')}, "
                                 f"the fetch inventory pins valkey at {digest('e')}"])
        missing = self.findings([self.pin("nextcloud", digest("a"))], records)
        self.assertEqual(missing, [f"CON-4: recipe nextcloud 1.0.0 includes valkey 1.0.0 at {digest('d')}, "
                                   "the fetch inventory does not pin valkey"])

    def test_two_parents_with_different_digests_are_both_named(self):
        records = {"nextcloud": {"1.0.0": recipe_record(digest("a"), includes=[self.VALKEY])},
                   "gitea": {"1.0.0": recipe_record(digest("b"), includes=[dict(self.VALKEY, version="1.1.0",
                                                                                digest=digest("e"))])},
                   "valkey": {"1.0.0": recipe_record(digest("d")), "1.1.0": recipe_record(digest("e"))}}
        findings = self.findings([self.pin("nextcloud", digest("a")), self.pin("gitea", digest("b")),
                                  self.pin("valkey", digest("d"))], records)
        self.assertEqual(findings, [f"CON-4: recipe gitea 1.0.0 includes valkey 1.1.0 at {digest('e')} and "
                                    f"recipe nextcloud 1.0.0 includes valkey 1.0.0 at {digest('d')}, "
                                    "the fetch inventory can pin only one"])


if __name__ == "__main__":
    unittest.main()
