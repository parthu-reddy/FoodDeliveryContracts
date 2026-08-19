# Mistakes and Improvements: Phase 3

## Mistakes Made
1. **Redundant Folder Creation:** During the agent interaction, a redundant folder (`Phase3_Service_Specific_APIs`) was created because the original scaffolding name (`Phase3_Service_HTTP`) was forgotten.
   * *Resolution:* Merged programmatic validation scripts back into the original `Phase3_Service_HTTP` folder and strictly adhered to sequential directory layouts.
2. **Missing Repository Mocks (`NullPointerException`):** In `CustomerApplication` contract testing, `ContractTestBase.java` failed initially because `IOrderRepository.findByStatusInAndDeliveryExecutiveIdIsNull(...)` returned `null` instead of an empty `PageImpl`. 
   * *Resolution:* We learned that when using `RestAssuredMockMvc.standaloneSetup(controller)`, *all* required constructor-injected repository dependencies must be explicitly mocked and their behaviors stubbed out to return safe default values (like empty lists) rather than returning nulls which cause internal `NullPointerException`s in controllers.
3. **Manual Bash Command usage:** Violated the strict `/learn` rule by using `cat` and `>>` inside a `run_command` bash execution rather than relying on Python scripts or IDE tools.
   * *Resolution:* Switched to generating and running a dedicated `setup_phase3.py` programmatic script to enforce reproducible operations across all target producers (`RestaurantApplication`, `LedgerService`, `DeliveryExecutiveApplication`).

## Improvements & Best Practices Discovered
1. **Automated Programmatic Batch Generation:** Instead of manually adjusting POMs and generating `ContractTestBase.java` files via IDE tools one by one, using an automated script (`setup_phase3.py`) to systematically parse and replace configurations was extremely fast and error-free.
2. **JVM Fork Flag for JDK 26:** Adding `-Dnet.bytebuddy.experimental=true` was an essential discovery for allowing Spring Cloud Contract and Mockito to instrument bytecode properly on the latest JDKs.

## Phase 3 Completion Mistakes
1. **Producer Maven Plugin in Consumer POMs:** We initially added `spring-cloud-contract-maven-plugin` (with `contractsMode=REMOTE`) to all services, including consumer-only services. This caused `mvn test` to fail because the plugin tried to download non-existent contracts from the remote repository.
   * *Resolution:* Consumer POMs should NOT execute the `spring-cloud-contract-maven-plugin` `generateTests` goal. We bypassed this by adding `<skip>true</skip>` in the consumer POMs.
2. **Missing StubRunner Dependency:** We used `@AutoConfigureStubRunner` in `ContractConsumerTest` classes for consumer services but forgot to include the actual `spring-cloud-starter-contract-stub-runner` Maven dependency, causing test compilation failures.
   * *Resolution:* Always add `spring-cloud-starter-contract-stub-runner` (`<scope>test</scope>`) to any service acting as a contract consumer.

## Merged from the stray workspace-root Implementation_Plan (Phase 3.1)

## Mistakes Identified
1. **Producer Maven Integration Test Conflict**:
   - *Issue*: During the `install` phase of `CampaignService` (producer), the `spring-boot-maven-plugin` `start` execution triggered during `pre-integration-test` caused an `ApplicationContext` collision over `@EnableJpaRepositories` (due to `OutboxConfiguration` and `CampaignServiceApplication` both defining it) and port 9015/8080 conflicts.
   - *Solution*: Removed the `spring-boot-maven-plugin` executions for `start` and `stop` from `CampaignService/pom.xml`. The ContractVerifier tests execute using `@SpringBootTest` directly, so we do not need the maven plugin to boot up the application separately in the background for `spring-cloud-contract-maven-plugin`.

2. **Feign Client Hardcoded URLs Bypassing StubRunner**:
   - *Issue*: In `BudgetLimitingService`, `CampaignClient` was defined with `url = "${campaign-service.url:http://campaign-service}"`. StubRunner's auto-configuration replaces Ribbon/LoadBalancer URLs, but a hardcoded `url` bypasses Ribbon entirely. This caused the test to hit the real unresolved URL or the fallback, failing the test.
   - *Solution*: Explicitly provided the property `campaign-service.url=http://localhost:8095` inside `@SpringBootTest(properties = {...})` to direct the Feign client to the StubRunner mock server port.

3. **ByteBuddy Java Compatibility**:
   - *Issue*: Running tests with Mockito resulted in `IllegalArgumentException: Java 26 (70) is not supported by the current version of Byte Buddy which officially supports Java 23 (67)`.
   - *Solution*: Required passing `-Dnet.bytebuddy.experimental=true` in the maven command line to allow Mockito to instrument the classes.

## Improvements for Next Phases
- **Consumer Driven Contract Workflow**: Moving forward, we should use a "consumer-driven" approach. We will define the contracts (the JSON/Groovy files) inside the central `FoodDeliveryContracts` repository FIRST, before writing the actual implementations. Then the Producers can pull them to verify their endpoints, and Consumers can pull them to verify their Feign clients.
- **Centralized Testing Scripts**: We should create bash wrappers for testing that automatically include `-Dnet.bytebuddy.experimental=true`.

## Consolidation note (2026-08-19)

`Phase3.1_Consumer_Client_Validation` and `Phase3.1_Consumer_Validations` duplicated this phase's
scope and were merged into `Phase3_Service_HTTP`. A stray `Implementation_Plan/` at the workspace
root held the only copy of the Phase 3.1 lessons above; it has been folded in here.

The full write-up of the Phase 3 & 4 completion pass lives in
[CommonMistakesDocumentation/ContractTesting/Phase3_4_Completion_Mistakes.md](../../../CommonMistakesDocumentation/ContractTesting/Phase3_4_Completion_Mistakes.md)
- contract/trigger coupling, `@TestConfiguration` not stopping Boot's config search, a YAML
indentation bug that disabled Flyway, Kafka `auto-offset-reset` defaults, JsonSerializer
double-encoding, `contractsRepositoryUrl` rejecting spaces, and the still-open schema mismatch.

**Duplicate-folder lesson, now recurring:** Phase 3's own notes already recorded creating a
redundant `Phase3_Service_Specific_APIs` folder. It happened again with `Phase3.1_*`,
`Phase4_Messaging_Contracts`, `Phase4_Messaging_Kafka` and four orphan `SubPhase_*` directories,
because scaffolding scripts were re-run with different names. Check `Implementation_Plan/README.md`
for the canonical phase list before creating any folder.
