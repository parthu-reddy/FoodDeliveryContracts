import os

base_dir = "/Users/parthureddy/Documents/Food Delivery.nosync/FoodDeliveryContracts/Implementation_Plan"

subphases_3 = {
    "SubPhase_A_Core_Domains": [
        "CustomerApplication: CustomerContractConsumerTest (asserts RestaurantClient, AdvertisementClient), WalletContractConsumerTest (asserts WalletServiceClient), MapsServiceClient (needs test)",
        "RestaurantApplication: RestaurantContractConsumerTest (asserts OrderClient, DeliveryClient, AdvertisementClient)",
        "DeliveryExecutiveApplication: DeliveryExecutiveContractConsumerTest (asserts CustomerServiceClient)"
    ],
    "SubPhase_B_Integrations": [
        "ONDCIntegrationService: ONDCContractConsumerTest (asserts LedgerServiceClient, CustomerServiceClient, RestaurantServiceClient, DeliveryServiceClient)",
        "GovernmentIDValidationService: GovIdContractConsumerTest (asserts IdentityServiceClient, RestaurantServiceClient, DeliveryExecutiveClient)",
        "CommunicationService: ContractConsumerTest (asserts RestTemplate to Customer and Restaurant)"
    ],
    "SubPhase_C_Ads_And_Budgets": [
        "BudgetLimitingService: BudgetLimitingContractConsumerTest (asserts CampaignClient)"
    ]
}

subphases_4 = {
    "SubPhase_A_Order_Fulfillment": [
        "CustomerApplication: OrderEventConsumerTest, MenuCacheInvalidationListenerTest",
        "RestaurantApplication: OrderEventConsumerTest",
        "DeliveryExecutiveApplication: OrderEventConsumerTest"
    ],
    "SubPhase_B_Financials": [
        "WalletService: LedgerResponseConsumerTest, BillingEventConsumerTest, LedgerFailureConsumerTest, TopupEventConsumerTest, GenericWalletEventConsumerTest",
        "LedgerService: LedgerEventListenerTest",
        "PaymentGatewayIntegration: OrderEventConsumerTest"
    ],
    "SubPhase_C_Ads_And_Tracking": [
        "CampaignService: KafkaAnalyticsConsumerTest",
        "BiddingEngine: CampaignEventConsumerTest",
        "BudgetLimitingService: CampaignSyncConsumerTest"
    ],
    "SubPhase_D_Edge_Integrations": [
        "ONDCIntegrationService: CatalogDeltaSyncServiceTest, ProactiveStatusPublisherTest, SearchEventProcessorTest, ConfirmEventProcessorTest",
        "MapsIntegration: DispatchEventConsumerTest",
        "CommunicationIntegration: NotificationEventConsumerTest, AdNotificationListenerTest"
    ]
}

def create_files(phase_path, subphases_dict, is_kafka):
    for subphase, items in subphases_dict.items():
        dir_path = os.path.join(base_dir, phase_path, subphase)
        os.makedirs(dir_path, exist_ok=True)
        
        # Write checklist.md
        with open(os.path.join(dir_path, "checklist.md"), "w") as f:
            f.write(f"# Checklist for {subphase}\n\n")
            for item in items:
                f.write(f"- [ ] Implement assertions for: {item}\n")
            f.write("- [ ] Run `mvn test` to verify stubs match the implementation.\n")
            f.write("- [ ] Ensure no Hardcoded IDs remain in test contexts.\n")

        # Write validation.md
        with open(os.path.join(dir_path, "validation.md"), "w") as f:
            f.write(f"# Validation Steps for {subphase}\n\n")
            f.write("1. **Unit Test Execution:** Run `mvn test` in the specified microservices.\n")
            f.write("2. **Stub Fetching:** Verify that Spring Cloud Contract downloads the stubs locally.\n")
            if is_kafka:
                f.write("3. **Kafka Assertions:** Verify that the DB state has mutated appropriately after `stubTrigger.trigger()`.\n")
            else:
                f.write("3. **HTTP Assertions:** Verify that the `FeignClient` or `RestTemplate` returns the expected JSON object corresponding to the groovy contract.\n")
            f.write("4. **Coverage:** Ensure all mocked responses are handled without NullPointerExceptions.\n")

create_files("Phase3.1_Consumer_Client_Validation", subphases_3, False)
create_files("Phase4_Core_Kafka", subphases_4, True)

print("Checklists and Validations created successfully.")
