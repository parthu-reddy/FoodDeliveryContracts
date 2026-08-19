# Phase 7: Kafka Edge Cases - Validation

## 1. Outbox header enforcement

Script: parse every contract produced via the outbox; assert each declares
`header('eventType', ...)`. Separately parse `OutboxProcessor` and assert the `send(...)` call
passes a `ProducerRecord`/`Message` carrying headers rather than the bare
`send(topic, key, payload)` form.

Expected outcome: exits `0`. Baseline today: fails on **every** outbox contract and on
`OutboxProcessor` itself.

## 2. Enum fallback verification

Script: for each enum in `CommonLibrary/.../enums`, assert either an `UNKNOWN` constant or a
`@JsonEnumDefaultValue`-annotated member exists.

Expected outcome: exits `0`. Baseline: passes only for `FaultType`.

Behavioural check: deserialize `{"gateway":"NEW_PROVIDER_XYZ"}` into the DTO and assert it maps to
`UNKNOWN` instead of throwing. A schema check alone cannot prove runtime tolerance.

## 3. Orphaned annotation sweeper

Script: for every class containing `@RetryableTopic` or `@DltHandler`, assert the same class also
contains `@KafkaListener`.

Expected outcome: exits `0`. Baseline: fails on `OrderSagaOrchestrator` (lines 92 and 438).

## 4. Header extraction consistency

Script: assert no consumer reads an event type directly from the JSON body
(`path("eventType")` / `get("eventType")`) outside `KafkaHeaderUtils`.

Expected outcome: exits `0` once the header fix lands. Until then the fallback inside
`KafkaHeaderUtils.extractEventType` is the only permitted body read.
