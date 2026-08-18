# Phase 4: Kafka Async Event Contracts (Core) — Validation

To rigorously crosscheck that Phase 4 was implemented correctly without missing edge cases, execute automated programmatic validations:

## 1. Automated Producer Trigger Verification
Run a strict Python validation script that loads all Groovy contracts using AST/regex, identifies every `triggeredBy('X')` clause, and cross-references it against the parsed Java AST of the `BaseMessagingClass.java`.
```python
# Execute: python3 scripts/verify_kafka_triggers.py
```
**Expected Outcome:** Script exits with code 0. All trigger methods exist, have `@Test` annotations, and successfully inject a message into the internal Kafka template mock.

## 2. Mathematical Consumer Listener Coverage
From `crosscheck_report_v2.md`, we know there are exactly 25 `@KafkaListener` annotations across all microservices. Execute an automated test counter to guarantee full coverage:
```bash
# Test execution counting
mvn test -Dtest=*KafkaConsumerTest* | grep "Tests run:"
```
**Expected Outcome:** The aggregate "Tests run" MUST equal exactly 25. If there are fewer than 25 executed CDC consumer tests for Kafka, a listener contract was missed.

## 3. Postel's Law Automated Audit
Use an automated schema validator to compare the Groovy `outputMessage` bodies against the full Database Entities.
```python
# Execute: python3 scripts/audit_postels_law.py
```
**Expected Outcome:** The validator asserts that the `outputMessage` bodies do NOT map to 100% of the Database Entity fields. They should only assert the subset of fields actually deserialized by the consumer to prevent brittle contracts.
