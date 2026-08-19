# SubPhase 4B: Financials Kafka Validations

## Objective
Replace empty `@AutoConfigureStubRunner` shell tests in the financial domains with actual assertions.

## Target Implementations
1. **`WalletService`**
   - `LedgerResponseConsumerTest.java`: Trigger `ledger-events` and assert wallet transaction state.
   - `BillingEventConsumerTest.java`: Trigger billing events and assert wallet deductions.
   - `LedgerFailureConsumerTest.java`: Assert compensatory actions on ledger failure.
   - `TopupEventConsumerTest.java`: Assert wallet balance increase.

2. **`LedgerService`**
   - `LedgerEventListenerTest.java`: Trigger `wallet-events` and assert immutable ledger append.

3. **`PaymentGatewayIntegration`**
   - `OrderEventConsumerTest.java`: Assert payment trigger on order creation.

## Steps
1. Trigger the financial mock events via `stubTrigger`.
2. Wait for async processing.
3. Assert that Wallet Balances and Ledger Append-Only structures are strictly correct (Zero tolerance for financial errors).
