# Phase 7: Kafka Edge Cases - Checklist

**Status: not started.** All four items re-verified as outstanding on 2026-08-19.

- [x] Patch `OutboxProcessor` to inject Kafka headers. Now builds a `ProducerRecord` and adds
      `eventType` + `aggregateType` as UTF-8 bytes (the format `KafkaHeaderUtils` already decodes).
      The partition key was already `aggregateId`, so no `kafka_messageKey` header is needed.
- [x] Add `headers { header('eventType', ...) }` to outbox-produced contracts. Done for
      `order_created` (asserts `eventType: ORDER_CREATED`, `aggregateType: ORDER`), negative-control
      verified. Remaining contracts gain it as Phase 5 converts each trigger to the outbox path.
- [x] Make consumers resolve the event type when the body lacks it - **but body-first, not
      header-first**. See `mistakes_and_improvements.md`: on `wallet-events` the header and body
      deliberately disagree, and header-first would convert a debit into a credit. Applied to
      `GenericWalletEventConsumer`, which also now accepts a flat payload. This repairs the
      silently-dropped `EARNINGS_GENERATED` credits.
- [ ] Audit the remaining consumers for the same envelope/flat split before migrating them.
- [ ] Write a dedicated contract for `DelayedDispatchPoller`, triggered via its scheduled method.
- [ ] Add `UNKNOWN` + `@JsonEnumDefaultValue` to cross-service enums (only `FaultType` has one).
- [ ] Write a negative contract emitting an unrecognised enum value; prove the consumer degrades
      gracefully rather than throwing `IllegalArgumentException`.
- [ ] Remove the orphaned `@RetryableTopic` (line 92) and `@DltHandler` (line 438) from
      `OrderSagaOrchestrator`, or attach them to a real `@KafkaListener`.
- [ ] Record mistakes and improvements; sync to `CommonMistakesDocumentation`.
