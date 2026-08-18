# Phase 5: Kafka Async Contracts (Edge Cases & Headers) — Validation

To rigorously crosscheck that Phase 5 was implemented correctly without missing edge cases, execute automated programmatic validations:

## 1. Automated Header Enforcement Verification
Run a Python validator to assert that every single Outbox event contract includes the `eventType` header constraint.
```python
# Execute: python3 scripts/enforce_outbox_headers.py
```
**Expected Outcome:** Script parses all Groovy contracts in the `contracts/` directory. If an Outbox contract is found without `header('eventType', ...)`, it throws a ValidationError and exits with code 1.

## 2. Programmatic Enum Fallback Verification
Run a strict Java AST parser across the `CommonLibrary` to ensure all deserialization mappings for core domain enums are wrapped in safety logic (like `@JsonEnumDefaultValue` or robust `try/catch` logic).
```python
# Execute: python3 scripts/verify_enum_deserialization.py
```
**Expected Outcome:** Script ensures Consumer applications will never crash (deserialization exception) when a Producer adds a new enum value (e.g., `PaymentGateway.NEW_STRIPE`).

## 3. Automated Orphaned Annotation Sweeper
Use an automated scanner to guarantee that no dead `@RetryableTopic` or raw `@KafkaListener` annotations were left behind on classes that have been migrated to the unified Outbox architecture.
```bash
# Automated Enforcement Script
python3 scripts/scan_orphaned_kafka_annotations.py
```
**Expected Outcome:** Exits 0. No dead annotations remain in the execution path.
