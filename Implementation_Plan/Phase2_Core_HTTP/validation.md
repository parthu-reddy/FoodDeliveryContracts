# Phase 2: Internal Core API Contracts (HTTP) — Validation

To rigorously crosscheck that Phase 2 was implemented correctly without missing edge cases, you must execute automated programmatic validations. Do NOT rely on manual grep searches.

## 1. Automated Feign Path vs Contract URL Matcher
Run the following Python script to parse Java files and Groovy contracts, ensuring every URL defined in a `.groovy` contract perfectly matches the `path` attribute in the corresponding `CommonLibrary` Feign Client.
```python
# Save as validate_phase2_paths.py and execute
import os, re
# Extract Feign paths
feign_paths = []
# Match logic here (simplified for doc)
# If a mismatch is found, script MUST exit(1)
```
**Expected Outcome:** Script exits with code 0. A mismatch means the stub will throw a 404 Not Found during the Consumer's test.

## 2. Duplicate Feign Client Enforcement
Run a strict AST/Regex parser across all 16 microservices to guarantee no local service redefines a Feign client that belongs in `CommonLibrary`.
```bash
# Automated Enforcement Script
python3 scripts/enforce_no_local_feign_overrides.py
```
**Expected Outcome:** Script exits with code 0. If any non-CommonLibrary service returns a match, they must be refactored to use the shared interface to prevent `ConflictingBeanDefinitionException`.

## 3. Contract Compilation and Stub Generation
In each Producer directory (e.g., `WalletService`), execute a full compilation to verify the Maven plugin binds and generates the Java test files from Groovy.
```bash
mvn clean test -Dtest=ContractVerifierTest
```
**Expected Outcome:** Spring Cloud Contract should automatically generate Java/JUnit test files in `target/generated-test-sources/contracts/` and the tests must pass. If the directory is empty, the plugin is misconfigured.
