# Checklist for SubPhase_A_Core_Domains

- [ ] Implement assertions for: CustomerApplication: CustomerContractConsumerTest (asserts RestaurantClient, AdvertisementClient), WalletContractConsumerTest (asserts WalletServiceClient), MapsServiceClient (needs test)
- [ ] Implement assertions for: RestaurantApplication: RestaurantContractConsumerTest (asserts OrderClient, DeliveryClient, AdvertisementClient)
- [ ] Implement assertions for: DeliveryExecutiveApplication: DeliveryExecutiveContractConsumerTest (asserts CustomerServiceClient)
- [ ] Run `mvn test` to verify stubs match the implementation.
- [ ] Ensure no Hardcoded IDs remain in test contexts.
- [ ] Implement assertions for: CustomerApplication: PaymentServiceClient
- [ ] Implement assertions for: RestaurantApplication: GovernmentIdServiceClient
- [ ] Implement assertions for: DeliveryExecutiveApplication: GovernmentIdServiceClient
