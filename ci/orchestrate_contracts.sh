#!/usr/bin/env bash
# Two-phase contract run across every repo. The CI counterpart of build_verify.sh.
#
# WHY TWO PHASES, NOT AN ORDER
# ----------------------------
# Five producer/consumer pairs are mutual -- each side consumes the other's stubs:
#
#   DeliveryExecutiveApplication <-> MapsIntegration
#   DeliveryExecutiveApplication <-> GovernmentIDValidationService
#   CustomerApplication          <-> PaymentGatewayIntegration
#   CustomerApplication          <-> RestaurantApplication
#   GovernmentIDValidationService<-> RestaurantApplication
#
# That is a cycle, so no per-service ordering exists where every consumer reads current stubs --
# whichever side runs first reads the other's PREVIOUS recording. build_verify.sh solves this
# locally by publishing everything before verifying anything; this does the same across GitHub.
#
#   Phase 1  every "Publish contract stubs"   (produces recordings, consumes none -- order irrelevant)
#   Phase 2  every "Contract tests"           (now every consumer reads a current registry)
#
# Phase 2 does not start if any Phase 1 run failed. A failed publish leaves a STALE jar in the
# registry, and the consumer error then surfaces a repo away from its cause -- which is exactly how
# CustomerApplication's getDriverOrderMoney contract, claiming an endpoint that did not exist,
# stayed hidden for two runs.
#
# Nothing here enables an automatic trigger: every workflow stays workflow_dispatch, and a human
# runs this. Usage:
#   ci/orchestrate_contracts.sh --dry-run    # show what would be triggered, trigger nothing
#   ci/orchestrate_contracts.sh              # run both phases
#   ci/orchestrate_contracts.sh --phase 1    # publish only
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1          # workspace root
MAP="FoodDeliveryContracts/ci/repo-map.tsv"
[ -f "$MAP" ] || { echo "FAIL: $MAP not found"; exit 1; }

DRY=0; ONLY_PHASE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1 ;;
    --phase) shift; ONLY_PHASE="$1" ;;
    *) echo "unknown arg: $1"; exit 2 ;;
  esac
  shift
done

# dir -> repo, skipping comments. Only repos that actually have the workflow are used.
repos_with() {
  local wf="$1"
  while IFS=$'\t' read -r dir repo; do
    case "$dir" in \#*|"") continue ;; esac
    [ -f "$dir/.github/workflows/$wf" ] && echo "$dir	$repo"
  done < "$MAP"
}

run_phase() {
  local wf_file="$1" wf_name="$2" phase="$3"
  local started="" failed=0 n=0
  echo "==> Phase $phase: $wf_name"

  local since
  since=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  while IFS=$'\t' read -r dir repo; do
    n=$((n+1))
    if [ "$DRY" -eq 1 ]; then
      printf "    would trigger  %-32s %s\n" "$dir" "$repo"
      continue
    fi
    if gh workflow run "$wf_name" --repo "$repo" >/dev/null 2>&1; then
      printf "    triggered      %-32s %s\n" "$dir" "$repo"
      started="$started$repo"$'\n'
    else
      printf "    FAILED TO START %-31s %s\n" "$dir" "$repo"
      failed=1
    fi
  done < <(repos_with "$wf_file")

  [ "$DRY" -eq 1 ] && { echo "    ($n repo(s), dry run -- nothing triggered)"; return 0; }
  [ "$failed" -eq 1 ] && { echo "FAIL: could not start every run in phase $phase"; return 1; }

  echo "    waiting for $n run(s)..."
  sleep 10
  local pending=1 loops=0
  while [ "$pending" -gt 0 ] && [ "$loops" -lt 120 ]; do
    pending=0
    while read -r repo; do
      [ -z "$repo" ] && continue
      local st
      st=$(gh run list --repo "$repo" --workflow "$wf_name" --created ">$since" \
             --limit 1 --json status -q '.[0].status' 2>/dev/null)
      [ "$st" = "completed" ] || pending=$((pending+1))
    done <<< "$started"
    [ "$pending" -gt 0 ] && sleep 15
    loops=$((loops+1))
  done

  echo "    results:"
  while read -r repo; do
    [ -z "$repo" ] && continue
    local concl
    concl=$(gh run list --repo "$repo" --workflow "$wf_name" --created ">$since" \
              --limit 1 --json conclusion -q '.[0].conclusion' 2>/dev/null)
    printf "      %-12s %s\n" "${concl:-unknown}" "$repo"
    [ "$concl" = "success" ] || failed=1
  done <<< "$started"

  [ "$failed" -eq 0 ] || { echo "FAIL: phase $phase had failures"; return 1; }
  echo "    phase $phase OK"
  return 0
}

if [ -z "$ONLY_PHASE" ] || [ "$ONLY_PHASE" = "1" ]; then
  run_phase "publish-stubs.yml" "Publish contract stubs" 1 || exit 1
fi
if [ -z "$ONLY_PHASE" ] || [ "$ONLY_PHASE" = "2" ]; then
  run_phase "contract-tests.yml" "Contract tests" 2 || exit 1
fi
echo "==> done"
