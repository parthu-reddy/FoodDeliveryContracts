# Phase 1: Foundation & Git Broker Setup — Validation

To crosscheck that Phase 1 was implemented correctly without missing edge cases, run the following verifications:

## 1. Maven Dependency Resolution
Run the following in the root of any microservice (e.g., `CustomerApplication`):
```bash
mvn dependency:tree -Dincludes=org.springframework.cloud:spring-cloud-starter-contract-*
```
**Expected Outcome:** The command succeeds and shows the dependency loaded with the correct version matching the Spring Boot release train. No `VersionNotFoundException`.

## 2. Git Broker Connectivity Test
Run the following command locally to simulate what the Stub Runner will do under the hood during tests:
```bash
git ls-remote https://github.com/parthu-reddy/FoodDeliveryContracts.git
```
**Expected Outcome:** The command should return the `HEAD` reference. If it prompts for a password, the Git authentication is not configured correctly for non-interactive CI/CD runners, and a PAT/SSH key must be provisioned.

## 3. Plugin Configuration Verification
Inspect the effective POM of a Consumer to ensure the Git URL was injected into the plugin configuration:
```bash
mvn help:effective-pom | grep -A 5 "contractsRepositoryUrl"
```
**Expected Outcome:** The `<contractsRepositoryUrl>` points exactly to `git://https://github.com/parthu-reddy/FoodDeliveryContracts.git`.

## 4. Full-Fleet Parallel Compilation
Because dependencies and plugins are injected across all 16 microservices simultaneously, you must guarantee that the build lifecycle remains intact globally. Run the following command across the workspace:
```bash
# In the parent directory containing all microservices
for d in */ ; do (cd "$d" && mvn clean compile -DskipTests); done
```
**Expected Outcome:** All microservices successfully compile and return `BUILD SUCCESS`.

## 5. Automated Syntax Validation (XML/YAML)
When bulk-editing configuration files, basic IDE linters aren't enough. Execute programmatic validation to ensure no tags were malformed:
1. **XML (pom.xml):** Use an abstract syntax tree parser (e.g., Python `xml.etree.ElementTree`) to load every `pom.xml`. It must not throw a `ParseError`.
2. **YAML (application-test.yml):** Use a strict YAML loader (e.g., Python `PyYAML`) to load every config. It must resolve into valid dictionaries without indentation exceptions.
