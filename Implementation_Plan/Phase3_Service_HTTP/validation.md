# Phase 3: Service-Specific API Contracts (HTTP) - Validation

Injection alone is not evidence. The validator below parses each consumer test and fails any client
that is declared but never invoked - the exact condition that made this phase look complete when
four tests were still `contextLoads` shells.

## 1. Client coverage validator

Already implemented. Run:

```bash
python3 FoodDeliveryContracts/validate_phase3_consumers.py
```

For every `*ContractConsumerTest.java` it must assert:

- each `@Autowired` client field name appears in at least one `@Test` method body (invoked, not just declared);
- the test class declares at least one `assert*` / `verify(` call;
- no test method body is only `contextLoads`.

Expected outcome: exits `0`.

**Confirmed baseline (2026-08-19): 6 problems** - ONDC (4 clients injected, none invoked),
RestaurantApplication (`AdvertisementClient` unused), GovernmentIDValidationService (2 clients
unused + contextLoads shell), CommunicationService x2 (contextLoads shells), and CampaignService
(no consumer test file at all). That failing baseline is what this phase closes; reproduce it
before changing anything so you know the validator discriminates.

## 2. Exact consumer test execution counter

```bash
for s in CustomerApplication RestaurantApplication DeliveryExecutiveApplication \
         GovernmentIDValidationService ONDCIntegrationService BudgetLimitingService \
         CommunicationService CampaignService; do
  (cd "$s" && mvn -o test -Dtest='*ContractConsumerTest' -DfailIfNoTests=false \
      -Dnet.bytebuddy.experimental=true)
done
```

Expected outcome: every service reports `Failures: 0, Errors: 0`, and the **aggregate test count
strictly increases** against the recorded baseline of 21. A run that stays at 21 means assertions
were added to a class that was not executed.

## 3. Producer stubs must be installed first

`@AutoConfigureStubRunner(stubsMode = LOCAL)` resolves from `~/.m2`, so a stale stub jar silently
validates against an old contract. Before the sweep:

```bash
for s in CustomerApplication RestaurantApplication DeliveryExecutiveApplication \
         GovernmentIDValidationService IdentityService LedgerService \
         PaymentGatewayIntegration BiddingEngine; do
  (cd "$s" && mvn -o install -DskipTests -Dnet.bytebuddy.experimental=true)
done
```

Expected outcome: each stub jar's timestamp is newer than the newest `.groovy` file in that
service's `src/test/resources/contracts`.

## Known trap

`-Dtest=X` on a non-`clean` build can silently skip freshly generated tests: the SCC plugin writes
into `target/generated-test-sources/contracts`, and incremental compilation may not pick them up.
Always `mvn clean test-compile` before a targeted `surefire:test`, and confirm the class exists in
`target/test-classes` rather than trusting `BUILD SUCCESS`.
