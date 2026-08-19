import os

base_dir = "/Users/parthureddy/Documents/Food Delivery.nosync/FoodDeliveryContracts/Implementation_Plan"

def append_to_checklist(subphase_path, additional_items):
    file_path = os.path.join(base_dir, subphase_path, "checklist.md")
    if os.path.exists(file_path):
        with open(file_path, "a") as f:
            for item in additional_items:
                f.write(f"- [ ] Implement assertions for: {item}\n")

append_to_checklist(
    "Phase3.1_Consumer_Client_Validation/SubPhase_A_Core_Domains",
    [
        "CustomerApplication: PaymentServiceClient",
        "RestaurantApplication: GovernmentIdServiceClient",
        "DeliveryExecutiveApplication: GovernmentIdServiceClient"
    ]
)

append_to_checklist(
    "Phase3.1_Consumer_Client_Validation/SubPhase_B_Integrations",
    [
        "ONDCIntegrationService: PaymentServiceClient"
    ]
)

append_to_checklist(
    "Phase3.1_Consumer_Client_Validation/SubPhase_C_Ads_And_Budgets",
    [
        "CampaignService: PaymentServiceClient (needs test)"
    ]
)
print("Checklists updated.")
