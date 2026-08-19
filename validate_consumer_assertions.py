#!/usr/bin/env python3
"""Phase 6 gate: messaging consumer tests must fire a real label, not swallow, and assert.

All 25 are green today while asserting nothing, so a passing test count is not a valid signal.
See Phase6_Consumer_Messaging_Validation/validation.md.
"""
import os
import re
import sys

WORKSPACE = "/Users/parthureddy/Documents/Food Delivery.nosync"
SKIP = {".git", "target", "node_modules", "venv"}
ASSERT_RE = re.compile(r"\bassert[A-Z]\w*\(|\bverify\(|\bawait\(")
TRIGGER_RE = re.compile(r'stubTrigger\s*\.\s*trigger\(\s*"([^"]+)"')

# Every label declared by a contract anywhere in the workspace.
labels = set()
for root, dirs, files in os.walk(WORKSPACE):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if f.endswith(".groovy"):
            labels |= set(re.findall(r'label\("([^"]+)"\)', open(os.path.join(root, f)).read()))

problems, total = [], 0
for root, dirs, files in os.walk(WORKSPACE):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in sorted(files):
        if not f.endswith(".java"):
            continue
        path = os.path.join(root, f)
        src = open(path).read()
        if "stubTrigger" not in src and "StubTrigger" not in src:
            continue
        total += 1
        rel = os.path.relpath(path, WORKSPACE)
        issues = []
        if "catch (Exception" in src:
            issues.append("swallows exceptions")
        if not ASSERT_RE.search(src):
            issues.append("no assertion")
        for lbl in TRIGGER_RE.findall(src):
            if lbl not in labels:
                issues.append(f'triggers undeclared label "{lbl}"')
        if issues:
            print(f"  FAIL {rel}: {'; '.join(issues)}")
            problems.append(rel)
        else:
            print(f"  OK   {rel}")

print(f"\n{len(problems)}/{total} messaging consumer test(s) are not yet meaningful.")
sys.exit(1 if problems else 0)
