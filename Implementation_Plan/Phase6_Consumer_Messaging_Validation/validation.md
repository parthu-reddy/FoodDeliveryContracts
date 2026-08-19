# Phase 6: Consumer Messaging Validation - Validation

A green messaging consumer test currently means nothing - all 25 are green today while asserting
nothing. Counting passing tests is therefore an invalid signal for this phase. Validate the
**content** of the tests programmatically.

## 1. No vacuous consumer tests

Already implemented. Run:

```bash
python3 FoodDeliveryContracts/validate_consumer_assertions.py
```

For every test using `stubTrigger` it asserts:

- **zero** occurrences of `catch (Exception` (no swallowing);
- at least one `assert*` / `verify(` / `await(` per `@Test` method;
- every `stubTrigger.trigger("X")` label X matches a `label("X")` declared in some contract.

Expected outcome: exits `0`.

**Confirmed baseline (2026-08-19): 25/25 fail**, every one on all three rules. The validator also
surfaces the label bug concretely - e.g. tests fire `trigger-ad-event` and `trigger-chat-event`,
neither of which any contract declares.

## 2. Exact listener coverage counter

```bash
grep -rho '@KafkaListener' --include='*.java' */src/main/java | wc -l   # must be 25
```

Then assert a 1:1 mapping from each `@KafkaListener`-bearing class to a consumer test class.
Expected outcome: 25 listeners, 25 mapped tests, zero unmapped.

## 3. Negative control (the important one)

Assertions can be written that pass regardless of delivery. Prove they fail when they should:

1. Temporarily point one consumer test at a label whose contract emits a **different** topic.
2. Re-run that test.

Expected outcome: the test **fails**. If it still passes, the assertion is not observing the
consumer and the test is vacuous in a new disguise. Revert after confirming.

## 4. Suite execution

```bash
for s in CustomerApplication RestaurantApplication DeliveryExecutiveApplication WalletService \
         LedgerService PaymentGatewayIntegration CampaignService BiddingEngine \
         BudgetLimitingService ONDCIntegrationService MapsIntegration \
         CommunicationIntegration CommunicationService GovernmentIDValidationService; do
  (cd "$s" && mvn -o clean test -Dnet.bytebuddy.experimental=true)
done
```

Expected outcome: 0 failures, and the total assertion count reported by check 1 is >= 25.
