# Phase 5: Kafka Async Contracts (Edge Cases & Headers) — Checklist

- [ ] Audit `OutboxProcessor` in `CommonLibrary` to ensure it injects the `eventType` header. If it doesn't, patch it.
- [ ] Add `headers { header('eventType', '...') }` to all Groovy contracts generated in Phase 4.
- [ ] Write a dedicated Groovy contract in `DeliveryExecutiveApplication` for the `DelayedDispatchPoller`.
- [ ] Write a contract in `CustomerApplication` testing an unknown enum value for `ChannelType`.
- [ ] Update Consumer code across all microservices to catch `IllegalArgumentException` on enum parsing and fallback gracefully.
- [ ] Remove the orphaned `@RetryableTopic` and `@DltHandler` annotations in `OrderSagaOrchestrator.java` (lines 92 and 438).
- [ ] Ensure `KafkaHeaderUtils` is used consistently by all consumers to extract the event type from the header, not the JSON payload.
