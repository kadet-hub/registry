# Changelog

Changes to the consumer workflow that you notice when you move your pin of
`consumer.yml` to a later commit, newest first. The workflow here means
`.github/workflows/consumer.yml`, the actions `consumer`, `compile-diff`
and `compile-diff-comment`, `consumer/`, the GitLab template
`sandbox/gitlab-ci.yml`, `policy/consumer.schema.json` and the sandbox
image they run. Tool updates that Renovate merges on its own are in the
commit history of `sandbox/`.

The next index release ([`index-<serial>`](https://github.com/kadet-hub/registry/releases))
after a change repeats its section in the release notes, and the release's
tag is the first commit to pin for it. Earlier changes are in the commit
history of the paths above.

## 2026-11-05: included recipes come from the index (#536)

For each recipe the fetch inventory pins, the workflow adds the recipes its
index record lists under `includes`, at the listed version and digest, and
verifies them like a pin. A pin of an included recipe passes at the listed
digest and fails at any other with a CON-9 finding that names the pin.

Fetch inventories that pin included recipes at the listed digests pass
unchanged. Delete those pins: with them in place, the first update that
moves a parent without its included recipe, or the other way round, fails.

## 2026-11-05: compile diff of pull requests (#537)

New actions `compile-diff` and `compile-diff-comment` compile a pull
request's base and merge commit through the consumer flow and post the
diff of `compiled/` as one comment. Projects that do not add them see no
change. [Compile diff in pull requests](https://github.com/kadet-hub/registry/blob/main/docs/consumers.md#compile-diff-in-pull-requests)
shows how to add them.
