# Incident runbook: a malicious version

For a listed version confirmed malicious (INC-1). Target: done within 24
hours of confirmation, best effort with one maintainer. Reports arrive as
described in [SECURITY.md](../SECURITY.md); a rescan finding (SEC-15)
needs the same confirmation before anything below.

Replace `<name>` and `<version>` throughout.

## 1. Draft the advisory

In `kadet-hub/registry`, Security → Advisories → New draft security
advisory. Name the generator and the affected versions, what the code does
and what a consumer who compiled it should rotate or check. Keep it a
draft for now and note its `GHSA-…` ID.

## 2. Yank in a maintainer pull request

```yaml
# generators/<name>.yaml, below the existing fields
yanked:
  "<version>": "malicious: <one line>"
advisories:
  "<version>": [GHSA-xxxx-xxxx-xxxx]
```

The gate accepts `advisories` only from a maintainer and treats the change
as no bump, since `tag` and `sha` stay. After the merge the release marks
the version yanked in the index; the catalog shows the reason and the
advisory, and the consumer workflow rejects the digest (CON-2).

If the source repository itself is hostile, remove the entry in the same
pull request instead and add the name to `policy/reserved-names.txt`
(REG-9); the index then reports the version as `entry removed`.

## 3. Delete the artifact

Only after step 2 is merged, because this cannot be undone:

```sh
id=$(gh api "/orgs/kadet-hub/packages/container/<name>/versions" \
  --jq '.[] | select(.metadata.container.tags | index("<version>")) | .id')
gh api -X DELETE "/orgs/kadet-hub/packages/container/<name>/versions/$id"
```

This needs a token with `delete:packages` and organization owner rights.
Then run the release once more (`gh workflow run release.yml -R
kadet-hub/registry`): it does not rebuild a yanked version, and the index
keeps the version's record with its digest, reason and advisory.

## 4. Check and publish

```sh
digest=$(oras resolve ghcr.io/kadet-hub/index:latest)
oras pull -o index "ghcr.io/kadet-hub/index@$digest"
jq '.generators["<name>"]["<version>"] | {digest, yanked, advisories}' index/index.json
oras resolve "ghcr.io/kadet-hub/<name>:<version>"   # must fail
```

Publish the advisory. If a newer version of the same generator is affected
too, repeat from step 2 for it.
