# Phase 5: Messaging Realignment - Decisions and Findings

## Decision: outbox-driven trigger (slice proved it viable)

The plan left open whether triggers should drive `OutboxProcessor` or just serialize the real DTO.
**Outbox-driven won**, and it was cheaper than expected.

The obstacle was assumed to be JPA: driving the outbox seemed to need a DataSource, the
`outbox_events` table and the scheduler, none of which exist in the minimal producer context (and
CustomerApplication's entities do not boot on H2). The way through is that **persistence is not
part of the contract**. Mock only `OutboxEventRepository`, hand the real `OutboxProcessor` the real
`KafkaTemplate`, and call `processOutboxEvents()` directly:

```java
OutboxEventRepository repo = Mockito.mock(OutboxEventRepository.class);
Mockito.when(repo.findTop100ByStatusInOrderByCreatedAtAsc(anyList()))
       .thenReturn(new ArrayList<>(List.of(outboxEvent)));
new OutboxProcessor(repo, kafkaTemplate).processOutboxEvents();
```

### What this now catches that the text-block version could not

- a field added to, removed from or renamed on `OrderCreatedEvent`;
- a type change (e.g. `orderId` UUID -> String) breaking the regex matcher;
- a change to `getTopicForAggregateType` routing `ORDER` somewhere other than `order-events`;
- a change to the Kafka message key (`aggregateId`).

### What it still does not cover - stated so nobody over-trusts it

- the outbox table write and the `@Scheduled` cadence (repository mocked, method called directly);
- retry/DLQ behaviour on send failure;
- other event types on `order-events` (`ORDER_PAID`, `DRIVER_ASSIGNED`, ...) which have *different*
  payload shapes and need their own contracts.

## Finding: `eventType` never reaches the wire

`OrderSagaOrchestrator` sets `eventType` on the outbox entity, but `OutboxProcessor` publishes with
`kafkaTemplate.send(topic, aggregateId, payload)` - no headers - and `OrderCreatedEvent` has no
`eventType` field. So the value is persisted and then dropped.

This is why `KafkaHeaderUtils.extractEventType` falls back to reading `eventType` out of the JSON
body, and why `BrandCreatedEventListener`'s `@Header("eventType")` cannot be satisfied.

The contract deliberately does **not** assert an `eventType` header today - a contract must describe
what is actually emitted. Phase 7 patches `OutboxProcessor`; the header assertion lands with it.

## Mistake caught during the slice: assuming the ObjectMapper

The trigger initially serialized with `new ObjectMapper()` while production uses the **injected**
one. For `OrderCreatedEvent` the two agree (no date types, no custom bean, no `spring.jackson.*`
properties - all verified), so the test passed either way. Passing for a reason you have not checked
is exactly the failure mode this phase exists to remove, so the trigger now `@Autowired`s the same
mapper. Reasoning that a difference "would not matter here" is not verification.

## Process note: always run the negative control

`validate_order_created` was green *before* realignment too - against invented JSON. Green is not
evidence. The check that mattered was injecting a field absent from the DTO and confirming the test
errors. Do this for every topic in the roll-out; a realigned contract whose trigger still hand-writes
JSON will look identical in the report and prove nothing.

---

# Roll-out findings (in progress)

## The roll-out is NOT mechanical - each topic needs tracing

The `order-events` slice suggested a repeatable pattern. Tracing the next few topics disproved that
assumption: real producers disagree with each other on the same topic, and two genuine defects
surfaced within the first three contracts examined. Trace every topic to its producing code; do not
pattern-match from a sibling contract.

## FINDING 1 (production defect): EARNINGS_GENERATED is silently dropped

`wallet-events` carries **two incompatible shapes from the same service**:

| Producer | Shape | Consumed? |
|---|---|---|
| `OrderActionService.emitEarningsGeneratedEvent` (`:205`) | flat `{entityId, entityType, amount, referenceId, description, metadata}` | **NO - dropped** |
| `AdminOrderManualController` (`:239`) | enveloped `{eventType, payload:{...}}` | yes |

`GenericWalletEventConsumer:40` is `if (!root.has("eventType")) return;`, then reads
`root.get("payload")`. It explicitly handles `"EARNINGS_GENERATED"` at line 44 - but only enveloped.
The flat payload has no root `eventType`, so the consumer returns early and the event vanishes with
no error and no DLQ.

The outbox row *does* carry `.eventType(EventType.EARNINGS_GENERATED)`; `OutboxProcessor:49`
(`send(topic, aggregateId, payload)`, no headers) drops it in transit.

**Impact:** driver and restaurant earnings, emitted from `HandedOverState:58,67` on hand-over, are
never credited to wallets through this path.

**Do not "fix" this by writing the contract to match the broken producer.** The contract should
describe what the consumer requires; the resulting red producer test *is* the bug report. The fix
is a production change (envelope the payload, or land Phase 7's `eventType` header) and is tracked
separately - it is financial code and needs an explicit decision.

## FINDING 2 (misplaced contract): `ad_events` sits in the wrong service

`ad_events.groovy` lives in `CustomerApplication`, but `AggregateType.ADVERTISEMENT` is produced
only by `CampaignService`. CustomerApplication has a `fireAdEvent()` trigger for a topic it never
publishes to, so the contract and its stub attribute the event to the wrong producer. Relocating it
means giving CampaignService a `BaseMessagingClass`, topic registration and a verifier.

Verified placements for the rest: `wallet_events`, `ledger_events`, `notification_dispatch` and
`chat_events` *are* produced by CustomerApplication (CHAT_SESSION also by CommunicationService).

## Confirmed real payload shapes so far

- **`order-events` / ORDER_CREATED** - flat `OrderCreatedEvent`. **Done.**
- **`ledger-events`** - flat `{transferId, referenceId?, fromId, fromType, toId, toType,
  amount (STRING, not number), chargeCategory?}` from `OrderActionService:53-66`.
- **`wallet-events`** - two shapes, see Finding 1.
- **`ad-billing-events`** - `BillingEventConsumer:33-42` reads `eventId`, `advertiserId`, `amount`,
  `chargeCategory` at the **root**. The current contract's
  `{eventId, type, payload:{campaignId, cost}}` matches none of it.

Note `amount` is repeatedly a **string** (`amount.toString()`), not a JSON number. Contracts must
match that or the consumer's `new BigDecimal(node.asText())` path diverges from what is asserted.

## MY OWN MISTAKE: the ONDC contracts asserted a topic that does not exist

Both ONDC contracts were written with `sentTo('ondc-order-created')` and
`sentTo('ondc-settlement-event')` — hyphens. `OndcKafkaConfig` declares
`ondc.order.created` and `ondc.settlement.event` — **dots**.

The tests passed anyway, because the trigger hardcoded the same wrong literal:

```java
kafkaTemplate.send("ondc-order-created", transactionId, ...);   // wrong, matched the contract
```

Contract and trigger agreed with each other and with nothing in production. This is exactly the
closed loop this phase exists to eliminate, reintroduced by me while eliminating it.

**Why the other contracts were immune:** every one whose trigger goes through production code was
protected for free. The outbox contracts get their topic from
`OutboxProcessor.getTopicForAggregateType`; `menu_events` and `order_events_dispatch` use
`KafkaConstants.TOPIC_*`; the ad contracts call the real `TrackingEventProducer`. Only the two
where I typed a string literal drifted.

**Rule:** a trigger must never contain a topic string literal. Use the constant the producer uses
(`KafkaConstants.TOPIC_*`, `OndcKafkaConfig.TOPIC_*`), so a rename breaks compilation instead of
silently passing.

**Guard added:** `FoodDeliveryContracts/validate_contract_topics.py` asserts every contract's
`sentTo` destination is a topic some production file actually publishes to. It resolves `TOPIC_*`
constants and bare literals across all `src/main/java`, and skips Redis Pub/Sub channels. Currently
18/18 OK. Run it after adding or editing any messaging contract.

**Wider lesson:** the "trigger mirrors production instead of invoking it" caveat recorded earlier
was not theoretical. It produced a real defect within the same session it was written down. Prefer
invoking production code; where that is impossible, at minimum share its constants.
