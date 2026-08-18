import os, sys, re

common_lib_dir = "/Users/parthureddy/Documents/Food Delivery.nosync/CommonLibrary/src/main/java/com/fooddelivery/common/client"
contracts_dir = "/Users/parthureddy/Documents/Food Delivery.nosync/FoodDeliveryContracts/META-INF/com.fooddelivery"

def extract_feign_paths():
    feign_paths = {}
    for filename in os.listdir(common_lib_dir):
        if filename.endswith(".java") and "Fallback" not in filename:
            with open(os.path.join(common_lib_dir, filename), "r") as f:
                content = f.read()
                
                # Extract @FeignClient path attribute
                class_match = re.search(r'@FeignClient.*name\s*=\s*"([^"]+)".*?path\s*=\s*"([^"]+)"', content, re.DOTALL)
                if class_match:
                    service_name = class_match.group(1)
                    base_path = class_match.group(2)
                    
                    # Extract endpoints mapping
                    # Match mapping annotations like @GetMapping("...")
                    mappings = re.findall(r'@(?:Get|Post|Put|Delete|Patch)Mapping\s*\(\s*(?:value\s*=\s*)?(?:path\s*=\s*)?"([^"]+)"', content)
                    paths = [base_path + m if not m.startswith('/') else base_path + m for m in mappings]
                    feign_paths[service_name] = paths
                else:
                    # Check for feign clients without path attribute
                    class_match = re.search(r'@FeignClient.*name\s*=\s*"([^"]+)"', content, re.DOTALL)
                    if class_match:
                        service_name = class_match.group(1)
                        mappings = re.findall(r'@(?:Get|Post|Put|Delete|Patch)Mapping\s*\(\s*(?:value\s*=\s*)?(?:path\s*=\s*)?"([^"]+)"', content)
                        feign_paths[service_name] = mappings
    return feign_paths

feign_paths = extract_feign_paths()
print("Extracted Feign Paths:", feign_paths)

def validate_contracts(feign_paths):
    mismatch = False
    for root, _, files in os.walk(contracts_dir):
        for file in files:
            if file.endswith(".groovy"):
                with open(os.path.join(root, file), "r") as f:
                    content = f.read()
                    
                    # Find service name from directory structure
                    service_name = os.path.basename(os.path.dirname(os.path.dirname(root)))
                    
                    # Try to extract the URL from the contract
                    url_match = re.search(r"url\s*\(\s*'([^']+)'\s*\)|urlPath\s*\(\s*'([^']+)'\s*\)", content)
                    if url_match:
                        url = url_match.group(1) or url_match.group(2)
                        
                        expected_paths = feign_paths.get(service_name, [])
                        
                        # Note: Simple exact matching is tough because Feign paths have {variables}
                        # We convert `{variable}` to regex `[^/]+` and check if the groovy URL matches it
                        
                        matched = False
                        for ep in expected_paths:
                            pattern = re.sub(r'\{[^}]+\}', r'[^/]+', ep)
                            if re.match(f"^{pattern}$", url):
                                matched = True
                                break
                        
                        if not matched:
                            print(f"[ERROR] URL {url} in {file} (for {service_name}) does not match any Feign path: {expected_paths}")
                            mismatch = True
                        else:
                            print(f"[OK] URL {url} in {file} matches a Feign path for {service_name}")
                            
    return not mismatch

if validate_contracts(feign_paths):
    print("All Phase 2 Contracts validated against Feign Paths.")
    sys.exit(0)
else:
    print("Validation failed!")
    sys.exit(1)
