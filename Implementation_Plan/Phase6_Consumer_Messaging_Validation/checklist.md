# Phase 6: Consumer Messaging Validation - Checklist

**Blocked by Phase 5.** Contracts must describe real event shapes first, or every consumer will
reject the stub payload.

## Prerequisites - ALL DONE, pattern proven

- [x] Phase 5 complete: contracts and triggers aligned to real event classes.
- [x] Implement the sender so `stubTrigger.trigger()` reaches the embedded broker.
      `WalletService/src/test/java/com/fooddelivery/wallet/contract/KafkaStubMessageSender.java`
      implements `MessageVerifierSender<Message<?>>`, publishes the stub body to the destination
      topic and forwards contract headers (skipping Spring's internal `id`/`timestamp`).
      **Copy this class per service** - it is the piece whose absence forced the try/catch shells.
- [x] Decide context strategy -> **minimal context, not Testcontainers.**
      `@SpringBootConfiguration` + `@EnableAutoConfiguration(exclude = {DataSource, HibernateJpa,
      Redis, RedisRepositories, Flyway})` + `@Import(TheConsumer.class)` + `@MockBean` its
      collaborators. Assert with `verify(...)`. The full app does not boot on H2, and asserting the
      mock is a sharper signal than a repository read anyway.
- [x] Blocker removed fleet-wide: `spring-boot-maven-plugin` start/stop executions were failing
      `mvn install` in **18 poms** ("Failed to connect to MBean server at port 9001"), so fresh
      producer stubs could not be published at all. Verified safe to delete - there is no
      `maven-failsafe-plugin` and no `*IT.java` anywhere, so nothing ran against the booted app.
      Script: `FoodDeliveryContracts/remove_boot_start_stop.py`.
- [ ] Fix the wrong trigger labels (`trigger-order-created`, `trigger-unknown`, `trigger-ad-event`,
      `trigger-chat-event` - none are declared by any contract).
- [ ] Remove the `catch (Exception)` swallow from all 25 tests.

## Proven reference implementation

`WalletService/src/test/java/com/fooddelivery/wallet/contract/WalletEarningsConsumerContractTest.java`
- fires the producer's real `wallet_events_earnings` stub, and asserts `WalletService.credit(...)`
is called with `ChargeCategory.FOOD_COST`. **Negative control verified**: pointing the trigger at
`wallet_events_reversal` (a debit) fails the assertion, so the test genuinely observes the consumer.

Recipe for each remaining consumer:

1. Copy `KafkaStubMessageSender` into the service's test tree.
2. `@SpringBootTest(classes = TestConfig.class)` + `@ActiveProfiles("contract-test")` +
   `@AutoConfigureStubRunner(ids = "<producer artifact>:+:stubs", stubsMode = LOCAL)` +
   `@EmbeddedKafka(topics = {"<topic>"})`.
3. `TestConfig`: `@SpringBootConfiguration`, `@EnableAutoConfiguration(exclude = ...)`,
   `@Import(TheConsumer.class)`, beans for the sender and any `MeterRegistry`.
4. `@MockBean` every collaborator; `@Autowired StubTrigger`.
5. `stubTrigger.trigger("<contract label>")` then `await().untilAsserted(() -> verify(...))`.
6. **Run the negative control** before believing the result.

Note the producer must be `mvn install`-ed first: `stubsMode = LOCAL` resolves from `~/.m2`, and a
stale stub jar silently validates against an old contract. The jar held `wallet_events.groovy` long
after the contract had been split in two.

## SubPhase A - Order Fulfilment

- [ ] `CustomerApplication` `OrderEventConsumerTest` - assert order status transition.
- [ ] `CustomerApplication` `MenuCacheInvalidationListenerTest` - assert cache invalidation.
- [ ] `CustomerApplication` `PaymentEventConsumerTest`, `ChatRefundProcessorServiceTest`.
- [ ] `RestaurantApplication` `OrderEventConsumerTest` - assert restaurant order state.
- [ ] `DeliveryExecutiveApplication` `OrderEventConsumerTest` - assert logistics state.

## SubPhase B - Financials (zero tolerance for silent failure)

- [ ] `WalletService` `LedgerResponseConsumerTest`, `BillingEventConsumerTest`,
      `LedgerFailureConsumerTest`, `TopupEventConsumerTest`, `GenericWalletEventConsumerTest`.
- [ ] `LedgerService` `LedgerEventListenerTest` - assert append-only entry.
- [ ] `PaymentGatewayIntegration` `OrderEventConsumerTest`.

## SubPhase C - Ads & Tracking

- [ ] `CampaignService` `KafkaAnalyticsConsumerTest`.
- [ ] `BiddingEngine` `CampaignEventConsumerTest`.
- [ ] `BudgetLimitingService` `CampaignSyncConsumerTest`.

## SubPhase D - Edge Integrations

- [ ] `ONDCIntegrationService` `CatalogDeltaSyncServiceTest`, `ProactiveStatusPublisherTest`,
      `SearchEventProcessorTest`, `ConfirmEventProcessorTest`.
- [ ] `MapsIntegration` `DispatchEventConsumerTest`.
- [ ] `CommunicationIntegration` `NotificationEventConsumerTest`, `AdNotificationListenerTest`.
- [ ] `CommunicationService` `RefundDecisionListenerTest`.
- [ ] `GovernmentIDValidationService` `BrandCreatedEventListenerTest`.

## Close-out

- [ ] 25/25 tests assert a real effect; validator exits 0.
- [ ] Record mistakes and improvements; sync to `CommonMistakesDocumentation/ContractTesting/`.


## Coverage reality (measured 2026-08-19) — the "25 tests" is not 25 achievable tests

Mapping every `@KafkaListener` to its topic and checking whether a contract exists for it changes
the shape of this phase considerably.

### Done (4) — financially-critical consumers first

- [x] `WalletService` `WalletEarningsConsumerContractTest` — fires `wallet_events_earnings`,
      asserts `credit(..., FOOD_COST)`.
- [x] `WalletService` `AdBillingConsumerContractTest` — fires `ad_billing_events`,
      asserts `debit(..., ADVERTISER, 0.50, AD_IMPRESSION)`.
- [x] `LedgerService` `LedgerTransactionConsumerContractTest` — fires `ledger_events`, asserts
      `recordTransaction(..., PLATFORM, ..., RESTAURANT, 125.50, FOOD_COST)`. Also covers the
      Phase 7 header end to end: the contract asserts the `eventType` header and the listener
      resolves it via `KafkaHeaderUtils.extractEventType`.
- [x] `CustomerApplication` `PaymentEventConsumerContractTest` — fires `payment_events`, asserts the
      consumer clears its `has(orderId) && has(gatewayOrderId)` guard and looks up the intent.

All four negative-control verified.

### Not testable yet — `PaymentGatewayIntegration` `OrderEventConsumer`

It only handles `PAYMENT_REFUND_REQUESTED`, and no contract exists for that event on `order-events`.
Add the producer contract first (Phase 5 work). It is otherwise well written — it tolerates both the
flat and enveloped shapes, unlike the four defective consumers.

### Blocked — consumer is defective, cannot assert success until fixed (3)

These consumers cannot process their own producer's real payload. Writing a passing test would mean
asserting the broken behaviour.

- `WalletService` `TopupEventConsumer` — requires a `payload` envelope; `payment-events` is flat.
  **Advertiser wallet top-ups are never credited.**
- `ONDCIntegrationService` `ConfirmEventProcessor` — reads `transactionId`/`bppUri` at the root in
  camelCase; real payload is `context.transaction_id` snake_case.
- `BiddingEngine` `CampaignEventConsumer` — guard `root.has("eventType") && root.has("payload")` is
  never true against a flat `Campaign`.

### Blocked — no producer contract exists for the topic (5)

CDC needs a contract to trigger. These topics have none, and writing them is Phase 5 work:

| Listener | Topic |
|---|---|
| `ONDCIntegrationService` `SearchEventProcessor` | `ondc.search.request` |
| `ONDCIntegrationService` `ProactiveStatusPublisher` | `ondc.order.status.changed` |
| `ONDCIntegrationService` `CatalogDeltaSyncService` | `ondc.catalog.delta` |
| `WalletService` `LedgerFailureConsumer` | `ledger-events-dlq` |
| `WalletService` `LedgerResponseConsumer` | `LEDGER_TRANSACTION_REPLY` |

### Achievable now (15)

`CustomerApplication` OrderEventConsumer / PaymentEventConsumer / MenuCacheInvalidationListener /
ChatRefundProcessorService; `RestaurantApplication` OrderEventConsumer;
`DeliveryExecutiveApplication` OrderEventConsumer; `PaymentGatewayIntegration` OrderEventConsumer;
`LedgerService` LedgerEventListener; `MapsIntegration` DispatchEventConsumer;
`CommunicationIntegration` NotificationEventConsumer / AdNotificationListener;
`CommunicationService` RefundDecisionListener; `CampaignService` KafkaAnalyticsConsumer;
`BudgetLimitingService` CampaignSyncConsumer; `GovernmentIDValidationService`
BrandCreatedEventListener.

Caveat: several of these may turn out to be defective too — three of the first five consumers
examined were. Expect the achievable count to fall as each is traced.

**Revised phase scope: 2 done, 15 achievable, 8 blocked.** The blocked 8 are not this phase's work:
3 need consumer fixes (tracked separately) and 5 need producer contracts.
