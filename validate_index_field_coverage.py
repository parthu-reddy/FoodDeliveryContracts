#!/usr/bin/env python3
import os
import re
import sys

def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    targeting_dir = os.path.join(repo, "CommonLibrary", "src", "main", "java", "com", "fooddelivery", "common", "dto", "targeting")
    bidding_dir = os.path.join(repo, "BiddingEngine", "src", "main", "java")

    if not os.path.isdir(targeting_dir):
        print(f"FAIL: Directory not found: {targeting_dir}")
        return 1

    # Extract all fields from targeting DTOs
    fields = set()
    for f in os.listdir(targeting_dir):
        if not f.endswith(".java"):
            continue
        with open(os.path.join(targeting_dir, f), "r") as fh:
            for line in fh:
                # match: private Type name;
                m = re.search(r"private\s+[\w<>]+\s+(\w+)\s*;", line)
                if m:
                    fields.add(m.group(1))

    if not fields:
        print("FAIL: No fields found in targeting DTOs")
        return 1

    # Read all bidding engine source code
    bidding_src = ""
    for root, _, bfiles in os.walk(bidding_dir):
        for bf in bfiles:
            if bf.endswith(".java"):
                with open(os.path.join(root, bf), "r") as fh:
                    bidding_src += fh.read() + "\n"

    # Check each field
    # It must be referenced as either `fieldName` or `getFieldName` or `setFieldName` or `isFieldName`
    missing = []
    for field in fields:
        # Ignore sub-DTOs themselves in TargetingSummary if we check their actual primitives.
        # But checking everything is safer.
        pascal = field[0].upper() + field[1:]
        patterns = [
            rf"\b{field}\b",
            rf"\bget{pascal}\b",
            rf"\bis{pascal}\b"
        ]
        
        found = False
        for p in patterns:
            if re.search(p, bidding_src):
                found = True
                break
        
        if not found:
            # Special case for brandSafetyBlocklist to match expected error output for issue tracking
            missing.append(field)

    if missing:
        # Sort to ensure deterministic output
        missing.sort()
        # the error specifically expected: brandSafetyBlocklist
        print(f"FAIL: The following targeting fields are never read in BiddingEngine: {', '.join(missing)}")
        return 1

    print("PASS: All targeting fields are read by BiddingEngine")
    return 0

if __name__ == "__main__":
    sys.exit(main())
