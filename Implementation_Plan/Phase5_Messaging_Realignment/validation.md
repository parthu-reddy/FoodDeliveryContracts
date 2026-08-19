# Phase 5: Messaging Contract Realignment - Validation

The failure this phase exists to prevent is a contract that is internally consistent but describes
nothing real. A passing producer test is therefore **not** sufficient evidence - the closed loop
passes today. Validation must compare the contract against the **Java event class** and against the
**fields consumers actually read**.

## 1. Contract body vs real event class

Save as `FoodDeliveryContracts/validate_event_schema_alignment.py`.

For each messaging contract, resolve its topic to the producing event class (mapping table in
`plan.md`), parse that class's fields with a Java field parser, and assert:

- every top-level key in the contract body exists as a field on the event class;
- no contract key is nested under a `payload` object that the class does not declare;
- a field typed `UUID` is matched by the UUID regex, never by an integer literal;
- a field typed `BigDecimal`/`Double` is matched by a number, not a string.

Expected outcome: exits `0`. Against today's contracts it must fail for **every** Kafka contract
except `redis_tracking_order` - that failing baseline is what proves the validator works.

## 2. Contract vs consumer read paths

Parse each `@KafkaListener` method for `rootNode.path("x")` / `.get("x")` reads, and assert every
field the consumer reads is present in the contract for that topic.

Expected outcome: exits `0`. This is the check that catches the current envelope bug - consumers
read `orderId` at the root while the contract nests it under `payload`.

## 3. Trigger must not hand-write the payload

Assert that no `BaseMessagingClass` trigger method contains a JSON text block literal
(`String payload = """{`). Triggers must serialize a real DTO or drive the outbox.

Expected outcome: exits `0`. This is the check that closes the loop hole; without it a realigned
contract can still be validated against invented JSON.

## 4. Producer suite still green

```bash
for s in DeliveryExecutiveApplication ONDCIntegrationService MapsIntegration \
         PaymentGatewayIntegration CustomerApplication RestaurantApplication \
         UserTrackingService GovernmentIDValidationService; do
  (cd "$s" && mvn -o clean test-compile -Dnet.bytebuddy.experimental=true \
   && mvn -o surefire:test -Dtest=MessagingTest -DfailIfNoTests=false \
        -Dnet.bytebuddy.experimental=true)
done
```

Expected outcome: **17 tests, 0 failures, 0 errors** - the same count as the Phase 4 baseline. A
drop means a contract was realigned but its trigger was not.
