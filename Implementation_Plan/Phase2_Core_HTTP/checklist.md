# Phase 2: Internal Core API Contracts (HTTP) - Checklist

**Status: COMPLETE** (verified 2026-08-19)

Contracts for the Feign clients exported by `CommonLibrary`:

- [x] `WalletService` -> `contracts/get-wallet.groovy` (`/api/v1/wallets/{entityType}/{entityId}`).
      Added late: the contract had existed only in the central broker, never locally.
- [x] `PaymentService` -> `contracts/payment/create-order.groovy`.
- [x] `MapsIntegration` -> `contracts/mapsintegration/reverse-geocode.groovy`.
- [x] `IdentityService` -> `contracts/identity-service/initiate-login.groovy`.
- [x] `GovernmentIDValidationService` -> `getVerificationSummary.groovy`,
      `brandVerifyGstin.groovy`, `brandVerifyBankAccount.groovy`.
- [x] `@FeignClient(path=...)` prefixes match contract URLs. -> `validate_phase2_paths.py` exits 0.
- [x] Producer verification generates and passes. -> e.g. GovID `ContractVerifierTest` **3/3 green**.
- [x] `CustomerApplication` runs Feign tests against the `WalletService` stub.
      -> `WalletContractConsumerTest` **1/1 green**.

## Moved out of this phase

- [ ] ~~Push the generated stubs to the Git broker~~ -> moved to **Phase 8**.
      Deliberately deferred: the central broker holds **30** contracts against **48** local, and
      Phase 5 is about to change the shape of roughly a third of them. Publishing now would
      entrench the wrong schema in the place consumers read from.
