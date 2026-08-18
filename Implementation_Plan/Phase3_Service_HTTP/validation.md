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
# Phase 3: Service-Specific APIs — Validation

To rigorously crosscheck that Phase 3 was implemented correctly, we will execute an automated programmatic validation.

## 1. Automated Feign Path vs Contract URL Matcher
Run a Python AST parser to parse Java files and Groovy contracts, ensuring every URL defined in a `.groovy` contract perfectly matches the `path` attribute in the corresponding `ONDCIntegrationService` Feign Clients.

```python
# Save as validate_phase3_paths.py and execute
import os, re

def find_feign_paths():
    feign_paths = []
    base_dir = "/Users/parthureddy/Documents/Food Delivery.nosync/ONDCIntegrationService/src/main/java/com/fooddelivery/ondc/client"
    for filename in os.listdir(base_dir):
        if filename.endswith("Client.java"):
            with open(os.path.join(base_dir, filename), 'r') as f:
                content = f.read()
                # find @GetMapping("/api/...") or @PostMapping("/api/...")
                matches = re.findall(r'@(?:Get|Post)Mapping\("([^"]+)"\)', content)
                feign_paths.extend(matches)
    return feign_paths

def find_contract_urls():
    contract_urls = []
    apps = ["CustomerApplication", "RestaurantApplication", "LedgerService", "DeliveryExecutiveApplication"]
    for app in apps:
        contract_dir = f"/Users/parthureddy/Documents/Food Delivery.nosync/{app}/src/test/resources/contracts"
        if os.path.exists(contract_dir):
            for root, dirs, files in os.walk(contract_dir):
                for file in files:
                    if file.endswith(".groovy"):
                        with open(os.path.join(root, file), 'r') as f:
                            content = f.read()
                            url_match = re.search(r'url\s*\(\s*\'([^\']+)\'\s*\)', content)
                            if url_match:
                                contract_urls.append(url_match.group(1))
    return contract_urls

feign_paths = set(find_feign_paths())
contract_urls = set(find_contract_urls())

# Convert paths with path variables like {orderId} to regex for matching
missing = []
for f_path in feign_paths:
    # replace {id} with generic matcher just to see if the static parts match
    f_path_clean = re.sub(r'\{[^}]+\}', '', f_path).strip('/')
    found = False
    for c_url in contract_urls:
        c_url_clean = re.sub(r'\{[^}]+\}', '', c_url).strip('/')
        if f_path_clean in c_url_clean or c_url_clean in f_path_clean:
            found = True
            break
    if not found:
        missing.append(f_path)

if missing:
    print(f"FAILED: The following Feign paths are missing contracts: {missing}")
    exit(1)
else:
    print("SUCCESS: All Feign paths have matching contracts.")
    exit(0)
```

## 2. Contract Compilation and Stub Generation
In each Producer directory (e.g., `CustomerApplication`), execute a full compilation to verify the Maven plugin binds and generates the Java test files from Groovy.
```bash
mvn clean test -Dtest=ContractVerifierTest -Dnet.bytebuddy.experimental=true
```
**Expected Outcome:** Spring Cloud Contract should automatically generate Java/JUnit test files in `target/generated-test-sources/contracts/` and the tests must pass.
