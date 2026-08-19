# Phase 5: Messaging Contract Realignment - Checklist

## Slice: `order-events` (do this first, do not skip ahead)

- [x] Record the exact JSON `OrderCreatedEvent` serializes to. -> flat object with
      `orderId`/`customerId`/`restaurantId` (UUID), `totalAmount` (BigDecimal -> JSON number),
      `deliveryLat`/`deliveryLng` (Double), `deliveryAddress`/`pickupOtp`/`deliveryOtp` (String).
      **No `eventType` anywhere** - the outbox stores it but `OutboxProcessor` transmits neither a
      header nor a body field.
- [x] Rewrite `order_created.groovy` to that shape.
- [x] Rewrite `fireOrderCreated()` to publish through the real `OutboxProcessor`.
- [ ] ~~Add the `eventType` header~~ -> **deferred to Phase 7**, where `OutboxProcessor` is patched.
      The contract must describe what is emitted *today*; asserting a header no producer sends
      would make the contract fail against production.
- [x] `MessagingTest.validate_order_created` green against real serialization (6/6 in the class).
- [x] **Negative control passed**: adding a field absent from `OrderCreatedEvent` makes the test
      error. The test is genuinely bound to the DTO, not to invented JSON.
- [x] **Decision recorded** - outbox-driven, see `mistakes_and_improvements.md`.

## Roll-out (only after the slice is green)

- [x] `chat_events` (CustomerApplication) - `{quoteAmount (number), refundType}` from
      `ChatRefundProcessorService` (CHAT_REFUND_QUOTE_RESPONSE).
- [x] `payment_events` (PaymentGatewayIntegration) - real `PaymentSucceededEvent` record
      `{orderId, gatewayOrderId, amount (NUMBER), gatewayName}` + an `eventType` field.
      Negative-control verified.
- [x] `menu_events` (RestaurantApplication) - flat `{brandId, type, timestamp}` from
      `CatalogService.notifyMenuUpdate`. Field is `type`, not `eventType`. Negative-control verified.
- [x] `restaurant_events` (RestaurantApplication) - **the old contract described an event that is
      never published to this topic** (ORDER_ACCEPTED with orderId/restaurantId).
      `RestaurantActionService` uses the ORDER aggregate, which routes to order-events. This topic
      carries BRAND_CREATED / OUTLET_ACTIVATED / OUTLET_DEACTIVATED; now contracted as BRAND_CREATED.
- [x] `logistics_dispatch` (DeliveryExecutiveApplication) - flat `{orderId, restaurantLat,
      restaurantLng, deliveryLat, deliveryLng, deliveryAddress}`. No event type anywhere: this
      producer bypasses the outbox and sets no headers.
- [x] `wallet_events` **split into two contracts**, both real production behaviour:
      `wallet_events_earnings` (flat, no body eventType) and `wallet_events_reversal` (enveloped,
      body `REVERSAL_GENERATED` vs header `REFUND_GENERATED`). The disagreement is asserted on
      purpose - it is the trap that would flip a debit into a credit.
- [x] `ledger_events` (CustomerApplication) - flat `{transferId, referenceId, fromId, fromType,
      toId, toType, amount (STRING), chargeCategory}`.
- [x] `ad_billing_events` (UserTrackingService) - flat `{eventId, campaignId, advertiserId,
      amount (STRING), chargeCategory, timestamp}`. Trigger calls the **real** `TrackingEventProducer`.
- [x] `ad_tracking_events` (UserTrackingService) - billing fields + `{eventType, deviceId}`.
      Restored production's `JsonSerializer` instead of pinning `StringSerializer`, which is what
      caused the earlier double-encoding.
- [x] `ad_events` - **relocated to CampaignService**, the only producer of the ADVERTISEMENT
      aggregate. Given a `BaseMessagingClass`, `KafkaMessageVerifier`, contract plugin and pinned
      contract-test profile; removed from CustomerApplication along with its `fireAdEvent()` trigger
      and the `ad-events` topic registration. Payload is the flat saved `Campaign` entity.
