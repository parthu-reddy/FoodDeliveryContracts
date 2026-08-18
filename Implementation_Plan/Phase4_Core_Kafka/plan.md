# Phase 4: Kafka Async Event Contracts (Core) — Plan

## Objective
Establish messaging contracts for the core asynchronous event streams (Kafka topics). This replaces the need for the Schema Registry by validating the JSON payload structure at build time using Spring Cloud Contract Messaging.

## 1. Producer Identification
Based on the Kafka crosscheck report (`crosscheck_report_v2.md`), the core event producers are:
- `CustomerApplication` (Produces to `order-events`, `chat-events`)
- `PaymentService` (Produces to `payment-events`)
- `RestaurantApplication` (Produces to `restaurant-events`, `menu-events`)
- `DeliveryExecutiveApplication` (Produces to `platform.logistics.dispatch`)
- `UserTrackingService` (Produces to `ad-billing-events`, `ad-tracking-events`)
- `CommonLibrary` (Outbox dynamically produces: `notification-events`, `platform.notifications.dispatch`, `wallet-events`, `ledger-events`, `ad-events`)
- `MapsIntegration` (Produces to `order-events` for DISPATCH_CANDIDATE_FOUND)
- `GovernmentIDValidationService` (Produces to `delivery-executive-events`)
- `ONDCIntegrationService` (Produces to `ondc-order-created`, `ondc-settlement-event`, `ondc-search-request`, `ondc-callback-dlq`)

## 2. Defining Messaging Contracts (Producer Side)
For each producer, create `.groovy` files using the `message` block instead of the HTTP `request/response` block.

### Example: Order Created Contract (`order-created.groovy` in CustomerApplication)
```groovy
org.springframework.cloud.contract.spec.Contract.make {
    description("Should send order events")
    label("order_created")
    input {
        triggeredBy('createOrderEvent()')
    }
    outputMessage {
        sentTo('order-events')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "ORDER_CREATED",
            payload: [
                orderId: 12345
            ]
        ])
    }
}
```

## 3. Postel's Law (Robustness Principle)
The contracts MUST only enforce the fields that consumers strictly require. For example, if a consumer only needs `orderId` and `totalAmount`, the contract should not fail if `restaurantId` is missing, UNLESS the producer guarantees it will always be there.
Since we have multiple consumers for `order-events` (e.g., `RestaurantApplication`, `LedgerService`), the contract must represent the intersection of all mandatory fields required by all consumers.

## 4. Setting up Spring Cloud Contract Messaging
1. **Producer Side:** Requires adding the `spring-cloud-stream-test-support` or specific Spring Kafka test utilities depending on the messaging framework used. We need to create a base test class that implements the `triggeredBy` methods (e.g., `fireOrderCreatedEvent()`) by directly calling the `OutboxProcessor` or `KafkaTemplate`.
2. **Consumer Side:** The `@AutoConfigureStubRunner` will automatically intercept the Kafka listeners and inject the mocked JSON message when the consumer test is run.
