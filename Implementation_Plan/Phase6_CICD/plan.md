# Phase 6: CI/CD Pipeline Enforcement & Governance — Plan

## Objective
Automate the execution and publication of Spring Cloud Contracts in the CI/CD pipeline. Without pipeline enforcement, contract testing is purely theoretical. The pipeline must guarantee that a Producer cannot deploy if it breaks a Consumer, and a Consumer cannot deploy if it violates a Producer's required payload.

## 1. Producer Pipeline (Publishing Contracts)
When a Producer (e.g., `WalletService`) is built in the CI/CD pipeline:
1. `mvn clean test` runs.
2. The `spring-cloud-contract-verifier` reads the `.groovy` files and generates tests.
3. The generated tests are executed against the actual Spring context. If they fail, the pipeline fails (the Producer didn't meet its own contract).
4. If they pass, `mvn clean deploy` or `mvn spring-cloud-contract:pushStubsToScm` is executed to push the resulting stub `.jar` files to `FoodDeliveryContracts`.

## 2. Consumer Pipeline (Consuming Contracts)
When a Consumer (e.g., `CustomerApplication`) is built:
1. `mvn clean test` runs.
2. The `@AutoConfigureStubRunner` detects the `@FeignClient` and `@KafkaListener` tests.
3. It clones the `FoodDeliveryContracts` Git repo, extracts the `.jar` stubs, and spins up WireMock servers / Mock Kafka queues locally.
4. The Consumer tests execute. If the Consumer requests an invalid path (e.g., `/api/v2/wallets` instead of `v1`) or expects a missing JSON field, the test fails. The pipeline stops.

## 3. Git Authentication in CI/CD
The `FoodDeliveryContracts` repo requires authentication to clone (for Consumers) and push (for Producers).
**Plan:**
Inject a Personal Access Token (PAT) into the CI environment as `GIT_TOKEN`.
Update the Maven plugin and `application-test.yml` configurations to use this token:

### Producer Configuration (`pom.xml`):
```xml
<plugin>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-contract-maven-plugin</artifactId>
    <configuration>
        <contractsRepositoryUrl>git://https://${env.GIT_TOKEN}@github.com/parthu-reddy/FoodDeliveryContracts.git</contractsRepositoryUrl>
        <!-- ... -->
    </configuration>
</plugin>
```

### Consumer Configuration (`application-test.yml`):
```yaml
stubrunner:
  repositoryRoot: git://https://${GIT_TOKEN}@github.com/parthu-reddy/FoodDeliveryContracts.git
```

## 4. Branching Strategy (Governance)
- Contracts pushed from `develop` branches should have the version suffix `-SNAPSHOT`.
- Contracts pushed from `main` should have a fixed version (e.g., `1.0.0`).
- Consumers testing on `develop` must use `stubrunner.ids = com.fooddelivery:wallet-service:+:stubs` (the `+` fetches the latest version, ensuring they test against the newest contracts).
