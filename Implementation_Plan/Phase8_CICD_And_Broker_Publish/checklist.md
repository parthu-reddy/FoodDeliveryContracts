# Phase 8: CI/CD Enforcement & Broker Publication - Checklist

**Status: not started. Blocked on Phase 5** (do not publish contracts that are about to change shape).

## Broker publication (deferred from Phase 2)

- [ ] Resolve the artifactId version mismatch: `META-INF` uses `1.0-SNAPSHOT` for all services, but
      `mapsintegration`, `payment-service` and `government-id-validation-service` are `0.0.1-SNAPSHOT`.
- [ ] Reconcile local -> central (48 local vs 30 central): CustomerApplication 15/9,
      RestaurantApplication 9/3, DeliveryExecutiveApplication 6/4,
      GovernmentIDValidationService 5/2, LedgerService 2/0.
- [ ] Commit and push the 2 outstanding commits in `FoodDeliveryContracts`.
- [ ] Automate publication via `pushStubsToScm` so drift cannot recur.

## Broker URL switch (deferred from Phase 1)

- [ ] Flip `CANONICAL` in `set_broker_url.py` to the GitHub URL; re-run `validate_broker_url.py`.
- [ ] Keep producers on local contracts - the Maven plugin cannot take a spaced path.
- [ ] Delete the stale `/tmp/FoodDelivery/FoodDeliveryContracts` duplicate clone once unreferenced.

## CI/CD

- [ ] Generate a GitHub PAT with `repo` scope for `FoodDeliveryContracts`.
- [ ] Add it as a CI secret and document it (`.env.example` or workflow docs) - it currently exists
      only as prose in plan files.
- [ ] Replace the bare `mvn clean install` with explicit producer and consumer jobs.
- [ ] Producer job publishes stubs only on `develop` / `main`.
- [ ] Consumer job resolves `+` from the remote broker, not `.m2`.
- [ ] Adopt the `-SNAPSHOT` (develop) / fixed-version (main) branching convention.

## Proof

- [ ] Break a contract in `WalletService` on a feature branch and confirm CI **blocks the merge**.
