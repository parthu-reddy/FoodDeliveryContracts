# Consumer-Driven Contract Testing — Implementation Plan

Single source of truth for CDC across the Food Delivery microservices. Every status below was
**measured on the date shown**, by running the validators and building each service — not carried
over from a checkbox.

**Last verified: 2026-08-20.** Scope: all microservices **except `ReviewsService`**, which is
in-flight work owned elsewhere and deliberately excluded from this audit.

> **The workspace changed shape since the previous revision.** The multi-module aggregator `pom.xml`
> at the workspace root **no longer exists**. It has been replaced by `FoodDeliveryParent/` — a
> dependency-management parent (`packaging: pom`, no `<modules>`) that **21 services now inherit
> from**. There is no reactor build any more; each service builds independently, and
> `FoodDeliveryParent` then `CommonLibrary` must be installed first.
>
> **This breaks CI.** `.github/workflows/ci-cd.yml` still runs `mvn clean install` from the workspace
> root, which now fails instantly with *"there is no POM in this directory"*. See
> [Phase 8](Phase8_CICD_And_Broker_Publish/).

## Phase status

| Phase | Scope | Status |
|---|---|---|
| [Phase1_Foundation](Phase1_Foundation/) | SCC deps, BOM, stub resolution | **Complete** |
| [Phase2_Core_HTTP](Phase2_Core_HTTP/) | Contracts for CommonLibrary Feign clients | **Complete** |
| [Phase3_Service_HTTP](Phase3_Service_HTTP/) | Service HTTP contracts + consumer validation | **Complete** — `validate_phase3_consumers` 0 problems (was 6) |
| [Phase4_Core_Kafka](Phase4_Core_Kafka/) | Messaging contracts + producer verification | **Complete** |
| [Phase5_Messaging_Realignment](Phase5_Messaging_Realignment/) | Contracts describe real event shapes | **Substantially complete** — 9 of 12 modules publish through the production path; 3 remain |
| [Phase6_Consumer_Messaging_Validation](Phase6_Consumer_Messaging_Validation/) | Real assertions for every consumer | **In progress** — 12 meaningful tests, 0 vacuous; 6 of 24 consumers untested |
| [Phase7_Edge_Kafka](Phase7_Edge_Kafka/) | eventType headers, orphaned annotations | **Complete** — enum-fallback item cancelled, see phase doc |
| [Phase8_CICD_And_Broker_Publish](Phase8_CICD_And_Broker_Publish/) | Publish stubs, gate CI | **Not started, now blocked** by the missing aggregator |

## Measured state, 2026-08-20

### Validators — all green

| Validator | Result |
|---|---|
| `validate_broker_url.py` | PASSED — all services resolve from `~/.m2` |
| `validate_contract_topics.py` | 0 contracts target a topic nothing publishes to |
| `sync_messaging_ids.py --check` | PASSED — identifiers use regex matchers |
| `audit_consumer_contract_shapes.py` | **0 consumers flagged** (was 3) |
| `validate_consumer_assertions.py` | **0 of 12 not meaningful** (was 28 of 37) |
| `validate_phase3_consumers.py` | **0 problems** (was 6) |
| `validate_vacuous_consumer_tests.py` | **0 vacuous** of 12 examined (was 21 of 37) |
| `validate_messaging_base_isolation.py` | PASSED — no autoconfig leakage |
| `audit_http_contracts.py` | 30 contracts, **0 need attention**, 1 `ignored()` pending |
| `validate_contract_base_coverage.py` | PASSED — every contract's controller is mounted |

### Contract inventory (excluding ReviewsService)

**30 HTTP + 34 messaging = 64 contracts** across 14 services. The messaging count has grown
substantially since the previous revision — `CampaignService` alone now carries 9.

### Consumer coverage

**24 `@KafkaListener` consumers. 18 are referenced by their module's tests; 6 are not:**