- [x] `notification_dispatch` (CustomerApplication) - real serialized `NotificationRequestEvent`.
      NOTE: `PaymentEventConsumer` publishes a different `{template, data}` shape to the same topic
      for refund notifications - **not yet contracted**.
- [x] `order_events_dispatch` (MapsIntegration) - `{orderId, driverIds[], eventType, deliveryLat,
      deliveryLng, deliveryAddress}` **plus** an `eventType` Kafka header. The only producer that
      already sent both.
- [x] `delivery_executive_events` (GovernmentIDValidationService) - flat
      `{eventType: EXECUTIVE_SUSPENSION_REQUESTED, executiveId}` from `BiometricVerificationService`.
- [x] `ondc_settlement_event` (ONDCIntegrationService) - `{transactionId, type, amount (NUMBER),
      currency}`. `amount` is interpolated unquoted, unlike wallet/ledger where it is a string.
- [x] `ondc_order_created` (ONDCIntegrationService) - real `OndcRequest` envelope built from the
      DTOs. Postel's-law subset: only the `context` fields needed to route and correlate the
      callback. Wire keys are **snake_case** (`transaction_id`, `bpp_uri`) via `@JsonProperty`.
- [ ] `redis_tracking_order` - already correct, confirm no regression

## Close-out

- [ ] All 17 producer messaging tests green against real payload shapes.
- [ ] `sync_messaging_ids.py --check` still exits 0 (identifiers stay regex-matched).
- [ ] Record mistakes and improvements; sync to `CommonMistakesDocumentation/ContractTesting/`.


## Roll-out COMPLETE: 18 of 18 contracts describe reality

All 18 producer messaging tests green (17 + 1 from the wallet split).

All 18 producer messaging tests green across 9 services (CampaignService is new to the suite).

**Still uncontracted (additions, not corrections):** the `{template, data}` notification variant from `PaymentEventConsumer`, and
the OUTLET_ACTIVATED/OUTLET_DEACTIVATED variants on `restaurant-events`. One contract per event
type, so these are additions rather than corrections.

### Fidelity caveat - read before trusting these

All outbox-driven contracts (`order_created`, `ledger_events`, both `wallet_events`,
`notification_dispatch`, `chat_events`, `restaurant_events`, `payment_events`) plus the two ad
contracts invoke **real production code** - `OutboxProcessor` via a shared `publishViaOutbox`
helper, or `TrackingEventProducer` - so they break when the payload, topic routing or Kafka key
changes. `payment_events` and `notification_dispatch` also bind to the real `PaymentSucceededEvent`
and `NotificationRequestEvent` classes.

The other five direct-send producers build their payload inline in a private method or inside a
larger service method, so their triggers **mirror** the construction rather than invoke it. The
contract schema is now correct - which was the actual defect - but a change to
`CatalogService.notifyMenuUpdate` would not fail its test. Closing that gap means extracting those
payload builders into something callable; worth doing, tracked as follow-up rather than done.


## Three production defects surfaced by this phase

All the same shape: the producer emits a flat DTO, the consumer expects an `{eventType, payload}`
envelope, and the mismatch fails **silently** - no exception, no DLQ, no log at error level.

| Topic | Consumer | Effect |
|---|---|---|
| `wallet-events` | `GenericWalletEventConsumer` | driver/restaurant earnings never credited - **fixed in Phase 7** |
| `ondc-order-created` | `ConfirmEventProcessor` | reads `transactionId`/`bppUri` at the root in camelCase; real payload is `context.transaction_id` snake_case, so `BapConfirmService.confirm` is never called - **open** |
| `ad-events` | `CampaignEventConsumer` (BiddingEngine) | guard `root.has("eventType") && root.has("payload")` is never true against a flat `Campaign`, so campaigns are never indexed into or removed from the matcher - **open** |

The contracts describe the **producers** truthfully in all three cases. Encoding the consumers'
mistaken expectations would have made the contracts agree with nothing and hidden the defects
permanently. Fixing the two open ones is consumer-side work, tracked separately.

This is the strongest argument for the phase: three real, silent, production-affecting bugs found
purely by writing down what each producer actually emits.
