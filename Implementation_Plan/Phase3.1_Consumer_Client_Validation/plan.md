# Phase 3.1: Consumer Client Validation

## Objective
The primary goal of Phase 3 was to set up consumer contracts for service-to-service communication. While we successfully established the `StubRunner` configurations and proved that the stubs download properly (using `contextLoads()`), we missed actually testing the Feign client invocations. 

This phase focuses on fully validating that the Consumer's Feign clients match the Producer's generated HTTP stubs by writing programmatic assertions for each client.

## Scope
We will update or create the following tests to inject their respective Feign clients, invoke their methods, and assert the returned payloads:
1. **CustomerApplication**
   - Consumers: `AdvertisementClient`, `RestaurantClient`
2. **RestaurantApplication**
   - Consumers: `OrderClient`, `AdvertisementClient`, `DeliveryClient`
3. **DeliveryExecutiveApplication**
   - Consumer: `CustomerServiceClient`
4. **ONDCIntegrationService**
   - Consumers: `DeliveryServiceClient`, `RestaurantServiceClient`, `CustomerServiceClient`, `LedgerServiceClient`
5. **GovernmentIDValidationService**
   - Consumers: `DeliveryExecutiveClient`, `RestaurantServiceClient`, `IdentityServiceClient`
6. **BudgetLimitingService**
   - **Missing Test**: Create `BudgetLimitingContractConsumerTest.java`.
   - Consumer: `CampaignClient`
7. **CommunicationService**
   - Consumer: Raw `RestTemplate` (Must assert parsed RestTemplate payload).

## Methodology
For each service:
1. Auto-wire the relevant `@FeignClient` interfaces into the `*ContractConsumerTest` class.
2. Invoke the methods on these clients.
3. Assert that the responses match the predefined responses from the Groovy stubs we created in Phase 3.
4. If a client fails to parse a payload (e.g., mismatched data types or URLs), we will correct the Consumer's `@FeignClient` or DTOs.
