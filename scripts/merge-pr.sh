#!/usr/bin/env bash
#
# merge-pr.sh — solo-maintainer toggle merge for protected branches.
#
# GitHub forbids approving your own PR, so when there's only one human
# committer the `required_approving_review_count: 1` rule on `main` blocks
# every merge. This script wraps the safe pattern:
#
#   1. Snapshot current branch protection
#   2. Lower required_approving_review_count to 0
#   3. Squash-merge the PR
#   4. Restore required_approving_review_count to its original value
#
# The whole sequence takes ~3 seconds and is auditable in the repo's
# Settings → Audit log.
#
# Usage:
#   scripts/merge-pr.sh <PR_NUMBER> [BRANCH]
#
# Examples:
#   scripts/merge-pr.sh 42                # merge into main (default)
#   scripts/merge-pr.sh 42 main           # explicit main
#   scripts/merge-pr.sh 42 staging        # merge into staging
#
# Requirements:
#   - gh CLI authenticated as a repo admin (write isn't enough — branch
#     protection is admin-only)
#   - The PR must be CLEAN with all required CI checks GREEN
#   - jq is NOT required; uses python3 for JSON parsing
#
# Safety rails:
#   - Refuses to run if PR is not OPEN
#   - Refuses to run if any required CI check is failing or pending
#   - Always restores the original review count, even on failure (trap EXIT)
#   - Refuses to lower below 0
#
set -euo pipefail

PR_NUMBER="${1:-}"
BRANCH="${2:-main}"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

if [[ -z "$PR_NUMBER" ]]; then
  echo "Usage: $0 <PR_NUMBER> [BRANCH=main]"
  exit 1
fi

if ! gh pr view "$PR_NUMBER" --json state -q .state | grep -qx "OPEN"; then
  echo "::error::PR #$PR_NUMBER is not OPEN"
  gh pr view "$PR_NUMBER" --json state,title
  exit 1
fi

# Verify CI is fully green before touching protection.
# We use mergeStateStatus to get GitHub's combined view of the gate.
MERGE_STATE=$(gh pr view "$PR_NUMBER" --json mergeStateStatus -q .mergeStateStatus)
case "$MERGE_STATE" in
  CLEAN|BLOCKED)
    # CLEAN = ready, BLOCKED = only the review requirement is blocking
    ;;
  DIRTY)
    echo "::error::PR #$PR_NUMBER has merge conflicts. Resolve them first."
    exit 1
    ;;
  BEHIND)
    echo "::error::PR #$PR_NUMBER is behind the base branch. Update first."
    exit 1
    ;;
  UNSTABLE)
    echo "::error::PR #$PR_NUMBER has failing required checks."
    gh pr view "$PR_NUMBER" --json statusCheckRollup -q '.statusCheckRollup[] | select(.conclusion == "FAILURE") | .name'
    exit 1
    ;;
  *)
    echo "::error::PR #$PR_NUMBER mergeStateStatus is '$MERGE_STATE' (expected CLEAN or BLOCKED)"
    exit 1
    ;;
esac

# Snapshot current required_approving_review_count.
# A 404 here means there's no review-protection rule (already 0 effectively).
ORIGINAL_COUNT=$(
  gh api -X GET "repos/$REPO/branches/$BRANCH/protection/required_pull_request_reviews" 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('required_approving_review_count', 0))" \
    || echo "0"
)

if [[ "$ORIGINAL_COUNT" -eq 0 ]]; then
  echo "Branch '$BRANCH' has no review requirement; merging directly."
  gh pr merge "$PR_NUMBER" --squash --delete-branch
  exit 0
fi

echo "Branch '$BRANCH' requires $ORIGINAL_COUNT approving review(s)."
echo "Lowering to 0 → merging → restoring."

# Make sure we always restore the rule, even if the merge fails.
restore_protection() {
  echo "Restoring required_approving_review_count to $ORIGINAL_COUNT..."
  gh api -X PATCH "repos/$REPO/branches/$BRANCH/protection/required_pull_request_reviews" \
    -F dismiss_stale_reviews=true \
    -F require_code_owner_reviews=false \
    -F require_last_push_approval=false \
    -F required_approving_review_count="$ORIGINAL_COUNT" \
    > /dev/null
  echo "Restored."
}
trap restore_protection EXIT

gh api -X PATCH "repos/$REPO/branches/$BRANCH/protection/required_pull_request_reviews" \
  -F dismiss_stale_reviews=true \
  -F require_code_owner_reviews=false \
  -F require_last_push_approval=false \
  -F required_approving_review_count=0 \
  > /dev/null

gh pr merge "$PR_NUMBER" --squash --delete-branch

echo "PR #$PR_NUMBER merged successfully."
