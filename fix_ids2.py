import os
import re

contract_dir = "META-INF"
keys_to_replace = r"(customerId|itemId)"
replacement_value = r"\1: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}')))"
pattern = re.compile(keys_to_replace + r'\s*:\s*"[^"]+"')

for root, _, files in os.walk(contract_dir):
    if "messaging" in root.split(os.sep):
        for file in files:
            if file.endswith(".groovy"):
                filepath = os.path.join(root, file)
                with open(filepath, "r") as f:
                    content = f.read()
                
                new_content = pattern.sub(replacement_value, content)
                
                if content != new_content:
                    with open(filepath, "w") as f:
                        f.write(new_content)
                    print(f"Updated {filepath}")
