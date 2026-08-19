# Phase 4: Kafka Async Event Contracts (Core) — Validation

To rigorously crosscheck that Phase 4 was implemented correctly without missing edge cases, execute automated programmatic validations:

## 1. Automated Producer Trigger Verification
Run a strict Python validation script that loads all Groovy contracts using AST/regex, identifies every `triggeredBy('X')` clause, and cross-references it against the parsed Java AST of the `BaseMessagingClass.java`.
```python
# Execute: python3 scripts/verify_kafka_triggers.py
```
**Expected Outcome:** Script exits with code 0. All trigger methods exist, have `@Test` annotations, and successfully inject a message into the internal Kafka template mock.

## 2. Mathematical Consumer Listener Coverage
From `crosscheck_report_v2.md`, we know there are exactly 25 `@KafkaListener` annotations across all microservices. Execute an automated test counter to guarantee full coverage:
```bash
# Test execution counting
mvn test -Dtest=*KafkaConsumerTest* | grep "Tests run:"
```
**Expected Outcome:** The aggregate "Tests run" MUST equal exactly 25. If there are fewer than 25 executed CDC consumer tests for Kafka, a listener contract was missed.

## 3. Postel's Law Automated Audit
Use an automated schema validator to compare the Groovy `outputMessage` bodies against the full Database Entities.
```python
# Execute: python3 scripts/audit_postels_law.py
```
**Expected Outcome:** The validator asserts that the `outputMessage` bodies do NOT map to 100% of the Database Entity fields. They should only assert the subset of fields actually deserialized by the consumer to prevent brittle contracts.

## 4. Dynamic Identifier Enforcement (Contract ↔ Trigger Coupling)

**Context:** Messaging contracts originally pinned identifiers as hardcoded strings (`eventId: "log-444"`,
`executiveId: "exec-777"`). Those values are meaningless to consumers and make the contract brittle:
any real producer emits a UUID, so the contract asserted something production never satisfies.

**The coupling that makes this non-trivial.** A messaging contract is verified against the payload
emitted by its `triggeredBy('fireX()')` method in that producer's `BaseMessagingClass`. The contract
and the trigger are two halves of one assertion:

- contract `outputMessage.body` → what the generated producer test asserts
- `BaseMessagingClass.fireX()` → the JSON that test actually receives

Changing only the contract to `$(producer(regex('[a-f0-9]{8}-...')))` while the trigger still emits
`"log-444"` produces a **guaranteed producer-test failure**. Both sides must move together.

**Identifier fields in scope** (same 11 the central repo already uses, via `fix_ids.py`/`fix_ids2.py`):
`eventId`, `userId`, `customerId`, `executiveId`, `candidateId`, `transactionId`, `paymentId`,
`chatId`, `senderId`, `networkOrderId`, `itemId`.

Explicitly **out of scope** — these are numeric or semantic, not identity, and regex-ing them would
destroy the contract's meaning: `orderId`, `restaurantId`, `campaignId`, `localOrderId`, `amount`,
`cost`, `totalAmount`, `type`, `status`, `message`.

**Replacement UUIDs are deterministic**, derived `uuid5(NAMESPACE_OID, <old literal>)`, keyed on the
old literal *alone*. This is deliberate: `"exec-777"` appears as `executiveId` in
DeliveryExecutiveApplication and GovernmentIDValidationService and as `candidateId` in
MapsIntegration. Keying on the literal keeps it the same UUID in all three, so cross-service
identity survives the rewrite and reruns are idempotent.

**Run the validator (never grep — it cannot see the contract/trigger pairing):**

```bash
python3 FoodDeliveryContracts/sync_messaging_ids.py --check
```

**Expected Outcome:** exits `0`. It fails (exit `1`) if any of the following hold:
- a messaging `.groovy` still binds an in-scope identifier to a string literal instead of a matcher;
- a `BaseMessagingClass` trigger payload still emits a non-UUID value for an in-scope identifier;
- a contract declares a `triggeredBy('fireX()')` whose method does not exist in that producer's
  `BaseMessagingClass` (the failure mode that silently produces an uncompilable generated test);
- a contract's `sentTo(...)` destination is not registered in that base class's `@EmbeddedKafka`
  topics **and** is not served by a direct in-memory publish (see the Redis note below).

**Known caveat (documented, not enforced):** these producer tests pin the *schema* of a hand-written
payload; they do not exercise the service's real production publish path. The value is that the
stubs consumers test against are generated from this schema. `tracking:order:{orderId}` is a Redis
Pub/Sub channel, not a Kafka topic — a colon is not a legal Kafka topic character — so it is fed
into the verifier by a direct in-memory publish. That validates the payload structure only, never
the Redis transport.
