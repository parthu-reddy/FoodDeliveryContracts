# Phase 3: Service-Specific API Contracts (HTTP) - Checklist

**Status: 5 gaps open.** All 21 existing consumer tests pass; the gaps are tests that exist but do
not assert what this phase requires.

## Done (verified by test run, 2026-08-19)

- [x] Audit `@FeignClient(name=...)` values against target `artifactId` / `spring.application.name`.
- [x] Contracts in `CustomerApplication` for endpoints hit by ONDC, Delivery, Restaurant and
      CommunicationService (15 contracts incl. `getOrderParticipants`).
- [x] Contracts in `RestaurantApplication` for endpoints hit by ONDC, GovernmentID and
      CommunicationService (9 contracts incl. `getOwnerOutlets`).
- [x] `CustomerApplication` `CustomerContractConsumerTest` - asserts `RestaurantClient` +
      `AdvertisementClient` (4/4 green).
- [x] `CustomerApplication` `MapsContractConsumerTest` (1/1), `PaymentContractConsumerTest` (1/1),
      `WalletContractConsumerTest` (1/1).
- [x] `RestaurantApplication` `RestaurantContractConsumerTest` - asserts `OrderClient` +
      `DeliveryClient` (4/4 green).
- [x] `RestaurantApplication` `GovIdContractConsumerTest` - asserts `verifyGstin` +
      `verifyBrandBankAccount` (2/2 green). Required two new producer contracts, both asserting
      **202 Accepted** to match `BrandVerificationController`.
- [x] `DeliveryExecutiveApplication` `DeliveryExecutiveContractConsumerTest` - asserts
      `CustomerServiceClient` (3/3 green).
- [x] `DeliveryExecutiveApplication` `GovIdContractConsumerTest` (1/1 green).
- [x] `BudgetLimitingService` `BudgetLimitingContractConsumerTest` - asserts `CampaignClient` (1/1 green).
- [x] Fix pre-existing producer failure: `getVerificationSummary.groovy` expected
      `2023-01-01T00:00:00Z` while the base class mocks a time serialising as `2023-10-01T12:00Z`.
- [x] Fix pre-existing `spring-boot-maven-plugin` start/stop port collision blocking
      `GovernmentIDValidationService` install (per the documented Phase 3.1 resolution).

## Open

- [ ] **Gap 1 - CommunicationService RestTemplate.** Replace `contextLoads` in
      `ContractConsumerTest` and `CommunicationContractConsumerTest` with real assertions on
      `RestTemplate.getForEntity` to Customer `/api/v1/internal/orders/{orderId}/participants`
      and Restaurant `/api/v1/internal/restaurants/owner/{userId}/outlets`.
- [ ] **Gap 2 - GovernmentIDValidationService.** Assert the injected `DeliveryExecutiveClient` and
      `RestaurantServiceClient`; inject and assert `IdentityServiceClient`.
- [ ] **Gap 3 - ONDCIntegrationService.** Assert `CustomerServiceClient`, `DeliveryServiceClient`
      and `LedgerServiceClient` (only `RestaurantServiceClient` is currently exercised).
- [ ] **Gap 4 - RestaurantApplication.** Exercise the injected `AdvertisementClient` against the
      BiddingEngine `fetchAds` stub.
- [ ] **Gap 5 - CampaignService.** Create `CampaignContractConsumerTest` asserting
      `PaymentServiceClient`.
- [ ] Re-run the Phase 3 validator; every named client must be both injected **and** invoked.
