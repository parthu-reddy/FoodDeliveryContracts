# Phase 8: CI/CD Enforcement & Broker Publication - Plan

Formerly `Phase6_CICD`, now also absorbing the stub-publication item deferred from Phase 2 and the
`GIT_TOKEN` item deferred from Phase 1.

## Current state - verified 2026-08-19

`.github/workflows/ci-cd.yml` runs a single aggregator step:

```yaml
- run: mvn clean install
```

There is **no** stub publication, no `GIT_TOKEN`, and no contract-specific gate. Contract testing is
therefore unenforced: nothing stops a producer merging a breaking change.

The broker is also **stale**: the central `META-INF` holds **30** contracts against **48** local,
with 5 services behind and 2 unpushed commits.

## Ordering constraint

**Do not publish before Phase 5 completes.** Roughly a third of the contracts are about to change
shape; pushing now would entrench the wrong schema in the exact place consumers read from.

## 1. Broker publication

Reconcile local -> central for `CustomerApplication` (15 vs 9), `RestaurantApplication` (9 vs 3),
`DeliveryExecutiveApplication` (6 vs 4), `GovernmentIDValidationService` (5 vs 2) and
`LedgerService` (2 vs 0), then automate it via `pushStubsToScm` so drift cannot recur.

Note the artifactId/version mismatch to resolve first: `META-INF` uses `1.0-SNAPSHOT` for every
service, but `mapsintegration`, `payment-service` and `government-id-validation-service` are
actually `0.0.1-SNAPSHOT`.

## 2. Broker URL switch

The whole fleet currently points at the local workspace clone
(`git://file:///Users/.../FoodDeliveryContracts/.git`) - a deliberate temporary setting. Switching
back is a one-line change to `CANONICAL` in `set_broker_url.py`, re-verified by
`validate_broker_url.py`.

**Constraint discovered in Phase 1:** the Maven plugin's `contractsRepositoryUrl` cannot take a
path containing a space, so producers must keep reading their local contracts. Only the runtime
`stubrunner.repositoryRoot` and `@AutoConfigureStubRunner` should point at the remote.

## 3. Pipeline gates

- **Producer job:** `mvn clean test` -> generated contract tests run -> on success
  `pushStubsToScm`. A producer that breaks its own contract fails the build.
- **Consumer job:** `mvn clean test` -> stub runner clones the broker -> consumer tests run against
  the newest stubs. A consumer expecting a removed field fails the build.
- Inject a PAT as `GIT_TOKEN`; use `+` version resolution so consumers always test the latest stubs.

## 4. Governance

`-SNAPSHOT` from `develop`, fixed versions from `main`.
