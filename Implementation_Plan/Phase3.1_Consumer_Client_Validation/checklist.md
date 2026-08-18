# Phase 3.1 Checklist

- [ ] Write `BudgetLimitingContractConsumerTest.java` for `BudgetLimitingService`.
- [ ] Inject `CustomerServiceClient`, `RestaurantServiceClient`, `DeliveryServiceClient`, `LedgerServiceClient` into `ONDCContractConsumerTest.java` and write validation tests.
- [ ] Inject `AdvertisementClient` and `RestaurantClient` into `CustomerContractConsumerTest.java` and write validation tests.
- [ ] Inject `OrderClient`, `AdvertisementClient`, and `DeliveryClient` into `RestaurantContractConsumerTest.java` and write validation tests.
- [ ] Inject `CustomerServiceClient` into `DeliveryExecutiveContractConsumerTest.java` and write validation tests.
- [ ] Inject `DeliveryExecutiveClient`, `RestaurantServiceClient`, and `IdentityServiceClient` into `GovIdContractConsumerTest.java` and write validation tests.
- [ ] Mock and assert the `RestTemplate` internal communication paths in `CommunicationService`'s `ContractConsumerTest.java`.
- [ ] Run `mvn test` across all these 7 services.
- [ ] Record mistakes and improvements in `mistakes_and_improvements.md` upon completion.
- [ ] Synchronize `mistakes_and_improvements.md` to `CommonMistakesDocumentation`.
