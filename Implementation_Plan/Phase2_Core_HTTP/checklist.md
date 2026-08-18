# Phase 2: Internal Core API Contracts (HTTP) — Checklist

- [ ] Identify all API endpoints exposed by `WalletService` that are consumed by the `WalletServiceClient` in `CommonLibrary`.
- [ ] Create `src/test/resources/contracts/wallet/` in `WalletService` and write `.groovy` files for each endpoint.
- [ ] Repeat the process for `PaymentService`.
- [ ] Repeat the process for `MapsIntegration`.
- [ ] Repeat the process for `IdentityService`.
- [ ] Repeat the process for `GovernmentIDValidationService`.
- [ ] Ensure all `@FeignClient(path = "...")` prefixes in `CommonLibrary` match the URL prefixes in the written contracts.
- [ ] Ensure `spring-cloud-starter-contract-verifier` generates the mock Spring MVC tests successfully for each producer (`mvn clean test`).
- [ ] Push the generated stubs to the Git broker.
- [ ] Configure `CustomerApplication` to download and run its Feign client tests against the `WalletService` stub.
