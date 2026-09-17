#!/usr/bin/env bash
# Commit and push the same change across the repos that have one. Nothing else.
#
# Replaces the commit stage of the old publish-all-changes workflow, which did `git add .` in every
# repo with a fixed message, then `git pull --rebase || true` before pushing -- so a conflicted
# rebase was swallowed and the push went out anyway. It is also why the history is a wall of
# "chore: automated workflow update".
#
# This script:
#   * requires a real message
#   * SHOWS what it is about to commit, per repo, and asks once
#   * treats a failed rebase as fatal FOR THAT REPO and pushes nothing there
#   * never touches repository visibility (see the runbook for why that is gone)
#
# Usage:
#   ci/commit_and_push.sh -m "fix: correct the earnings contract path"
#   ci/commit_and_push.sh -m "..." --dry-run     show what would happen, change nothing
#   ci/commit_and_push.sh -m "..." --yes         skip the confirmation
#   ci/commit_and_push.sh -m "..." --only CustomerApplication,MapsIntegration
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1
MAP="FoodDeliveryContracts/ci/repo-map.tsv"
[ -f "$MAP" ] || { echo "FAIL: $MAP not found"; exit 1; }

MSG=""; DRY=0; ASSUME_YES=0; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    -m) shift; MSG="${1:-}" ;;
    --dry-run) DRY=1 ;;
    --yes) ASSUME_YES=1 ;;
    --only) shift; ONLY="${1:-}" ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
  shift
done
[ -n "$MSG" ] || { echo "FAIL: -m \"message\" is required. A shared generic message is how the"; \
                   echo "      history became unreadable; say what changed."; exit 2; }

selected() {
  local dir="$1"
  [ -z "$ONLY" ] && return 0
  case ",$ONLY," in *",$dir,"*) return 0 ;; *) return 1 ;; esac
}

# Repos with something to commit, from the map -- never derived, never hardcoded.
DIRTY=()
while IFS=$'\t' read -r dir repo; do
  case "$dir" in \#*|"") continue ;; esac
  [ -d "$dir/.git" ] || continue
  selected "$dir" || continue
  [ -n "$(cd "$dir" && git status --porcelain)" ] && DIRTY+=("$dir")
done < "$MAP"

if [ ${#DIRTY[@]} -eq 0 ]; then
  echo "Nothing to commit in any repo."
  exit 0
fi

echo "About to commit and push with message:"
echo "    $MSG"
echo
for dir in "${DIRTY[@]}"; do
  echo "  $dir"
  (cd "$dir" && git status --porcelain | sed 's/^/      /')
done
echo

if [ "$DRY" -eq 1 ]; then
  echo "(dry run -- nothing committed, nothing pushed)"
  exit 0
fi

if [ "$ASSUME_YES" -eq 0 ]; then
  printf "Commit and push these %d repo(s)? [y/N] " "${#DIRTY[@]}"
  read -r reply
  case "$reply" in y|Y|yes|YES) ;; *) echo "aborted"; exit 1 ;; esac
fi

FAILED=()
for dir in "${DIRTY[@]}"; do
  echo "==> $dir"
  (
    cd "$dir" || exit 1
    git add -A || exit 1
    git commit -m "$MSG" || exit 1
    # Fatal, not `|| true`. A conflicted rebase leaves the tree mid-operation; pushing from there
    # is how half-merged work reaches a shared branch.
    if ! git pull --rebase origin main; then
      echo "    REBASE FAILED -- resolve it here, then re-run. Nothing pushed for this repo."
      exit 1
    fi
    git push origin main || exit 1
  )
  if [ $? -ne 0 ]; then
    FAILED+=("$dir")
    echo "    FAILED: $dir"
  else
    echo "    pushed"
  fi
done

if [ ${#FAILED[@]} -gt 0 ]; then
  echo
  echo "FAIL: ${#FAILED[@]} repo(s) not pushed: ${FAILED[*]}"
  exit 1
fi
echo
echo "All ${#DIRTY[@]} repo(s) pushed."
