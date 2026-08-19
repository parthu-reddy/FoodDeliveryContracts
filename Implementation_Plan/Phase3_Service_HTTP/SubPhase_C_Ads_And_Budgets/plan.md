# SubPhase 3.1C: Ads & Budgets HTTP Validations

## Objective
Implement `@AutoConfigureWireMock` consumer validation tests for the Ads & Budgeting systems.

## Target Implementations
1. **`BudgetLimitingService`** (`BudgetLimitingContractConsumerTest.java`)
   - Mock and assert `CampaignClient` HTTP calls.

## Steps
1. Verify `spring-cloud-contract-wiremock` dependency in `pom.xml`.
2. Add `@AutoConfigureWireMock(port = 0)` to the test classes.
3. Stub the campaign metadata retrieval endpoint.
4. Call the budget evaluation logic.
5. Assert that the budget constraints are correctly applied based on the mocked HTTP response.
