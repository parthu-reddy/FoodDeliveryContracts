# SubPhase 3.1A: Core Domains HTTP Validations

## Objective
Implement `@AutoConfigureWireMock` consumer validation tests for the core tri-party actors: Customer, Restaurant, and Delivery Executive.

## Target Implementations
1. **`CustomerApplication`** (`CustomerContractConsumerTest.java`)
   - Mock and assert `RestaurantClient` calls (e.g. fetching restaurant outlets).
   - Mock and assert `AdvertisementClient` calls.

2. **`RestaurantApplication`** (`RestaurantContractConsumerTest.java`)
   - Mock and assert `OrderClient` calls.
   - Mock and assert `DeliveryClient` calls.
   - Mock and assert `AdvertisementClient` calls.

3. **`DeliveryExecutiveApplication`** (`DeliveryExecutiveContractConsumerTest.java`)
   - Mock and assert `CustomerServiceClient` calls.

## Steps
1. Verify `spring-cloud-contract-wiremock` dependency in `pom.xml`.
2. Add `@AutoConfigureWireMock(port = 0)` to the test classes.
3. Write `stubFor(get(urlEqualTo(...)).willReturn(aResponse()...))` configurations matching the Groovy contracts.
4. Execute the targeted Feign Client method.
5. Assert that the response from the Feign client matches the stubbed response.
