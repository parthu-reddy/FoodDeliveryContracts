# Phase 2: Core HTTP Contracts - Mistakes and Improvements

## Mistakes & Pitfalls Encountered

1. **Spring Cloud Contract Groovy vs DTO Strictness**:
   - *Mistake*: Defining a Groovy contract response like `data: "null"` or omitting it completely, while the actual Spring controller returned an `ApiResponse` with `data: null`. SCC Verifier strictly enforces JSON structure and type.
   - *Improvement*: The Groovy contract `body` must **exactly** mirror the Java DTO's serialized output structure, including nulls (`data: null`) and lists.

2. **Mockito Initialization and NullPointerExceptions**:
   - *Mistake*: When mocking `ObjectMapper.readTree()`, returning a partially mocked `JsonNode`. Because the service code chained calls like `jsonNode.path("lat").asDouble()`, it threw an NPE.
   - *Improvement*: Either fully deep-mock `JsonNode` (e.g., `Mockito.mock(JsonNode.class, Mockito.RETURNS_DEEP_STUBS)`) or construct an actual `ObjectMapper().readTree("{\"lat\":0.0}")` and return the real node instead of a mock.

3. **Asynchronous/CompletableFuture Mocking**:
   - *Mistake*: Mocking `KafkaTemplate.send()` to just return null. It returns a `CompletableFuture<SendResult<...>>`, so the service calling `.join()` or `.whenComplete()` failed with a NullPointerException.
   - *Improvement*: Always return `CompletableFuture.completedFuture(null)` or a successfully resolved mock object for asynchronous return types.

4. **Missing Dependencies in `ContractTestBase.java`**:
   - *Mistake*: Creating the `Controller` inside `ContractTestBase` but failing to mock **all** constructor arguments. This causes Java compilation errors (`cannot find symbol` or `required X, found Y`).
   - *Improvement*: Before creating `ContractTestBase`, explicitly open and read the target `Controller` to identify exactly which dependencies are `@Autowired` or injected via constructor. Mock every single one of them.

5. **Incorrect Package Imports**:
   - *Mistake*: Guessing the location of DTOs and Entities (e.g., assuming `BankDetails` was in `.entity` instead of `.entity.ExecutiveBankDetails`).
   - *Improvement*: If a compilation error states "cannot find symbol," do a programmatic `grep` for the exact class name or `find` the exact file name before guessing the package import.

## Agent/Process Improvements
- **Iterative Compilation**: Always run `mvn clean test -Dnet.bytebuddy.experimental=true` immediately after creating a single `ContractTestBase` and its `.groovy` contract, rather than writing them for all services at once and drowning in compilation errors.
