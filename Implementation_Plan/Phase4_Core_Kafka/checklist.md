# Phase 4: Kafka Async Event Contracts (Core) - Checklist

**Status: producer side COMPLETE.** Consumer-side work moved to Phase 5 (realignment) and
Phase 6 (assertions), because it cannot be done meaningfully against the current contract shape.

## Done (verified by test run, 2026-08-19)

- [x] Messaging dependencies present in all Kafka producer applications.
- [x] `BaseMessagingClass.java` with `triggeredBy` methods in all 8 producers.
- [x] Map the core Kafka topics to producer projects. -> 17 contracts across 8 producers.
- [x] Contracts for `order-events`, `chat-events`, `wallet-events`, `ledger-events`, `ad-events`,
      `platform.notifications.dispatch` (CustomerApplication, 6 tests green).
- [x] Contracts for `payment-events` (PaymentGatewayIntegration, 1 green).
- [x] Contracts for `restaurant-events`, `menu-events` (RestaurantApplication, 2 green).
- [x] Contract for `platform.logistics.dispatch` (DeliveryExecutiveApplication, 2 green incl. Redis).
- [x] Contracts for `ad-billing-events`, `ad-tracking-events` (UserTrackingService, 2 green).
- [x] Contract for `order-events` / `DISPATCH_CANDIDATE_FOUND` (MapsIntegration, 1 green).
- [x] Contract for `delivery-executive-events` (GovernmentIDValidationService, 1 green).
- [x] Contracts for `ondc-order-created` and `ondc-settlement-event` (ONDCIntegrationService, 2 green).
- [x] **Redis Pub/Sub** contract for `tracking:order:{orderId}` asserting the real
      `TelemetryEventRequest` shape. Fed by an in-memory direct publish because a colon is not a
      legal Kafka topic character - validates payload schema only, never the Redis transport.
- [x] Replace hardcoded identifiers with regex matchers in all contracts **and** their trigger
      payloads. Enforced by `sync_messaging_ids.py --check`.

**Producer totals: 17 tests, 0 failures** - DeliveryExecutive 2, ONDC 2, Maps 1, Payment 1,
Customer 6, Restaurant 2, UserTracking 2, GovID 1.

## Harness defects fixed to get there (all pre-existing, none had ever run)

- [x] `@TestConfiguration` does not stop Boot's config search - promoted `TestConfig` to
      `@SpringBootConfiguration` so producers stop booting the whole service on H2.
- [x] `application-contract-test.yml` had `datasource`/`jpa`/`flyway` indented under `feign:` -
      `spring.flyway.enabled=false` was dead config.
- [x] Pinned `auto-offset-reset: earliest`; the default silently dropped the triggered message.
- [x] Pinned String (de)serializers; UserTracking's `JsonSerializer` double-encoded the payload.
- [x] Removed `<skip>true</skip>` from ONDC, which owns contracts and was never verifying them.
- [x] Dropped `contractsMode REMOTE` + `contractsRepositoryUrl` + `contractDependency` from
      BiddingEngine / UserTrackingService / WalletService (Maven plugin cannot take a spaced path).

## Moved out of this phase

- [ ] ~~Ensure all 25 `@KafkaListener` consumers have tests~~ -> **Phase 6**.
      Tests already exist 1:1 with the 25 listeners, but **all 25 have zero assertions and swallow
      exceptions**, so coverage is nominal only.
- [ ] ~~Verify consumer tests assert on side-effects~~ -> **Phase 6**, blocked by **Phase 5**.
