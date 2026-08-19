#!/usr/bin/env python3
"""Point every Spring Cloud Contract broker URL at the local workspace clone.

Temporary local-development setting; the GitHub URL is restored in Phase 6 (CI/CD).
Edits are textual so that file formatting survives, then proven correct by the
parser-based validator (validate_broker_url.py). See Phase1_Foundation/validation.md #6.
"""
import os
import re
import sys

WORKSPACE = "/Users/parthureddy/Documents/Food Delivery.nosync"
CANONICAL = "git://file:///Users/parthureddy/Documents/Food%20Delivery.nosync/FoodDeliveryContracts/.git"

# Any git:// URI mentioning the contracts repo, however it is currently spelled.
BROKER_RE = re.compile(r"git://[^\"'\s<>]*FoodDeliveryContracts[^\"'\s<>]*")
SKIP_DIRS = {".git", "target", "node_modules", "venv", "dist", ".venv"}

changed = []


def targets():
    for root, dirs, files in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        # The contracts repo holds these scripts and the plan docs; never rewrite itself.
        if os.path.basename(root) == "FoodDeliveryContracts":
            dirs[:] = []
            continue
        for f in files:
            if f == "application-test.yml" or f == "pom.xml" or f.endswith(".java"):
                yield os.path.join(root, f)


for path in sorted(targets()):
    with open(path) as fh:
        original = fh.read()
    if "FoodDeliveryContracts" not in original:
        continue
    updated, count = BROKER_RE.subn(CANONICAL, original)
    if updated != original:
        with open(path, "w") as fh:
            fh.write(updated)
        changed.append((os.path.relpath(path, WORKSPACE), count))

for rel, count in changed:
    print(f"  updated ({count}x) {rel}")
print(f"\nRewrote {sum(c for _, c in changed)} occurrence(s) across {len(changed)} file(s).")
sys.exit(0)
