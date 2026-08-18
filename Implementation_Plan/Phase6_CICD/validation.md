# Phase 6: CI/CD Pipeline Enforcement & Governance — Validation

To rigorously crosscheck that Phase 6 was implemented correctly without missing edge cases, execute automated programmatic validations:

## 1. Automated Mock CI/CD Runner (Consumer)
Execute a shell script that provisions a clean, isolated environment (stripping local Maven caches) and injects a mock `GIT_TOKEN` to perfectly simulate the CI/CD pipeline environment during consumer tests.
```bash
# Execute: ./scripts/simulate_ci_cd_consumer_test.sh
```
**Expected Outcome:** The tests pass, successfully cloning from the remote `FoodDeliveryContracts` Git repository rather than falling back to local `.m2` caches.

## 2. Automated SCM Push Validation (Producer)
Run the automated deployment simulator to verify that the `spring-cloud-contract-maven-plugin` successfully executes a Git commit and push.
```bash
# Execute: ./scripts/simulate_ci_cd_producer_deploy.sh
```
**Expected Outcome:** 
1. Tests pass.
2. A `.jar` file containing the stubs is generated.
3. The plugin successfully executes a `git commit` and `git push` to the `FoodDeliveryContracts` remote repository. (The script verifies the latest commit hash on the remote).

## 3. Strict Version Resolution Audit
Use a parser on the `surefire-reports` XML output to mathematically guarantee that the consumer resolved the exact `+` (latest) version from the remote Git repository, failing the build if a stale local version was used.
```python
# Execute: python3 scripts/audit_surefire_stub_resolution.py
```
**Expected Outcome:** The script strictly asserts that `stubsMode=REMOTE` was active and the latest Git SHA/tag was resolved.
