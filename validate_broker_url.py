#!/usr/bin/env python3
"""Enforce the stub-resolution rule: local development resolves from ~/.m2, never a file:// broker.

The workspace path contains a space, and Spring Cloud Contract decodes %20 then re-parses it, so a
file:// repositoryRoot fails both in the Maven plugin and in BatchStubRunner at runtime. See
Phase1_Foundation/validation.md section 6.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

import yaml

WORKSPACE = "/Users/parthureddy/Documents/Food Delivery.nosync"
SKIP = {".git", "target", "node_modules", "venv", "dist", ".venv"}
ANNOTATION_RE = re.compile(r'repositoryRoot\s*=\s*"([^"]*)"')

problems = []
checked = 0


def walk(pred):
    for root, dirs, files in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in files:
            if pred(f):
                yield os.path.join(root, f)


def rel(p):
    return os.path.relpath(p, WORKSPACE)


print("== 1. application-test.yml: must use stubsMode LOCAL and declare no repositoryRoot ==")
for path in sorted(walk(lambda f: f == "application-test.yml")):
    try:
        doc = yaml.safe_load(open(path)) or {}
    except yaml.YAMLError as exc:
        print(f"  FAIL {rel(path)} -- invalid YAML: {exc}")
        problems.append(rel(path))
        continue
    sr = doc.get("stubrunner")
    if not isinstance(sr, dict):
        continue
    checked += 1
    issues = []
    if sr.get("stubsMode") == "REMOTE":
        issues.append("stubsMode REMOTE (dev must resolve from ~/.m2)")
    if "repositoryRoot" in sr:
        issues.append(f"declares repositoryRoot ({sr['repositoryRoot']})")
    if issues:
        print(f"  FAIL {rel(path)}: " + "; ".join(issues))
        problems.append(rel(path))
    else:
        print(f"  OK   {rel(path)}")

print("== 2. pom.xml: no contractsRepositoryUrl ==")
for path in sorted(walk(lambda f: f == "pom.xml")):
    try:
        root_el = ET.parse(path).getroot()
    except ET.ParseError as exc:
        print(f"  FAIL {rel(path)} -- invalid XML: {exc}")
        problems.append(rel(path))
        continue
    for el in root_el.iter():
        if el.tag.endswith("contractsRepositoryUrl"):
            checked += 1
            print(f"  FAIL {rel(path)}: declares contractsRepositoryUrl ({(el.text or '').strip()})")
            problems.append(rel(path))

print("== 3. @AutoConfigureStubRunner: no repositoryRoot attribute ==")
for path in sorted(walk(lambda f: f.endswith(".java"))):
    src = open(path).read()
    if "AutoConfigureStubRunner" not in src:
        continue
    for match in ANNOTATION_RE.findall(src):
        checked += 1
        print(f"  FAIL {rel(path)}: pins repositoryRoot ({match})")
        problems.append(rel(path))

print("== 4. no file:// broker URL anywhere ==")
found_file_url = False
for path in sorted(list(walk(lambda f: f.endswith((".yml", ".yaml", ".java")))) +
                   list(walk(lambda f: f == "pom.xml"))):
    src = open(path, errors="ignore").read()
    if re.search(r'git://file://', src):
        print(f"  FAIL {rel(path)}: contains a file:// broker URL")
        problems.append(rel(path))
        found_file_url = True
if not found_file_url:
    print("  OK   none found")

print(f"\nChecked {checked} stub-resolution declaration(s).")
if problems:
    print(f"VALIDATION FAILED: {len(set(problems))} file(s) with problems.")
    sys.exit(1)
print("VALIDATION PASSED: all services resolve stubs from ~/.m2.")
sys.exit(0)
