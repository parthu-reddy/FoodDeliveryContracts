# Validation Steps for SubPhase_C_Ads_And_Tracking

1. **Unit Test Execution:** Run `mvn test` in the specified microservices.
2. **Stub Fetching:** Verify that Spring Cloud Contract downloads the stubs locally.
3. **Kafka Assertions:** Verify that the DB state has mutated appropriately after `stubTrigger.trigger()`.
4. **Coverage:** Ensure all mocked responses are handled without NullPointerExceptions.
