# Phase 3: Service-Specific API Contracts (HTTP) - Plan

> ## STATUS UPDATE — 2026-08-20: complete
>
> `validate_phase3_consumers.py` reports **0 files with problems** (was 6). Every HTTP consumer test
> that injected a Feign client now actually invokes it, and the `contextLoads`-only shells are gone.
>
> `audit_http_contracts.py` additionally reports **30 HTTP contracts, 0 needing attention**, and
> `validate_contract_base_coverage.py` passes — every contract's controller is mounted by its
> module's test base.
>
> **Related work happened outside this plan.** Nine HTTP contracts were found to be *untrue* — they
> asserted fields that did not exist on the DTOs they described — and were corrected under
> `HttpContractRemediation/Phase1_ContractTestHarness/`. That effort also found that two modules'
> `ContractTestBase` mounted only one controller each, so every contract for any other controller
> returned 404 from an empty dispatcher, which read as a missing endpoint. Worth reading before
> assuming a 404 here means an API gap.
>
> One contract is deliberately **pending**: `getDeliveryStatus.groovy` is marked `ignored()`, which
> generates a `@Disabled` test. It specifies an endpoint ONDC needs that does not exist yet. Removing
> `ignored()` is the switch that turns it back into a live test. See
> `ONDCIntegrationService/UNIMPLEMENTED_FOR_ONDC/`.

---


Absorbs the former `Phase3.1_Consumer_Client_Validation` and `Phase3.1_Consumer_Validations`
folders, which duplicated this scope.

## Objective

Contracts and consumer validation for service-to-service HTTP calls that are **not** exported via
`CommonLibrary` - specialised edge integrations (ONDC routing, ads, Customer to Restaurant queries)
plus `CommunicationService`'s raw `RestTemplate` calls.

## What "done" means here

Phase 3's original pass only proved `contextLoads()` - stubs downloaded but the Feign clients were
never invoked. A consumer validation counts as done only when it:

1. injects the `@FeignClient` (or `RestTemplate`),
2. **invokes** the method against the stub, and
3. asserts on the returned payload.

Injection without invocation is the failure mode that made this phase look finished when it was not.
Four tests still sit at `contextLoads` with clients injected and unused.

## Implementation note: WireMock vs StubRunner

The original checklist specified `@AutoConfigureWireMock`. The implemented approach uses
`@AutoConfigureStubRunner` with `stubsMode = LOCAL`, which resolves stub jars from `~/.m2` and
starts WireMock internally. No service declares `spring-cloud-contract-wiremock`. This is a
deliberate substitution, not a gap - but it means **producers must be `mvn install`-ed** before
their consumers can be tested.

## Remaining work

All five gaps are unblocked: the producer contract each one needs already exists.

| # | Consumer test | Missing |
|---|---|---|
| 1 | `CommunicationService` `ContractConsumerTest` + `CommunicationContractConsumerTest` | both are `contextLoads` only; the raw `RestTemplate` calls to Customer `/participants` and Restaurant `/outlets` are unasserted |
| 2 | `GovernmentIDValidationService` `GovIdContractConsumerTest` | injects `DeliveryExecutiveClient` + `RestaurantServiceClient`, asserts neither; `IdentityServiceClient` not injected |
| 3 | `ONDCIntegrationService` `ONDCContractConsumerTest` | injects 4 clients, asserts only `RestaurantServiceClient` |
| 4 | `RestaurantApplication` `RestaurantContractConsumerTest` | `AdvertisementClient` injected but never exercised |
| 5 | `CampaignService` | no consumer test exists at all (`PaymentServiceClient`) |

## Producer contracts available to assert against

- Customer `/api/v1/internal/orders/{id}/participants` -> `CustomerApplication/.../getOrderParticipants.groovy`
- Restaurant `/api/v1/internal/restaurants/owner/{id}/outlets` -> `RestaurantApplication/.../getOwnerOutlets.groovy`
- Delivery `/api/v1/internal/admin/delivery/drivers/{id}` -> `DeliveryExecutiveApplication/.../internal/getDriverById.groovy`
- Ledger `/api/v1/ledger/orders/{id}/total` -> `LedgerService/.../getOrderLedgerAmount.groovy`
- Identity `/api/v1/internal/auth/initiate` -> `IdentityService/.../initiate-login.groovy`
- Ads `/api/v1/ads/serve` -> `BiddingEngine/.../fetchAds.groovy`
- Payment `/api/v1/payments/create-order` -> `PaymentGatewayIntegration/.../payment/create-order.groovy`
