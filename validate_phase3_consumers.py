#!/usr/bin/env python3
"""Phase 3 gate: a consumer test must INVOKE each client it injects, not merely declare it.

Injection without invocation is what made Phase 3 look finished while four tests were still
contextLoads shells. See Phase3_Service_HTTP/validation.md.
"""
import os
import re
import sys

WORKSPACE = "/Users/parthureddy/Documents/Food Delivery.nosync"
SKIP = {".git", "target", "node_modules", "venv"}

FIELD_RE = re.compile(r"@Autowired\s+(?:private\s+)?([\w.]+)\s+(\w+)\s*;")
TEST_RE = re.compile(r"@Test\s+public\s+void\s+(\w+)\s*\([^)]*\)\s*\{", re.S)
ASSERT_RE = re.compile(r"\bassert[A-Z]\w*\(|\bverify\(")

problems = []


def tests_and_bodies(src):
    """Return {method name: body} for every @Test, by brace matching."""
    out = {}
    for m in TEST_RE.finditer(src):
        i = src.index("{", m.end() - 1)
        depth, j = 0, i
        while j < len(src):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out[m.group(1)] = src[i:j]
    return out


for root, dirs, files in os.walk(WORKSPACE):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in sorted(files):
        if not f.endswith("ContractConsumerTest.java"):
            continue
        path = os.path.join(root, f)
        rel = os.path.relpath(path, WORKSPACE)
        src = open(path).read()
        bodies = tests_and_bodies(src)
        all_bodies = "\n".join(bodies.values())

        clients = [(t, n) for t, n in FIELD_RE.findall(src)
                   if t.endswith("Client") or t.endswith("RestTemplate")]

        if not clients:
            print(f"  FAIL {rel}: no client injected")
            problems.append(rel)

        for typ, name in clients:
            if re.search(rf"\b{name}\s*\.", all_bodies):
                print(f"  OK   {rel}: {typ.split('.')[-1]} invoked")
            else:
                print(f"  FAIL {rel}: {typ.split('.')[-1]} injected but never invoked")
                problems.append(rel)

        if not ASSERT_RE.search(all_bodies):
            print(f"  FAIL {rel}: no assertion in any @Test")
            problems.append(rel)

        for nm, body in bodies.items():
            if nm == "contextLoads" and len(bodies) == 1:
                print(f"  FAIL {rel}: only a contextLoads shell")
                problems.append(rel)

# A service that consumes another service over HTTP but has no consumer test at all cannot be
# caught by walking test files -- check the expected set explicitly.
EXPECTED = {
    "CustomerApplication", "RestaurantApplication", "DeliveryExecutiveApplication",
    "GovernmentIDValidationService", "ONDCIntegrationService", "BudgetLimitingService",
    "CommunicationService", "CampaignService",
}
found = set()
for root, dirs, files in os.walk(WORKSPACE):
    dirs[:] = [d for d in dirs if d not in SKIP]
    for f in files:
        if f.endswith("ContractConsumerTest.java"):
            found.add(os.path.relpath(os.path.join(root, f), WORKSPACE).split(os.sep)[0])
for svc in sorted(EXPECTED - found):
    print(f"  FAIL {svc}: no *ContractConsumerTest exists")
    problems.append(svc)

print(f"\n{len(set(problems))} file(s) with problems.")
sys.exit(1 if problems else 0)
