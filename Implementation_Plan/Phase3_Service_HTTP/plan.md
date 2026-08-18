# Phase 3: Service-Specific API Contracts (HTTP) — Plan

## Objective
Establish HTTP contracts for direct service-to-service calls that are NOT part of the `CommonLibrary`. These are usually specialized edge integrations (like ONDC routing, Campaign specific calls, or Customer to Restaurant queries).

## 1. Producer Identification
Based on the `@FeignClient` scan, the following applications export service-specific APIs:
- `CustomerApplication` (Calls `RestaurantService`, `AdvertisementService`)
- `RestaurantApplication` (Calls `AdvertisementService`, `DeliveryService`, `OrderService`)
- `DeliveryExecutiveApplication` (Calls `CustomerService`)
- `PaymentService` (No outgoing internal calls currently tracked for CDC)
- `CommunicationService` (Calls `CustomerApplication`, `RestaurantApplication` via raw `RestTemplate`)
- `ApiGateway` (Passthrough, technically a consumer but we don't mock it for CDC usually, we test edge services)
- `LedgerService` (Standalone)
- `WalletService` (Standalone)
- `GovernmentIDValidationService` (Calls `IdentityService`, `RestaurantService`, `DeliveryExecutiveService`)
- `BudgetLimitingService` (Calls `CampaignService`)
- `ONDCIntegrationService` (Calls `LedgerService`, `CustomerService`, `RestaurantService`, `DeliveryService`)
- `CampaignService` (Consumer: `BudgetLimitingService`, `RestaurantApplication`)
- `BiddingEngine` (Consumer: `CustomerApplication`)

### Edge Case: RestTemplate Bypassing Feign
`CommunicationService` uses a standard `RestTemplate` to make internal calls to:
1. `http://customer-service/api/v1/internal/orders/{orderId}/participants`
2. `http://restaurant-service/api/v1/internal/restaurants/owner/{userId}/outlets`

Even though it bypasses `@FeignClient`, we MUST write contracts for these endpoints in `CustomerApplication` and `RestaurantApplication` because `CommunicationService` expects a specific JSON structure. In the consumer tests for `CommunicationService`, we will configure WireMock to mock these hostnames.

## 2. Defining Contracts (Producer Side)
For each of these producers, create `.groovy` files in `src/test/resources/contracts/`.

### Edge Case: ONDC Integration Client Names
The `ONDCIntegrationService` uses generic fallback names:
- `@FeignClient(name = "customer-service")`
- `@FeignClient(name = "restaurant-service")`
- `@FeignClient(name = "delivery-service")`

We must ensure that the `CustomerApplication` actually registers itself as `customer-service` in Eureka (and in its `spring.application.name`). If `CustomerApplication` is registered as `customer-app`, the CDC tests will still pass (because stubs don't check Eureka), but it will fail in production.

## 3. Correcting Known Feign Client Mismatches
According to the `CommonMistakesDocumentation`, there have been multiple instances of Feign Client name mismatches causing `503 Service Unavailable` errors.

1. **CampaignService -> PaymentService:**
   `CampaignService` used `@FeignClient(name = "payment-gateway-service")`, but the actual name is `payment-service`. The contract stub runner relies on the Feign client name matching the `stubrunner.ids` exactly (e.g., `com.fooddelivery:payment-service:+:stubs`). We must enforce that all Feign Client names perfectly match the `artifactId` of the target stub.

2. **GovernmentIDValidationService -> DeliveryService:**
   Used `deliveryexecutive` instead of `delivery-service`. 

**Action:** Phase 3 requires standardizing all `@FeignClient(name="...")` properties to precisely match the target microservice's `pom.xml` artifactId.

## 4. Consumer Setup
Update `application-test.yml` for all consuming services (like `ONDCIntegrationService`) to list the required stubs:
```yaml
stubrunner:
  ids: 
    - com.fooddelivery:customer-application:+:stubs
    - com.fooddelivery:restaurant-application:+:stubs
    - com.fooddelivery:delivery-executive-application:+:stubs
```
