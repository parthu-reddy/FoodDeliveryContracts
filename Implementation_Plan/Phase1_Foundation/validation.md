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

## 6. Stub Resolution Strategy (supersedes the earlier local-broker section)

**Decision (2026-08-19): local development resolves stubs from `~/.m2`, never from a `file://` git
broker.**

### Why the file:// broker was abandoned

The workspace path contains a space (`Food Delivery.nosync`). Spring Cloud Contract decodes the
percent-encoded `%20` and then re-parses the result, so the space reappears and URI parsing fails:

```
Illegal character in path at index 40: file:///Users/parthureddy/Documents/Food Delivery.nosync/...
```

This happens in **two independent layers** and is not a transient bug:

- the Maven plugin's `contractsRepositoryUrl` (build time), and
- `BatchStubRunner` at **runtime**, which breaks any test resolving via `stubrunner.repositoryRoot`.

A space-free mirror was rejected: a second copy drifts silently, which already caused a stale
`wallet_events.groovy` to be validated against a contract that no longer existed.

### The rule

- **Local/dev:** `stubsMode: LOCAL` with explicit `ids`; stubs come from `~/.m2`. Producers must be
  `mvn install`-ed first — verify jar *contents*, not timestamps:
  `unzip -l <stubs.jar> | grep groovy`.
- **CI:** the GitHub broker URL, injected per environment. Tracked in Phase 8.
- **Never** a `file://` repositoryRoot, in YAML, in a pom, or in an `@AutoConfigureStubRunner`
  annotation, while the workspace path contains a space.

### Programmatic validation

```bash
python3 FoodDeliveryContracts/validate_broker_url.py
```

**Expected outcome:** exits `0`. It fails if any of the following hold:
- a `file://` broker URL appears in any YAML, pom, or annotation;
- an `application-test.yml` declares `stubsMode: REMOTE` (dev must resolve from `.m2`);
- a `stubrunner.repositoryRoot` is present at all in a test profile;
- any `application-test.yml` fails to parse as YAML, or any `pom.xml` fails to parse as XML.

The root cause is the space in the workspace directory name, which has now produced three distinct
failure classes: the Maven plugin, the runtime stub runner, and the `rsync` deployment problems
recorded in `CommonMistakesDocumentation/AgentRules/agent-best-practices.md` items 6 and 7. Renaming
the directory would remove all three, at the cost of updating ~170 files that hardcode the path.
