# Phase 5: Messaging Contract Realignment - Plan

> ## STATUS UPDATE — 2026-08-20: substantially complete
>
> The problem described below **has been fixed**, and this section supersedes the original status.
> Measured, not assumed:
>
> | Check | Result |
> |---|---|
> | `audit_consumer_contract_shapes.py` | **0 consumers flagged** (was 3) |
> | `validate_contract_topics.py` | 0 contracts target a topic nothing publishes to |
> | `sync_messaging_ids.py --check` | PASSED — identifiers use regex matchers, not literals |
> | Messaging contracts (excl. ReviewsService) | **34**, up from ~20 |
>
> **9 of 12 messaging base classes now publish through a real production path** — `publishViaOutbox`,
> a real `OutboxProcessor`, or a real controller — rather than hand-writing the JSON the contract
> asserts. That was the phase's actual acceptance criterion, and it is the part that mattered: fixing
> the contract body alone would only have moved the fiction.
>
> ### The 3 that still hand-write their payload
>
> | Module | Current trigger style |
> |---|---|
> | `GovernmentIDValidationService` | raw `kafkaTemplate.send(...)` |
> | `MapsIntegration` | raw `kafkaTemplate.send(...)` |
> | `UserTrackingService` | neither — no publish call found in the base class |
>
> These are the remaining Phase 5 work. A trigger that hand-writes JSON proves only that the contract
> agrees with itself.
>
> ### NEW DEFECT found during this audit — shared-topic queue cross-talk
>
> `CustomerApplication` now **fails two messaging contract tests**:
>
> ```
> validate_wallet_events_reversal        PathNotFoundException: Missing property in path $['payload']
> validate_order_payment_refund_requested NullPointerException: "receive" is null
> ```
>
> Neither is a contract error. `KafkaMessageVerifier` keeps **one queue per topic and never drains it
> between tests** — there is no `@BeforeEach` reset, only `poll()`. As soon as a module has two
> contracts on the same topic, one test can consume the other's message: the first gets the wrong
> shape, the last finds the queue empty.
>
> **Four modules are exposed**, and the risk grows as contracts are added:
>
> | Module | Shared topics |
> |---|---|
> | `CampaignService` | `ad-events` ×9 |
> | `CustomerApplication` | `order-events` ×2, `wallet-events` ×2 |
> | `BudgetLimitingService` | `ad-events` ×2 |
> | `PaymentGatewayIntegration` | `payment-events` ×2 |
>
> **Fix:** drain the verifier's queues in a `@BeforeEach` on the base class (the verifier needs a
> `reset()`), or key messages by correlation id rather than topic alone. Until then, contract results
> on a shared topic depend on test execution order — which means a green run is not evidence.
>
> This is now the highest-priority item in this phase, ahead of the remaining 3 modules.

---

## Original plan (2026-08-19) — retained for context

**Status at the time: not started. Highest priority - this is the only phase where the current state
actively misleads.**

## The problem

Every messaging contract describes an event shape that does not exist in production.

Contracts assert:

```
{ eventId, type, payload: { orderId: 1001, restaurantId: 501, ... } }
```

Production emits a flat serialized DTO. `OrderCreatedEvent` is:

```
{ orderId: UUID, customerId: UUID, restaurantId: UUID, totalAmount, deliveryLat, deliveryLng,
  deliveryAddress, pickupOtp, deliveryOtp }
```

and `OutboxProcessor` publishes it with `kafkaTemplate.send(topic, aggregateId, payload)`.

Consumers read those fields at the **root**. `CustomerApplication.OrderEventConsumer` does
`rootNode.path("orderId")` then `UUID.fromString(...)`; `RestaurantApplication` reads
`orderId`, `restaurantId`, `deliveryLat`, `deliveryOtp`, `itemsJson`; `WalletService` reads
`entityId`, `entityType`, `amount`, `chargeCategory`. None of them look inside a `payload` object,
and none would parse `1001` as a UUID.

Fed a current stub, `OrderEventConsumer` logs `"Missing orderId or eventType. Ignored."` and does
nothing.

## Why the producer tests pass anyway

Each `triggeredBy('fireX()')` method hand-writes a JSON text block, and the contract asserts that
same invented JSON. The test is a closed loop that never touches production serialization. It is
green and it proves nothing - which is worse than red, because a breaking change to
`OrderCreatedEvent` would leave the whole suite green.

**Rewriting the contract body alone does not fix this.** As long as the trigger hand-writes the
payload, the fiction just moves. The trigger must publish through the real production path.

## Approach: one vertical slice, then roll out

Do not rewrite 17 contracts on spec. Prove the pattern on `order-events` first - the saga backbone,
the busiest topic, the most consumers. This mirrors the process that made the Phase 4 harness work
tractable: prove on one service, then script the rest.

### Slice steps (CustomerApplication / `order-events`)

1. Rewrite `order_created.groovy` to mirror `OrderCreatedEvent` exactly: flat, UUID
   `orderId`/`customerId`/`restaurantId`, `totalAmount` as a number.
2. Rewrite `fireOrderCreated()` to publish through the **real** path - persist an `OutboxEvent` and
   let `OutboxProcessor` emit it - instead of `kafkaTemplate.send(topic, handWrittenJson)`.
3. Add the `eventType` Kafka header the contract should assert (see Phase 7, which this overlaps).
4. Confirm `MessagingTest.validate_order_created` still passes, now against real serialization.

### Known unknown

How cleanly `OutboxProcessor` can be driven from a test context is **not yet established**. It needs
a JPA repository and a scheduler. If persisting an outbox row proves impractical in the minimal
producer context, the fallback is to serialize the real DTO with the application's `ObjectMapper`
(`objectMapper.writeValueAsString(OrderCreatedEvent.builder()...build())`) - which still binds the
contract to the real class and breaks when a field changes, though it does not exercise the outbox.
Decide this on evidence from the slice, and record it.

## Roll-out after the slice

Map each contract to its real source type, then apply the proven pattern:

| Topic | Real payload source |
|---|---|
| `order-events` | `OrderCreatedEvent` / `OrderPaidEvent` |
| `payment-events` | `PaymentSucceededEvent`, `PaymentFailedEvent`, `PaymentRefundedEvent` |
| `platform.notifications.dispatch` | `NotificationRequestEvent` |
| `wallet-events`, `ledger-events` | Outbox payloads read by `WalletService` / `LedgerService` consumers |
| `restaurant-events`, `menu-events` | Fields read by `RestaurantApplication.OrderEventConsumer` |
| `platform.logistics.dispatch` | `DelayedDispatchPoller`'s `Message<String>` |
| `ad-*` | `UserTrackingService` producers |
| `ondc-*` | `ONDCIntegrationService` producers |
| `tracking:order:{orderId}` | `TelemetryEventRequest` - **already correct**, done in Phase 4 |

## Scope note

`redis_tracking_order.groovy` is the one contract already derived from the real DTO, and can serve
as the reference example.
