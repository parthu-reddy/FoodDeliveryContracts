#!/usr/bin/env bash
#
# Safe repository visibility flipper.
#
# Flips all safe repositories in repo-map.tsv to public to avoid GitHub Actions billing limits.
# Records the prior visibility of each repository and only restores those it actually changed.
#
# Usage:
#   ci/flip_visibility.sh --public
#   ci/flip_visibility.sh --revert
#   ci/flip_visibility.sh --dry-run
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1
MAP="FoodDeliveryContracts/ci/repo-map.tsv"
STATE_FILE="FoodDeliveryContracts/ci/.visibility_state"

# Explicitly unsafe repositories that should NEVER be made public
UNSAFE_REPOS=("parthu-reddy/IdentitySigning" "parthu-reddy/IdentityService" "parthu-reddy/ConfigService")

DRY=0
ACTION=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --public) ACTION="public" ;;
    --revert) ACTION="revert" ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

if [ -z "$ACTION" ] && [ "$DRY" -eq 0 ]; then
  echo "Usage: $0 [--public | --revert] [--dry-run]"
  exit 1
fi

is_unsafe() {
  local repo="$1"
  for unsafe in "${UNSAFE_REPOS[@]}"; do
    if [ "$repo" == "$unsafe" ]; then return 0; fi
  done
  return 1
}

if [ "$ACTION" == "public" ] || [ "$DRY" -eq 1 -a -z "$ACTION" ]; then
  echo "==> Flipping safe repositories to PUBLIC"
  if [ "$DRY" -eq 0 ]; then
    > "$STATE_FILE"
  fi
  
  while IFS=$'\t' read -r dir repo; do
    case "$dir" in \#*|"") continue ;; esac
    
    if is_unsafe "$repo"; then
      echo "    SKIP $repo (marked as UNSAFE)"
      continue
    fi
    
    if [ "$DRY" -eq 1 ]; then
      echo "    would check and flip $repo"
      continue
    fi
    
    # Check current visibility
    current=$(gh repo view "$repo" --json visibility -q '.visibility' 2>/dev/null || echo "UNKNOWN")
    
    if [ "$current" == "PRIVATE" ]; then
      echo "    flipping $repo to PUBLIC..."
      if (cd "$dir" && gh repo edit --visibility public --accept-visibility-change-consequences); then
        # We cd'd into the dir, so the relative path to state file changes
        echo "$repo" >> "../../$STATE_FILE"
      else
        echo "    FAILED to flip $repo"
      fi
    elif [ "$current" == "PUBLIC" ]; then
      echo "    $repo is already PUBLIC, skipping."
    else
      echo "    FAILED to read visibility for $repo"
    fi
  done < "$MAP"
  
elif [ "$ACTION" == "revert" ]; then
  echo "==> Reverting repositories to PRIVATE"
  
  if [ ! -f "$STATE_FILE" ]; then
    echo "    No state file found at $STATE_FILE. Nothing to revert."
    exit 0
  fi
  
  while read -r repo; do
    [ -z "$repo" ] && continue
    if [ "$DRY" -eq 1 ]; then
      echo "    would revert $repo to PRIVATE"
      continue
    fi
    
    # Find directory for this repo
    dir=$(awk -F'\t' -v r="$repo" '$2 == r {print $1}' "$MAP")
    if [ -n "$dir" ]; then
      echo "    reverting $repo to PRIVATE..."
      (cd "$dir" && gh repo edit --visibility private --accept-visibility-change-consequences) || true
    else
      echo "    WARNING: Could not find directory for $repo in $MAP"
    fi
  done < "$STATE_FILE"
  
  if [ "$DRY" -eq 0 ]; then
    rm -f "$STATE_FILE"
  fi
fi

echo "==> done"
