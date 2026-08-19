# Phase 8: CI/CD Enforcement & Broker Publication - Validation

## 1. Broker parity

Script: walk every service's `src/test/resources/contracts` and the matching
`META-INF/com.fooddelivery/<artifactId>/<version>/contracts`, and assert set equality by
`(topic-or-url, method)`.

Expected outcome: exits `0`. Baseline today: **48 local vs 30 central**, 5 services behind.

Also assert `<version>` in the META-INF path equals the `<version>` in that service's `pom.xml` -
this catches the `1.0-SNAPSHOT` vs `0.0.1-SNAPSHOT` mismatch.

## 2. Broker URL uniformity

```bash
python3 FoodDeliveryContracts/validate_broker_url.py
```

Expected outcome: exits `0` with every occurrence on the intended URL. Update `CANONICAL` in the
script when the switch happens, so the validator tracks the new intent.

## 3. Simulated CI consumer run

Run consumer tests with the local `~/.m2` contract artifacts removed and a mock `GIT_TOKEN`
injected, so stubs must come from the remote.

Expected outcome: tests pass **and** the log shows a git clone of the broker. If they pass without
one, they silently fell back to `.m2` and the gate is not real.

## 4. Producer publication

Run the producer pipeline and assert a stubs `.jar` is produced and the broker's remote HEAD
advances (compare `git rev-parse origin/main` before and after).

## 5. The gate actually gates (negative control)

Break a `WalletService` contract on a branch and run the consumer job.

Expected outcome: the build **fails**. A green run here means the pipeline is decorative - this is
the single check that proves Phase 8 delivered anything.
