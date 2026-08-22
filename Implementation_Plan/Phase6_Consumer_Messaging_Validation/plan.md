# Phase 6: Consumer Messaging Validation - Plan

> ## STATUS UPDATE — 2026-08-20: unblocked, in progress
>
> **No longer blocked.** Phase 5 is substantially complete, so the contracts now describe real event
> shapes and consumer tests written against them mean something.
>
> The original problem statement below — *"25 tests, zero assertions, every one swallows the
> failure"* — **is obsolete**:
>
> | Check | Then | Now |
> |---|---|---|
> | Vacuous consumer tests | 25 | **0** |
> | Messaging consumer tests examined | 25 | 12 |
> | Of those, meaningful (assert + verify + propagate) | 0 | **12** |
> | `validate_consumer_assertions.py` | 25/25 not meaningful | **0/12 not meaningful** |
>
> **The 21 assert-nothing tests were deleted, not fixed.** Each was verified to contain exactly one
> `@Test`, no assertion, no Mockito `verify`, and a swallowed exception — so removing them destroyed
> no verification. They also cost **41.8 minutes** of every build; two `CustomerApplication` stubs
> accounted for ~20 minutes each. The consumers they nominally covered are recorded in
> `RandomDocuments/claude/06_Phase6ConsumerTests/deleted-vacuous-tests.md`.
>
> ### Remaining work: 6 consumers with no test at all
>
> There are **24 `@KafkaListener` consumers** (excluding ReviewsService). 18 are referenced by their
> module's tests. These 6 are not:
>
> | Module | Consumer |
> |---|---|
> | `CampaignService` | `KafkaAnalyticsConsumer` |
> | `CommunicationService` | `RefundDecisionListener` |
> | `CustomerApplication` | `MenuCacheInvalidationListener` |
> | `CustomerApplication` | `OrderEventConsumer` |
> | `GovernmentIDValidationService` | `BrandCreatedEventListener` |
> | `PaymentGatewayIntegration` | `OrderEventConsumer` |
>
> `CustomerApplication/OrderEventConsumer` is the notable one — it handles the primary order flow and
> currently has no consumer-side verification.
>
> ### Before writing any of them, fix the shared-topic defect
>
> `KafkaMessageVerifier` does not drain its per-topic queue between tests, so on a shared topic one
> test can consume another's message. Four modules are already exposed, and two
> `CustomerApplication` contract tests fail because of it today. Writing more consumer tests on those
> topics will produce results that depend on execution order. See
> [Phase 5](../Phase5_Messaging_Realignment/plan.md) for the detail.
>
> ### Reference implementation
>
> `WalletService/src/test/java/com/fooddelivery/wallet/contract/WalletEarningsConsumerContractTest.java`
> — triggers a real contract stub, waits with Awaitility, asserts the consumer's observable effect.
> Every new test must be negative-control proven: revert the consumer and watch it fail. Do **not**
> invert with Mockito `never()` inside `await().untilAsserted` — that passes at t=0 and proves nothing.

---

## Original plan (2026-08-19) — retained for context

**Status at the time: blocked by Phase 5.** Do not start until the contracts describe real event
shapes.

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
