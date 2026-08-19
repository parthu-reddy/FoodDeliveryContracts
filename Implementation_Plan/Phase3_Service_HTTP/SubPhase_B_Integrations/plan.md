# SubPhase 3.1B: Integrations HTTP Validations

## Objective
Implement `@AutoConfigureWireMock` consumer validation tests for integration services: ONDC, GovernmentID, and Communication.

## Target Implementations
1. **`ONDCIntegrationService`** (`ONDCContractConsumerTest.java`)
   - Mock and assert `LedgerServiceClient` calls.
   - Mock and assert `CustomerServiceClient` calls.
   - Mock and assert `RestaurantServiceClient` calls.
   - Mock and assert `DeliveryServiceClient` calls.

2. **`GovernmentIDValidationService`** (`GovIdContractConsumerTest.java`)
   - Mock and assert `IdentityServiceClient` calls.
   - Mock and assert `RestaurantServiceClient` calls.
   - Mock and assert `DeliveryExecutiveClient` calls.

3. **`CommunicationService`** (`ContractConsumerTest.java`)
   - Mock and assert raw `RestTemplate.getForEntity` calls to `CustomerApplication` and `RestaurantApplication`.

## Steps
1. Verify `spring-cloud-contract-wiremock` dependency in `pom.xml`.
2. Add `@AutoConfigureWireMock(port = 0)` to the test classes.
3. Stub the external proxy endpoints.
4. Call the service layer method that triggers the FeignClient or RestTemplate.
5. Verify the HTTP interactions using WireMock's `verify(...)`.
