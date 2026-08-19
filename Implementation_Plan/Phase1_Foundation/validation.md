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

## 6. Broker URL Uniformity (Local Development Mode)

**Context:** While implementation is in progress, every service must resolve stubs from the
*local* workspace clone of the contracts repository, not from GitHub. The canonical value is:

```
git://file:///Users/parthureddy/Documents/Food%20Delivery.nosync/FoodDeliveryContracts/.git
```

The space in `Food Delivery.nosync` MUST stay percent-encoded (`%20`) because the value is a URI,
not a shell path. The GitHub URL will be restored in Phase 6 (CI/CD) once implementation completes.

**Three surfaces carry this value.** All three must agree, because the most specific one wins:
1. `*/src/test/resources/application-test.yml` → `stubrunner.repositoryRoot`
2. `*/pom.xml` → `spring-cloud-contract-maven-plugin` → `<contractsRepositoryUrl>`
3. `*/src/test/java/**/*.java` → `@AutoConfigureStubRunner(repositoryRoot = "...")`
   — an annotation attribute **overrides** the YAML, so editing only the YAML is a silent no-op.

**Do not rely on `grep`/`sed` to verify this.** Run the programmatic validator, which parses each
file with a real parser (`yaml.safe_load`, `xml.etree.ElementTree`) rather than matching text:

```bash
python3 FoodDeliveryContracts/validate_broker_url.py
```

**Expected Outcome:** exits `0` and prints `OK` for every occurrence across all three surfaces.
The script fails (exit `1`) if any of the following hold:
- a `repositoryRoot` / `contractsRepositoryUrl` differs from the canonical value (e.g. a stale
  `https://github.com/...` or the throwaway `file:///tmp/FoodDelivery/...` copy);
- the space is left unencoded, which yields a silently unresolvable URI;
- the `.git` directory the URI points at does not exist on disk;
- any `application-test.yml` fails to parse as valid YAML, or any `pom.xml` fails to parse as XML.

**Known caveat (documented, not enforced by the script):** with `stubsMode: REMOTE` against a
`file://` URI, Spring Cloud Contract *clones* the repository, so it reads **committed** state only.
Contracts added to the working tree but not yet committed will NOT be visible to consumer tests.
