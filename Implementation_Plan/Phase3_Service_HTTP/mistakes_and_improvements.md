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
