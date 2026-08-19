#!/usr/bin/env python3
"""Every contract's sentTo destination must be a topic production actually publishes to.

Catches the failure where a contract and its trigger both hardcode the same wrong topic literal:
they agree with each other, the test is green, and neither agrees with production. That happened
with the ONDC contracts, which asserted 'ondc-order-created' while OndcKafkaConfig declares
'ondc.order.created'.
"""
import os
import re
import sys

WS = "/Users/parthureddy/Documents/Food Delivery.nosync"
SKIP = {".git", "target", "node_modules", "venv"}

# Every topic value declared as a constant anywhere in production code.
declared = set()
for root, dirs, files in os.walk(WS):
    dirs[:] = [d for d in dirs if d not in SKIP]
    if "/src/main/java" not in root.replace(os.sep, "/"):
        continue
    for f in files:
        if f.endswith(".java"):
            src = open(os.path.join(root, f)).read()
            declared |= set(re.findall(r'String\s+TOPIC_[A-Z_]+\s*=\s*"([^"]+)"', src))
            # topics published or consumed as bare literals
            declared |= set(re.findall(r'\.send\(\s*"([a-z0-9._\-]+)"', src))
            declared |= set(re.findall(r'topics\s*=\s*(?:\{\s*)?"([a-z0-9._\-]+)"', src))

problems = []
for root, dirs, files in os.walk(WS):
    dirs[:] = [d for d in dirs if d not in SKIP]
    if not root.endswith(os.path.join("resources", "contracts", "messaging")):
        continue
    for f in sorted(files):
        if not f.endswith(".groovy"):
            continue
        p = os.path.join(root, f)
        m = re.search(r"sentTo\('([^']+)'\)", open(p).read())
        if not m:
            continue
        topic, svc = m.group(1), os.path.relpath(p, WS).split(os.sep)[0]
        # Redis Pub/Sub channels are not Kafka topics and carry a dynamic id.
        if ":" in topic:
            print(f"  SKIP {svc}/{f}: {topic} (Redis channel, not a Kafka topic)")
            continue
        if topic in declared:
            print(f"  OK   {svc}/{f}: {topic}")
        else:
            print(f"  FAIL {svc}/{f}: '{topic}' is not published by any production code")
            problems.append(f"{svc}/{f}")

print(f"\n{len(problems)} contract(s) target a topic nothing publishes to.")
sys.exit(1 if problems else 0)
