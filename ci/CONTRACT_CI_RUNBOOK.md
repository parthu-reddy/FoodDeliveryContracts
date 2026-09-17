# Publishing and verifying contract stubs across all repos

How to get every service's stubs republished and every consumer contract test passing. Works as a
runbook for a person, or as a prompt for an agent — paste the whole file.

Workspace root: `/Users/parthureddy/Documents/Food Delivery.nosync`. Each service directory is its
own git repository; the workspace root is deliberately NOT a repo, so never `git init` there.

---

## Why two phases, and not an order

Consumer contract tests replay a "stub jar" the producer's build recorded, resolved from the GitHub
Packages registry at `parthu-reddy/FoodDeliveryContracts`. Five producer/consumer pairs are MUTUAL —
each consumes the other's stubs:

    DeliveryExecutiveApplication  <-> MapsIntegration
    DeliveryExecutiveApplication  <-> GovernmentIDValidationService
    CustomerApplication           <-> PaymentGatewayIntegration
    CustomerApplication           <-> RestaurantApplication
    GovernmentIDValidationService <-> RestaurantApplication

That is a cycle, so no per-service ordering works: whichever side runs first reads the other's
PREVIOUS recording, and can go green while proving nothing. Hence:

    Phase 1   every "Publish contract stubs"   produces recordings, consumes none -- order irrelevant
    Phase 2   every "Contract tests"           every consumer now reads a current registry

**Phase 2 must not start if any Phase 1 run failed.** A failed publish leaves a stale jar in the
registry, and the resulting consumer error then surfaces in a different repo from its cause.

This is the CI counterpart of `build_verify.sh`, which solves the same cycle locally by publishing
every artifact in pass 1 before verifying anything in pass 2.

## Running it

    bash FoodDeliveryContracts/ci/orchestrate_contracts.sh --dry-run    # preview, triggers nothing
    bash FoodDeliveryContracts/ci/orchestrate_contracts.sh --phase 1
    # stop here and diagnose if any run failed
    bash FoodDeliveryContracts/ci/orchestrate_contracts.sh --phase 2

The script reads `ci/repo-map.tsv` rather than deriving repo names — three differ from their
directory (`PaymentGatewayIntegration -> PaymentService`, `RestaurantApplication ->
RestaurentApplication`, `CommunicationIntegration -> NotificationService`), so deriving silently
skips them. It triggers all repos in a phase at once, polls until each reports `completed`, prints
every conclusion, and returns non-zero if any is not `success`.

Report which repos are green and which are not, with the actual failure for each.

## Traps this codebase has actually sprung

Read these before debugging anything. Each one cost real time.

- **`mvn test -Dtest=SomeGeneratedTest` without `clean` exits 1 with "No tests matching pattern".**
  Generated contract tests only exist once the plugin regenerates them. That exit code means "ran
  nothing", not "found a bug". It misled two separate investigations on 2026-09-17.
- **Local maven here defaults to OFFLINE (`-o`) against a warm `~/.m2`.** A consumer contract test
  can resolve stubs from disk locally and still fail on CI, which has no local stub cache. Local
  green is NOT evidence for a CI change.
- **`-Pci-tests` excludes `**/*Contract*Test.java` AND sets
  `spring.cloud.contract.verifier.skip=true`.** A test's name alone does not tell you whether it
  runs; with that profile the generated producer tests are never created at all.
- **Producer vs consumer contract tests need different things.** Producer tests exercise a service
  against its own contracts via its own base class and need no registry. Consumer tests
  (`@AutoConfigureStubRunner`) resolve other services' stubs and need `STUBRUNNER_*` env, which only
  `contract-tests.yml` sets. Mixing them into a publish job breaks it — that mistake shipped once.
- **`CampaignService.MessagingTest` flakes** on an embedded-Kafka `createTopics` timeout under
  parallel builds; it passes in isolation and on re-run.
- **All 52 workflows are `workflow_dispatch` only**, by owner decision 2026-09-12. Do not add or
  propose automatic push triggers.
- **Never commit or push unless the user asks in the moment.**

## Verifying locally first

`bash FoodDeliveryContracts/build_verify.sh` — two passes plus a gate that generated contract tests
actually ran. 15-25 minutes, offline. Last known good: exit 0, 1044 tests, 0 failures, 30 modules.

---

## Current state, 2026-09-17

Time-bound; delete once done.

1. **12 repos have an uncommitted `.github/workflows/publish-stubs.yml` change.** Until now no
   workflow ran a PRODUCER contract test — this job used `-DskipTests`, and `build-and-push.yml` uses
   `-Pci-tests`. Stubs reached the registry unverified. The change runs only the generated producer
   tests, then asserts each produced a surefire report. Repos: BiddingEngine, BudgetLimitingService,
   CampaignService, CustomerApplication, DeliveryExecutiveApplication, GovernmentIDValidationService,
   MapsIntegration, ONDCIntegrationService, PaymentGatewayIntegration, RestaurantApplication,
   UserTrackingService, WalletService.
2. **`ci/orchestrate_contracts.sh` is new and untracked.** Only ever run with `--dry-run`; its
   trigger paths are unexercised, so suspect the script before suspecting CI on first use.
3. **A real contract bug is fixed but unpublished.** `CustomerApplication`'s
   `getDriverOrderMoney.groovy` claimed `/api/v1/money/driver/orders/{id}/earnings`; the real
   controller `InternalMoneyController` is mapped at `/api/v1/internal/money`. The fix is committed;
   the registry still holds the bad jar, which is why `DeliveryExecutiveApplication`'s "Contract
   tests" fails with `testGetDriverOrderMoney:84 expected: not <null>`.
4. **MapsIntegration's two new fleet contracts** (`fleet-release.groovy`,
   `fleet-set-availability.groovy`) are committed but not in the registry, so
   `DeliveryExecutiveApplication`'s `MapsFleetContractConsumerTest` fails until it republishes.

Items 1 and 2 need committing and pushing before any of this will work.
