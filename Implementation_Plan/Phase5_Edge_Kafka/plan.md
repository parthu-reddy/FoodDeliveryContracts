# Phase 5: Kafka Async Contracts (Edge Cases & Headers) — Plan

## Objective
Address the complex Kafka asynchronous edge cases identified during the Schema Registry migration crosscheck. These edge cases involve custom Kafka headers, Spring `MessageBuilder` patterns, and Enum mappings which standard JSON validation might miss.

## 1. OutboxProcessor Header Injection
**Issue:** `BrandCreatedEventListener` expects an `@Header("eventType")` but the current `OutboxProcessor` does not inject it. `KafkaHeaderUtils.extractEventType()` currently falls back to reading the JSON payload, but this is a brittle pattern.
**CDC Solution:**
The Groovy contracts for any message produced by the `OutboxProcessor` MUST explicitly define the headers.
```groovy
outputMessage {
    sentTo('order-events')
    headers {
        header('eventType', 'ORDER_CREATED')
        header('kafka_messageKey', '12345')
    }
    body(...)
}
```
If a Consumer (like `BrandCreatedEventListener`) fails to start in the Stub Runner test because the header is missing, the contract has successfully caught the bug!

## 2. DelayedDispatchPoller Pattern
**Issue:** `DelayedDispatchPoller` in `DeliveryExecutiveApplication` directly builds a Spring `Message<String>` and sets headers manually rather than using the `OutboxProcessor`.
**CDC Solution:**
Create a separate contract test in `DeliveryExecutiveApplication` specifically for this poller. The `triggeredBy` method should invoke the Poller's scheduled task method to ensure the message is serialized and headers are attached exactly as they would be in production.

## 3. Enum Mapping and `UNKNOWN` Values
**Issue:** Java Enums currently lack `UNKNOWN` values, but messages from other systems (or future versions) might send an enum value that the current Consumer doesn't recognize.
**CDC Solution:**
We must write a specific "Negative Contract" (or Edge Case Contract) where the Producer emits an enum value like `NEW_FEATURE_ENUM`. The Consumer's Stub Runner test must prove that it handles this gracefully (e.g., mapping to `UNKNOWN` or ignoring it) rather than throwing an `IllegalArgumentException` and blocking the Kafka topic.

## 4. DLT and RetryableTopic
**Issue:** `OrderSagaOrchestrator` has an orphaned `@RetryableTopic` and `@DltHandler` that are not attached to a valid `@KafkaListener`.
**CDC Solution:**
Contracts don't test DLT functionality directly (that's the framework's job), but Consumer tests MUST verify that they can process the core message. We will manually clean up the orphaned annotations as part of this phase to ensure the codebase is clean.
