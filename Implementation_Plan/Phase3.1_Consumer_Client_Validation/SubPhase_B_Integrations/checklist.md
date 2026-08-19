# Checklist for SubPhase_B_Integrations

- [ ] Implement assertions for: ONDCIntegrationService: ONDCContractConsumerTest (asserts LedgerServiceClient, CustomerServiceClient, RestaurantServiceClient, DeliveryServiceClient)
- [ ] Implement assertions for: GovernmentIDValidationService: GovIdContractConsumerTest (asserts IdentityServiceClient, RestaurantServiceClient, DeliveryExecutiveClient)
- [ ] Implement assertions for: CommunicationService: ContractConsumerTest (asserts RestTemplate to Customer and Restaurant)
- [ ] Run `mvn test` to verify stubs match the implementation.
- [ ] Ensure no Hardcoded IDs remain in test contexts.
- [ ] Implement assertions for: ONDCIntegrationService: PaymentServiceClient
