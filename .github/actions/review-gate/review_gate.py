"""AGT-11: the review gate of a pull request (REV-4).

It passes when neat-bot's latest review approves the head commit and no user
with write access has an open change request. Pull requests Renovate opens
pass. Reviews come from the API with the job's read-only token; nothing from
the pull request is checked out.
"""
import json
import os
import subprocess
import sys

REVIEWER = "neat-bot"
RENOVATE = "renovate[bot]"  # merges only once every check passed (REV-5), exempt from REV-4


def login(review):
    return (review.get("user") or {}).get("login")  # None for a deleted account


def decide(author, head, reviews, has_write):
    """Reasons the gate fails, empty when it passes. reviews in API order (oldest first)."""
    if author == RENOVATE:
        return []
    reasons = []
    own = [r for r in reviews if login(r) == REVIEWER]
    if not own or own[-1]["state"] != "APPROVED" or own[-1]["commit_id"] != head:
        reasons.append(f"{REVIEWER}'s latest review does not approve {head}")
    # A change request stays open until its author approves or it is dismissed;
    # a later comment does not close it, as on GitHub.
    latest = {}
    for r in reviews:
        if login(r) and r["state"] in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[login(r)] = r["state"]
    for user, state in latest.items():
        if state == "CHANGES_REQUESTED" and has_write(user):
            reasons.append(f"{user} has requested changes")
    return reasons


def gh(path, jq):
    return subprocess.run(["gh", "api", "--paginate", path, "--jq", jq], check=True, capture_output=True, text=True).stdout


def main():
    repo, pr, author, head = (os.environ.get(k, "") for k in ("REPO", "PR", "AUTHOR", "HEAD_SHA"))
    if not (repo and pr and author and head):
        sys.exit("review-gate runs on pull_request and pull_request_review")
    # Renovate's pull requests pass without an API call.
    reviews = [json.loads(line) for line in gh(f"repos/{repo}/pulls/{pr}/reviews?per_page=100", ".[]").splitlines()] if author != RENOVATE else []
    reasons = decide(author, head, reviews, lambda user: gh(f"repos/{repo}/collaborators/{user}/permission", ".permission").strip() in ("admin", "write"))
    for reason in reasons:
        print(reason)
    print("review gate failed" if reasons else f"review gate passed at {head}")
    return 1 if reasons else 0


if __name__ == "__main__":
    sys.exit(main())
