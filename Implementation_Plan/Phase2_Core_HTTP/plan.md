# Phase 2: Internal Core API Contracts (HTTP) — Plan

## Objective
Establish HTTP contracts for all synchronous Feign clients exported via the `CommonLibrary`. These are core domain services called by almost every other microservice.

## 1. Producer Identification
Based on the `@FeignClient` scan in `CommonLibrary`, the following Producers must define contracts:
- `WalletService` (Path: `/api/v1/wallets`)
- `PaymentService`
- `MapsIntegration`
- `IdentityService`
- `GovernmentIDValidationService`

## 2. Defining Contracts (Central Git Repository)
Because Phase 1 enforced a `REMOTE` Git broker architecture, contracts CANNOT be written in the local producer's `src/test/resources/contracts` folder. They will be ignored.

Instead, the `.groovy` contracts MUST be written directly in the centralized `FoodDeliveryContracts` repository under the strict `META-INF/groupId/artifactId/version/contracts/` directory structure.

For example, WalletService contracts must be placed at:
`/META-INF/com.fooddelivery/wallet-service/1.0-SNAPSHOT/contracts/`

### Example: WalletService Contract (`wallet-balance.groovy`)
```groovy
import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should return wallet balance for valid customer")
    request {
        method 'GET'
        // CRITICAL EDGE CASE: WalletClient uses `@FeignClient(path = "/api/v1/wallets")`
        // We MUST include this prefix in the contract URL.
        url('/api/v1/wallets/customers/12345/balance')
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            customerId: "12345",
            balance: 500.00
        ])
    }
}
```

## 3. Producer Test Base Classes
To generate valid Spring MockMvc tests from the Groovy contracts, every producer MUST define a Base Test Class (e.g., `WalletContractBase.java`) that mocks or initializes the web context.
The `spring-cloud-contract-maven-plugin` configuration in the `pom.xml` MUST be updated to include `<baseClassForTests>`.

## 4. Consumer Integration
Any service that imports `CommonLibrary` and injects `WalletServiceClient` (e.g., `CustomerApplication`) will use `@AutoConfigureStubRunner`.

### 4.1 Resolving Bean Name Collisions
**Edge Case identified in `CommonMistakesDocumentation`:** If `CommonLibrary` exports `@FeignClient(name="wallet-service")` and a Consumer accidentally defines its own interface with the same name, Spring throws `ConflictingBeanDefinitionException`. 
**Action:** Audit all consumers and delete local duplicate Feign clients. Consumers MUST use the shared `CommonLibrary` interface to guarantee the contract matches the stub.

## 4. ONDC Integration Exclusions
`ONDCIntegrationService` has local Feign clients for `ledger-service`, `customer-service`, `restaurant-service`, and `delivery-service`. These should NOT be migrated in Phase 2 because they are not exported via `CommonLibrary`. They belong in Phase 3 (Service-Specific APIs).
