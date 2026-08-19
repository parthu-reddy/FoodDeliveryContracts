# Validation Steps for SubPhase_B_Integrations

1. **Unit Test Execution:** Run `mvn test` in the specified microservices.
2. **Stub Fetching:** Verify that Spring Cloud Contract downloads the stubs locally.
3. **HTTP Assertions:** Verify that the `FeignClient` or `RestTemplate` returns the expected JSON object corresponding to the groovy contract.
4. **Coverage:** Ensure all mocked responses are handled without NullPointerExceptions.
