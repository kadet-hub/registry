# shellcheck shell=bash
# Sourced by sign and publish-index. Needs IDENTITY and GITHUB_REPOSITORY.

# Prints the output of an oras call; returns 1 when the registry reports the
# reference missing and 2 on any other error. Callers run it in $(...).
lookup() {
  local err
  err=$(mktemp)
  if "$@" 2>"$err"; then rm -f -- "$err"; return 0; fi
  if grep -qE 'not found|name unknown|manifest unknown' "$err"; then rm -f -- "$err"; return 1; fi
  cat -- "$err" >&2
  rm -f -- "$err"
  return 2
}

# The digest carries an attestation from this repository's release workflow on
# main. A lookup that fails is tried again, because the attestation API also
# fails on transient errors (PUB-4); a digest without one still fails.
# ATTESTED_DELAY_SCALE=0 lets the tests skip the waits.
attested() {
  local delay
  for delay in 5 15 0; do
    gh attestation verify "oci://$1" --repo "$GITHUB_REPOSITORY" --cert-identity "$IDENTITY" >/dev/null 2>&1 && return 0
    ((delay == 0)) || sleep "$((delay * ${ATTESTED_DELAY_SCALE:-1}))"
  done
  return 1
}