- `CampaignService/KafkaAnalyticsConsumer`
- `CommunicationService/RefundDecisionListener`
- `CustomerApplication/MenuCacheInvalidationListener`
- `CustomerApplication/OrderEventConsumer`
- `GovernmentIDValidationService/BrandCreatedEventListener`
- `PaymentGatewayIntegration/OrderEventConsumer`

Of the tests that do exist, **12 are meaningful** — they assert, verify, and propagate exceptions.
**None are vacuous.** That is the single biggest change since the previous revision: 21 assert-nothing
tests were deleted after being shown to verify nothing, and the consumers they nominally covered are
recorded in `RandomDocuments/claude/06_Phase6ConsumerTests/deleted-vacuous-tests.md`.

### Build state — measured 2026-08-20

Built individually in dependency order (`FoodDeliveryParent` → `CommonLibrary` → services), because
there is no aggregator any more. **19 of 21 pass. ReviewsService excluded from this audit.**

| Module | Result |
|---|---|
| FoodDeliveryParent, CommonLibrary, EurekaServer, ConfigService, ApiGateway, IdentityService, CommunicationIntegration, MapsIntegration, PaymentGatewayIntegration, RestaurantApplication, GovernmentIDValidationService, LedgerService, CommunicationService, ONDCIntegrationService, WalletService, BudgetLimitingService, BiddingEngine, CampaignService, UserTrackingService | **SUCCESS** (19) |
| CustomerApplication | **FAILURE** — 2 errors |
| DeliveryExecutiveApplication | **FAILURE** — 1 failure, 2 errors |

#### CustomerApplication — both failures are the shared-topic defect

```
validate_wallet_events_reversal          Missing property in path $['payload']
validate_order_payment_refund_requested  "receive" is null
```

Not contract errors. Two contracts share `wallet-events` and two share `order-events`, and the
verifier's per-topic queue is never drained between tests. See
[Phase 5](Phase5_Messaging_Realignment/plan.md).

#### DeliveryExecutiveApplication — one is a genuine consumer regression

```
delivery.MessagingTest.validate_order_status_updated              "receive" is null
delivery.contract.OrderEventConsumerContractTest                  Awaitility timeout
delivery.service.OrderEventConsumerTest.testConsumeEvent_Success  Wanted but not invoked
```

The third is a plain Mockito unit test with no stub runner involved, so infrastructure cannot explain
it:

```
Wanted but not invoked: mockAcceptedStrategy.process(<any>, "ORDER_ACCEPTED");
However, there was exactly 1 interaction with this mock: mockAcceptedStrategy.getEventTypes();
```

`OrderEventConsumer` constructs its strategy registry but never dispatches the event to it — so
delivery-side `ORDER_ACCEPTED` handling is not running. The other two failures are consistent with the
same cause. **This needs investigation before anything else in this plan**; it is a live behaviour
change, not a test problem.

## What changed since 2026-08-19

The previous revision's central claim — *"the messaging suite currently proves nothing"* — **no longer
holds.** It was accurate then and is obsolete now:

- Messaging contracts describe real payloads; `audit_consumer_contract_shapes` finds no mismatches.
- 9 of 12 messaging base classes drive a real production publish path (`publishViaOutbox`, the real
  `OutboxProcessor`, or a real controller) rather than hand-written JSON.
- The 25 assert-nothing consumer tests are gone.

Nine **HTTP** contracts were also found to be untrue and corrected during this period — asserting
fields that did not exist on the DTOs they described. Details in
`HttpContractRemediation/Phase1_ContractTestHarness/`.

## Related plans

This plan covers CDC. Two adjacent efforts have their own folders:

- `HttpContractRemediation/` — the five services whose HTTP contract tests were failing
- `RandomDocuments/claude/` — the prioritised backlog and `DECISIONS_NEEDED.md` (14 open decisions)
- `BiddingEngine/REVIEW/` — an architecture review of the ad-serving path
- `ONDCIntegrationService/UNIMPLEMENTED_FOR_ONDC/` — ONDC is parked; what must be built to unpark it
