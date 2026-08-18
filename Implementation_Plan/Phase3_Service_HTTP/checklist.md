# Phase 3: Service-Specific API Contracts (HTTP) — Checklist

- [ ] Audit all `@FeignClient(name="...")` values in non-CommonLibrary services.
- [ ] Compare each Feign Client name against the target service's `spring.application.name` (usually in `application.yml` or `bootstrap.yml`).
- [ ] Fix any misnamed clients (e.g., `payment-gateway-service` -> `payment-service`).
- [ ] Write contracts in `CustomerApplication` for the endpoints hit by ONDC, Delivery, Restaurant, and CommunicationService (`/api/v1/internal/orders/{id}/participants`).
- [ ] Write contracts in `RestaurantApplication` for the endpoints hit by ONDC, GovernmentID, and CommunicationService (`/api/v1/internal/restaurants/owner/{id}/outlets`).
- [ ] Implement JUnit `@AutoConfigureWireMock` test in `CustomerApplication` asserting the `RestaurantClient` and `AdvertisementClient` HTTP calls.
- [ ] Implement JUnit `@AutoConfigureWireMock` test in `RestaurantApplication` asserting the `AdvertisementClient`, `DeliveryClient`, and `OrderClient` HTTP calls.
- [ ] Implement JUnit `@AutoConfigureWireMock` test in `DeliveryExecutiveApplication` asserting the `CustomerServiceClient` HTTP calls.
- [ ] Implement JUnit `@AutoConfigureWireMock` test in `GovernmentIDValidationService` asserting the `IdentityServiceClient`, `RestaurantServiceClient`, and `DeliveryExecutiveClient` HTTP calls.
- [ ] Implement JUnit `@AutoConfigureWireMock` test in `BudgetLimitingService` asserting the `CampaignClient` HTTP calls.
- [ ] Implement JUnit `@AutoConfigureWireMock` test in `ONDCIntegrationService` asserting the `LedgerServiceClient`, `CustomerServiceClient`, `RestaurantServiceClient`, and `DeliveryServiceClient` HTTP calls.
- [ ] **RestTemplate Edge Case:** Implement JUnit `@AutoConfigureWireMock` test in `CommunicationService` asserting the raw `RestTemplate.getForEntity` calls made to `CustomerApplication` and `RestaurantApplication`.
