# Phase 7: Kafka Edge Cases - Findings

## CRITICAL: `KafkaHeaderUtils.extractEventType` is header-first, and that is unsafe here

`extractEventType` returns `headerEventType != null ? headerEventType : jsonEventType`. Now that
`OutboxProcessor` actually sets the header, **migrating a consumer to this helper can change
behaviour**, because at least one producer sets a header and a body that disagree:

`AdminOrderManualController` (CustomerApplication) publishes to `wallet-events` with

- body `"eventType": "REVERSAL_GENERATED"` -> `GenericWalletEventConsumer` **debits**
- outbox `EventType.REFUND_GENERATED`     -> `GenericWalletEventConsumer` **credits**

Switching that consumer to header-first would silently turn a refund reversal into a credit. Real
money, wrong direction, no error.

**Rule:** on any topic where a producer sets both, resolve **body first, header as fallback** until
producers are reconciled. That is strictly additive - existing paths behave identically, and only
messages that previously had no resolvable event type start being handled.

Reconciling the producers (so header and body always agree) is a prerequisite before
`extractEventType` can be adopted anywhere. Until then, treat it as unsafe on `wallet-events`.

## Fixed: EARNINGS_GENERATED credits were silently discarded

`GenericWalletEventConsumer` required `{eventType, payload}` and returned early otherwise.
`OrderActionService.emitEarningsGeneratedEvent` (called from `HandedOverState:58,67` on hand-over)
emits the payload **flat** with no body `eventType`, so every driver and restaurant earnings credit
was dropped with no error and no DLQ entry.

Two changes make it work:

1. `OutboxProcessor` now transmits the `eventType` it has always stored on the outbox row.
2. The consumer resolves the type body-first/header-fallback, and treats the root as the payload
   when there is no `payload` node.

Covered by `WalletService/src/test/java/com/fooddelivery/wallet/kafka/GenericWalletEventConsumerTest`:
one test proves the flat earnings payload now credits with `ChargeCategory.FOOD_COST`, the other
pins the reversal-still-debits behaviour so the header trap above cannot be reintroduced. Negative
control: removing the header from the first test fails it.

## Note: the header fix alone would not have fixed this

Worth recording because it was the initial assumption. `GenericWalletEventConsumer`'s listener
signature was `consumeWalletEvent(String message)` - it did not receive headers at all, and it also
required a `payload` node the flat producer never sends. Publishing the header was necessary but
not sufficient; the consumer needed both changes. Do not assume a transport fix reaches a consumer
that never asked for the data.

## Still open in this phase

- `DelayedDispatchPoller` builds its own `Message<String>` outside the outbox and needs its own contract.
- No enum fallback: only `FaultType` has `UNKNOWN`; no `@JsonEnumDefaultValue` anywhere.
- Orphaned `@RetryableTopic` (line 92) and `@DltHandler` (line 438) in `OrderSagaOrchestrator`,
  which contains no `@KafkaListener`.
