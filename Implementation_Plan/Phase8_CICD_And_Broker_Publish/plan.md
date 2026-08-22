# Phase 8: CI/CD Enforcement & Broker Publication - Plan

> ## STATUS UPDATE — 2026-08-20: not started, and NEWLY BLOCKED
>
> ### The blocker is new and structural
>
> The workspace no longer has a multi-module aggregator. The root `pom.xml` **has been deleted** and
> replaced by `FoodDeliveryParent/` — a dependency-management parent (`packaging: pom`, **no
> `<modules>`**) that 21 services now inherit from.
>
> **CI is therefore broken right now.** `.github/workflows/ci-cd.yml` still runs:
>
> ```yaml
> - name: Build and Test with Maven
>   run: mvn clean install
> ```
>
> from the workspace root, which fails immediately:
>
> ```
> [ERROR] The goal you specified requires a project to execute but there is no POM in this directory
> ```
>
> Nothing downstream of that step has run since the change.
>
> ### What this phase must now do first
>
> 1. **Decide the build topology.** Either restore an aggregator POM listing the modules, or change CI
>    to build each service in dependency order — `FoodDeliveryParent` → `CommonLibrary` → the rest.
>    The parent-only layout is a legitimate choice, but it means there is no single `mvn install` and
>    CI must encode the order explicitly.
> 2. **Then** gate on the validators, as originally planned.
>
> ### Validators ready to gate on
>
> All ten pass today. Each has been demonstrated to fail on an injected defect, which is the part that
> makes them enforcement rather than decoration:
>
> `audit_http_contracts` · `validate_contract_base_coverage` · `validate_vacuous_consumer_tests` ·
> `validate_messaging_base_isolation` · `validate_contract_topics` · `sync_messaging_ids --check` ·
> `audit_consumer_contract_shapes` · `validate_consumer_assertions` · `validate_phase3_consumers` ·
> `validate_broker_url`
>
> They are pure Python, run in seconds, and should go **before** the Maven step so a 2-second failure
> does not wait on a full build.
>
> ### Do not enable the gate while the build is red
>
> A gate that always fails gets bypassed, and then the gate is worthless. Current per-module state is
> in [README.md](../README.md); at least two modules regressed since 2026-08-19 and must be fixed
> first.
>
> ### Broker publishing — still deferred, and still not `file://`
>
> All services resolve stubs from `~/.m2` with `stubsMode: LOCAL` (25 Java + 15 YAML declarations).
> Publishing to a shared broker stays deferred until the contracts settle. **Do not reintroduce a
> `file://` broker**: the workspace path contains a space, and Spring Cloud Contract decodes `%20`
> then re-parses, failing in both the Maven plugin and `BatchStubRunner`. The abandoned attempt is
> still on disk at `FoodDeliveryContracts/META-INF/` and has since diverged from the live contracts —
> see `FoodDeliveryContracts/README.md`.

---


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
