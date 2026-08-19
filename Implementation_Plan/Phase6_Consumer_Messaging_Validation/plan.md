# Phase 6: Consumer Messaging Validation - Plan

**Status: blocked by Phase 5.** Do not start until the contracts describe real event shapes.

## The problem

There are exactly **25 `@KafkaListener`** annotations across the fleet and exactly **25 messaging
consumer tests**. Coverage looks complete. It is not:

> All 25 tests contain **zero assertions**, and every one wraps the trigger in a
> `catch (Exception)` that swallows the failure.

Each is a variation of:

```java
@Test
public void testConsumerIsWorking() {
    try {
        stubTrigger.trigger("trigger-order-created");
    } catch (Exception e) {
        System.out.println("Trigger failed, which might be expected ...");
    }
}
```

Three separate defects in four lines:

1. **The label does not exist.** Contracts declare `label("order_created")`; the tests trigger
   `"trigger-order-created"`. Nothing is ever fired.
2. **The exception is swallowed**, so defect 1 is invisible.
3. **Nothing is asserted**, so even a delivered message proves nothing.

## The second blocker: the trigger cannot reach Kafka

`stubTrigger.trigger(label)` routes through a `MessageVerifierSender`. The current
`KafkaMessageVerifier.send(...)` throws `UnsupportedOperationException("Not implemented for
producer tests")` in all 8 copies. Even with the right label, no message would be delivered - which
is the real reason the try/catch exists.

This phase must implement the sender before any assertion can work.

## Approach

### Step 1 - consumer-side sender (do once, reuse everywhere)

Implement `send(payload, headers, destination, contract)` to publish to the embedded broker via
`KafkaTemplate`, mirroring the receive side. The producer-side `UnsupportedOperationException` can
stay for genuinely producer-only paths, but the consumer path needs a real implementation.

### Step 2 - context strategy

These tests need the **real consumer bean**, unlike producer tests. The full application context
does not boot on H2 (`entityManagerFactory` fails; `CREATE EXTENSION postgis` is unsupported).
Two options, decide on evidence:

- **Minimal context** (preferred): a `@SpringBootConfiguration` importing only the consumer class,
  with `@MockBean` for its collaborators. Assert via `verify(collaborator)`. All 6 constructor deps
  of `OrderEventConsumer` are mockable.
- **Testcontainers PostgreSQL**: real schema, real Flyway, real repository assertions. Higher
  fidelity, slower; `testcontainers` is already a CommonLibrary dependency.

### Step 3 - assert per subphase

Group as before: A Order Fulfilment, B Financials, C Ads & Tracking, D Edge Integrations.

## Definition of done

A consumer test counts only when it fires the **correct** label, does **not** swallow exceptions,
and asserts an observable effect - a repository write, a mock interaction, or an outgoing call.
