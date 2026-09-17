#!/usr/bin/env bash
# Trigger "Build and Push Docker Image" across repos, base dependencies first, and wait.
#
# Replaces the build stage of the old publish-all-changes workflow, which:
#   * listed the parent as FoodDeliveryParentPOM -- that is the REPO name; the DIRECTORY is
#     FoodDeliveryParent, so `cd` failed and the parent POM never built
#   * hardcoded a service list that had already drifted from repo-map.tsv (missing CommonLibrary,
#     Deployment, FoodDeliveryContracts, FoodDeliveryParent, IdentitySigning)
#   * tracked runs with `gh run list -L N` -- the N most recent runs in the repo, unfiltered, so any
#     unrelated run in flight was watched instead
#
# This reads repo-map.tsv, and finds its runs by workflow name AND start time.
#
# Usage:
#   ci/build_services.sh --dry-run
#   ci/build_services.sh                       base deps, then every service with the workflow
#   ci/build_services.sh --only CustomerApplication,MapsIntegration
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1
MAP="FoodDeliveryContracts/ci/repo-map.tsv"
[ -f "$MAP" ] || { echo "FAIL: $MAP not found"; exit 1; }

SVC_WF_FILE="build-and-push.yml"
SVC_WF_NAME="Build and Push Docker Image"
# The base dependencies are libraries, not images: they publish to GitHub Packages via publish.yml
# and have no build-and-push.yml at all. Looking for the wrong file here silently skipped them --
# the same shape of bug as the old script's FoodDeliveryParentPOM/FoodDeliveryParent mixup.
BASE_WF_FILE="publish.yml"
BASE_WF_NAME="Publish to GitHub Packages"

# Ordered: each publishes artifacts the next consumes. Directory names, not repo names.
BASE=("FoodDeliveryParent" "IdentitySigning" "CommonLibrary")

DRY=0; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --only) shift; ONLY="${1:-}" ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
  shift
done

selected() {
  [ -z "$ONLY" ] && return 0
  case ",$ONLY," in *",$1,"*) return 0 ;; *) return 1 ;; esac
}

repo_for() {
  while IFS=$'\t' read -r dir repo; do
    case "$dir" in \#*|"") continue ;; esac
    [ "$dir" = "$1" ] && { echo "$repo"; return 0; }
  done < "$MAP"
  return 1
}

is_base() {
  local d="$1"; for b in "${BASE[@]}"; do [ "$b" = "$d" ] && return 0; done; return 1
}

# Trigger one group, wait for all of it, report. Returns non-zero if any run is not success.
run_group() {
  local label="$1" WF_FILE="$2" WF_NAME="$3"; shift 3
  local dirs=("$@")
  local started_dirs=() started_repos=() failed=0 n=0
  [ ${#dirs[@]} -eq 0 ] && { echo "==> $label: nothing to do"; return 0; }

  echo "==> $label"
  local since; since=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  for dir in "${dirs[@]}"; do
    local repo; repo=$(repo_for "$dir") || { echo "    SKIP $dir (not in repo-map.tsv)"; continue; }
    [ -f "$dir/.github/workflows/$WF_FILE" ] || { echo "    skip $dir (no $WF_FILE)"; continue; }
    n=$((n+1))
    if [ "$DRY" -eq 1 ]; then
      printf "    would trigger  %-32s %s\n" "$dir" "$repo"
      continue
    fi
    if gh workflow run "$WF_NAME" --repo "$repo" >/dev/null 2>&1; then
      printf "    triggered      %-32s %s\n" "$dir" "$repo"
      started_dirs+=("$dir"); started_repos+=("$repo")
    else
      printf "    FAILED TO START %-31s %s\n" "$dir" "$repo"
      failed=1
    fi
  done

  [ "$DRY" -eq 1 ] && { echo "    ($n repo(s), dry run)"; return 0; }
  [ "$failed" -eq 1 ] && { echo "FAIL: could not start every run in $label"; return 1; }
  [ ${#started_repos[@]} -eq 0 ] && return 0

  echo "    waiting for ${#started_repos[@]} run(s)..."
  sleep 10
  local pending=1 loops=0
  while [ "$pending" -gt 0 ] && [ "$loops" -lt 160 ]; do
    pending=0
    for repo in "${started_repos[@]}"; do
      local st
      st=$(gh run list --repo "$repo" --workflow "$WF_NAME" --created ">$since" \
             --limit 1 --json status -q '.[0].status' 2>/dev/null)
      [ "$st" = "completed" ] || pending=$((pending+1))
    done
    [ "$pending" -gt 0 ] && sleep 15
    loops=$((loops+1))
  done

  echo "    results:"
  local i=0
  for repo in "${started_repos[@]}"; do
    local concl
    concl=$(gh run list --repo "$repo" --workflow "$WF_NAME" --created ">$since" \
              --limit 1 --json conclusion -q '.[0].conclusion' 2>/dev/null)
    printf "      %-12s %-32s %s\n" "${concl:-unknown}" "${started_dirs[$i]}" "$repo"
    [ "$concl" = "success" ] || failed=1
    i=$((i+1))
  done
  [ "$failed" -eq 0 ] || { echo "FAIL: $label had failures"; return 1; }
  echo "    $label OK"
  return 0
}

# Base dependencies, one at a time and in order: each publishes what the next resolves.
for dir in "${BASE[@]}"; do
  selected "$dir" || continue
  run_group "base: $dir" "$BASE_WF_FILE" "$BASE_WF_NAME" "$dir" || exit 1
done

# Everything else, together -- they depend on the base, not on each other's images.
SERVICES=()
while IFS=$'\t' read -r dir repo; do
  case "$dir" in \#*|"") continue ;; esac
  is_base "$dir" && continue
  selected "$dir" || continue
  [ -f "$dir/.github/workflows/$SVC_WF_FILE" ] && SERVICES+=("$dir")
done < "$MAP"

run_group "services" "$SVC_WF_FILE" "$SVC_WF_NAME" "${SERVICES[@]}" || exit 1
echo "==> build complete"
