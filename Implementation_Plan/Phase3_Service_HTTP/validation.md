# Phase 3: Service-Specific API Contracts (HTTP) — Validation

To rigorously crosscheck that Phase 3 was implemented correctly, execute the following automated validation checks:

## 1. Automated Feign Client Name vs Artifact ID Validator
The `artifactId` in the target's `pom.xml` is what Spring Cloud Contract uses for the stub jar name. We cannot rely on manual `grep`.
Execute a Python script that parses Java files for `@FeignClient(name="X")`, then opens the `pom.xml` of microservice `X` using `xml.etree.ElementTree` to verify `<artifactId>X</artifactId>` exactly matches.
```python
# Execute: python3 validate_feign_artifact_ids.py
```
**Expected Outcome:** The script exits with code 0. If the target is actually `<artifactId>customer-application</artifactId>` but the Feign client says `name="customer-service"`, the Stub Runner will fail in CI/CD. The script will flag these instantly.

## 2. ONDC & Complex Consumer YAML Validation
Use a strict YAML parser to verify that all consuming microservices correctly request the necessary stubs in their `application-test.yml` files.
```python
# Execute: python3 validate_consumer_yaml_stubs.py
```
**Expected Outcome:** The `stubrunner.ids` list in `ONDCIntegrationService` must mathematically include all HTTP dependencies identified in Phase 3 (Ledger, Customer, Restaurant, Delivery). If any are missing, the integration tests will attempt real network calls and fail. The Python validation will catch missing keys.
