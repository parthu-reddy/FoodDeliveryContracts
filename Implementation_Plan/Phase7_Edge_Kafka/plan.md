# Phase 7: Kafka Edge Cases - Headers, Enums, Dead Annotations - Plan

> ## STATUS UPDATE — 2026-08-20: complete
>
> - **eventType/aggregateType headers — done.** `CommonLibrary/OutboxProcessor` now publishes via a
>   `ProducerRecord` carrying `HEADER_EVENT_TYPE` and `HEADER_AGGREGATE_TYPE`, instead of the bare
>   `kafkaTemplate.send(topic, key, payload)` it used before. Verified in the source.
> - **Orphaned annotations — done.** The `@RetryableTopic`/`@DltHandler` pair sitting on a *publisher*
>   in `CustomerApplication.OrderSagaOrchestrator` was removed; the class had no `@KafkaListener` at
>   all, so the DLT handler was unreachable.
> - **Enum fallbacks — CANCELLED, deliberately.** The original premise ("an unrecognised enum value
>   blocks a partition") is false: `CommonLibrary/KafkaConfig` registers a global
>   `DefaultErrorHandler` with 3 retries and a `DeadLetterPublishingRecoverer`. Adding an `UNKNOWN`
>   fallback to financial enums would convert safe quarantine into silent mis-booking. Not doing it
>   is the correct outcome, not an omission.
>
> ### Related item still open
>
> `ONDCIntegrationService.SearchEventProcessor` carries `@RetryableTopic(attempts = "5")` and a
> `@DltHandler`, but its body catches `Exception` and does **not** rethrow — so the retries never
> happen and the DLT is unreachable. The annotations advertise durability the code does not provide.
> ONDC is parked, so this is recorded rather than fixed; see
> `ONDCIntegrationService/UNIMPLEMENTED_FOR_ONDC/`.

---


Formerly `Phase5_Edge_Kafka`. Renumbered so the plan runs in dependency order; the content is
unchanged in intent, but every claim below was **re-verified against the codebase on 2026-08-19**
and all four are still outstanding.

## 1. OutboxProcessor does not inject the `eventType` header - CONFIRMED

`OutboxProcessor` line 49 publishes with:

```java
kafkaTemplate.send(topic, event.getAggregateId(), event.getPayload()).get();
```

No headers at all. `KafkaHeaderUtils.extractEventType(headers, jsonPayload)` therefore always falls
through to reading `eventType` out of the JSON body:

```java
return headerEventType != null ? headerEventType : jsonEventType;
```

That fallback is load-bearing today, and it is brittle - `BrandCreatedEventListener` declares
`@Header("eventType")`, which cannot be satisfied by a body field.

**Fix:** inject `eventType` (and `kafka_messageKey`) as real Kafka headers in `OutboxProcessor`,
then assert them in every outbox-produced contract:

```groovy
outputMessage {
    sentTo('order-events')
    headers {
        header('eventType', 'ORDER_CREATED')
    }
    body(...)
}
```

**Sequencing:** this overlaps Phase 5 step 3. If Phase 5 rewrites triggers to publish through the
outbox, do the header fix there and treat this item as verification only.

## 2. DelayedDispatchPoller builds its own Message - CONFIRMED

`DelayedDispatchPoller` in `DeliveryExecutiveApplication` constructs a Spring `Message<String>` and
sets headers by hand rather than going through `OutboxProcessor`, so it is a second, divergent
publishing path. It needs its own contract whose trigger invokes the poller's scheduled method.

## 3. No enum fallback - CONFIRMED

Only `FaultType` declares an `UNKNOWN` constant. No `@JsonEnumDefaultValue` exists anywhere in
`CommonLibrary`. A producer adding an enum value (e.g. `PaymentGateway.STRIPE`) would throw
`IllegalArgumentException` in every consumer and block the partition.

**Fix:** add `@JsonEnumDefaultValue` + `UNKNOWN` to the cross-service enums, then write a negative
contract that emits an unrecognised value and prove the consumer degrades instead of dying.

## 4. Orphaned retry annotations - CONFIRMED

`OrderSagaOrchestrator` has `@RetryableTopic` at **line 92** and `@DltHandler` at **line 438**, and
the file contains **no `@KafkaListener`**. Both are dead: `@RetryableTopic` only takes effect on a
listener method. Remove them, or attach them to the real listener if retry was intended.
