# Phase 4: Kafka Async Event Contracts (Core) — Checklist

- [ ] Add Spring Cloud Contract Messaging dependencies to all Kafka Producer applications.
- [ ] Create `BaseMessagingClass.java` in the test directory of each Producer to hold the `triggeredBy` trigger methods.
- [ ] Map the 14 core Kafka topics to their respective Producer projects.
- [ ] Write Groovy contracts for `order-events` and `chat-events` (CustomerApplication).
- [ ] Write Groovy contracts for `payment-events` (PaymentService).
- [ ] Write Groovy contracts for `restaurant-events` and `menu-events` (RestaurantApplication).
- [ ] Write Groovy contracts for `platform.logistics.dispatch` (DeliveryExecutiveApplication).
- [ ] Write Groovy contracts for `ad-billing-events` and `ad-tracking-events` (UserTrackingService).
- [ ] Write Groovy contracts for `wallet-events`, `ledger-events`, `ad-events`, `platform.notifications.dispatch` (Triggered via CommonLibrary Outbox).
- [ ] Write Groovy contracts for `order-events` specifically for `DISPATCH_CANDIDATE_FOUND` (MapsIntegration).
- [ ] Write Groovy contracts for `delivery-executive-events` (GovernmentIDValidationService).
- [ ] Write Groovy contracts for ONDC specific topics like `ondc-order-created`, `ondc-settlement-event` (ONDCIntegrationService).
- [ ] **Redis Pub/Sub:** Write a messaging contract in `DeliveryExecutiveApplication` for the `tracking:order:{orderId}` Redis channel, asserting the `TelemetryEventRequest` JSON structure.
- [ ] Ensure all 25 `@KafkaListener` consumers have corresponding JUnit tests annotated with `@AutoConfigureStubRunner`.
- [ ] Verify that consumer tests correctly assert on the side-effects of receiving the mock Kafka message (e.g., Database state changes, outgoing HTTP calls).
