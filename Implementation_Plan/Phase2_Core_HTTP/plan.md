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
> **CORRECTED 2026-08-19.** This section originally stated that contracts *cannot* live in the
> producer's local `src/test/resources/contracts` folder and must be written only in the central
> repository. That is **false**, and following it will waste your time.
>
> In the implemented system, local contracts are the source of truth for producer verification:
> the `spring-cloud-contract-maven-plugin` reads `src/test/resources/contracts` and generates the
> producer tests from it. All 48 contracts live locally, and all producer verification runs from
> them. The central `META-INF/groupId/artifactId/version/contracts/` layout is the **publication**
> format consumers resolve stubs from - it is a mirror, not the origin.
>
> The two are currently out of sync (48 local vs 30 central); reconciling and automating that
> publication is **Phase 8**.
>
> Related constraint: the plugin's `contractsRepositoryUrl` cannot point at a path containing a
> space, so a `REMOTE` producer mode against this workspace is not usable at all (see Phase 1).

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

## 5. ONDC Integration Exclusions
`ONDCIntegrationService` has local Feign clients for `ledger-service`, `customer-service`, `restaurant-service`, and `delivery-service`. These should NOT be migrated in Phase 2 because they are not exported via `CommonLibrary`. They belong in Phase 3 (Service-Specific APIs).
