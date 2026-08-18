# Phase 3.1 Validation

We will use an automated programmatic script to sequentially run `mvn clean test -Dtest=*ContractConsumerTest` on all relevant services.

## Programmatic Script

```python
import subprocess
import sys

services = [
    "BudgetLimitingService",
    "ONDCIntegrationService",
    "CustomerApplication",
    "RestaurantApplication",
    "DeliveryExecutiveApplication",
    "GovernmentIDValidationService",
    "CommunicationService"
]

def run_tests():
    failed = []
    for service in services:
        print(f"Running Contract Consumer Tests for {service}...")
        cmd = f"cd '/Users/parthureddy/Documents/Food Delivery.nosync/{service}' && mvn test -Dtest=*ContractConsumerTest"
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        
        if result.returncode != 0:
            print(f"[FAIL] {service}")
            print(result.stdout.decode('utf-8'))
            failed.append(service)
        else:
            print(f"[SUCCESS] {service}")
            
    if failed:
        print("\nFailed services:")
        for f in failed:
            print(f"- {f}")
        sys.exit(1)
    else:
        print("\nAll Contract Consumer Tests passed!")

if __name__ == "__main__":
    run_tests()
```
