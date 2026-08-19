#!/usr/bin/env python3
"""Validate that every Spring Cloud Contract broker URL points at the local workspace clone.

Parses each surface with a real parser (YAML/XML) instead of matching text, per the
project's programmatic-validation rule. See Phase1_Foundation/validation.md section 6.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

import yaml

WORKSPACE = "/Users/parthureddy/Documents/Food Delivery.nosync"
CANONICAL = "git://file:///Users/parthureddy/Documents/Food%20Delivery.nosync/FoodDeliveryContracts/.git"

MAVEN_NS = {"m": "http://maven.apache.org/POM/4.0.0"}
ANNOTATION_RE = re.compile(r'repositoryRoot\s*=\s*"([^"]*)"')
SKIP_DIRS = {".git", "target", "node_modules", "venv", "dist", ".venv"}

failures = []
checked = 0


def report(path, found):
    """Compare one occurrence against the canonical URL."""
    global checked
    checked += 1
    rel = os.path.relpath(path, WORKSPACE)
    if found == CANONICAL:
        print(f"  OK   {rel}")
    else:
        print(f"  FAIL {rel}\n         found:    {found}\n         expected: {CANONICAL}")
        failures.append(rel)


def walk(suffix):
    for root, dirs, files in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(suffix):
                yield os.path.join(root, f)


print("== 1. application-test.yml -> stubrunner.repositoryRoot ==")
for path in sorted(walk(".yml")):
    if os.path.basename(path) != "application-test.yml":
        continue
    try:
        with open(path) as fh:
            doc = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        print(f"  FAIL {os.path.relpath(path, WORKSPACE)} -- invalid YAML: {exc}")
        failures.append(path)
        continue
    if isinstance(doc, dict) and isinstance(doc.get("stubrunner"), dict):
        if "repositoryRoot" in doc["stubrunner"]:
            report(path, doc["stubrunner"]["repositoryRoot"])

print("== 2. pom.xml -> contractsRepositoryUrl ==")
# Exact filename only: generated effective-pom.xml dumps are console logs, not valid XML.
for path in sorted(p for p in walk("pom.xml") if os.path.basename(p) == "pom.xml"):
    try:
        root_el = ET.parse(path).getroot()
    except ET.ParseError as exc:
        print(f"  FAIL {os.path.relpath(path, WORKSPACE)} -- invalid XML: {exc}")
        failures.append(path)
        continue
    for el in root_el.iter():
        if el.tag.endswith("}contractsRepositoryUrl") or el.tag == "contractsRepositoryUrl":
            report(path, (el.text or "").strip())

print("== 3. @AutoConfigureStubRunner -> repositoryRoot ==")
for path in sorted(walk(".java")):
    with open(path) as fh:
        content = fh.read()
    if "AutoConfigureStubRunner" not in content:
        continue
    for match in ANNOTATION_RE.findall(content):
        report(path, match)

print("== 4. Referenced .git directory exists on disk ==")
target = CANONICAL.replace("git://file://", "").replace("%20", " ")
if os.path.isdir(target):
    print(f"  OK   {target}")
else:
    print(f"  FAIL {target} does not exist")
    failures.append(target)

print(f"\nChecked {checked} occurrence(s).")
if failures:
    print(f"VALIDATION FAILED: {len(failures)} problem(s).")
    sys.exit(1)
print("VALIDATION PASSED: all broker URLs point at the local workspace clone.")
sys.exit(0)
