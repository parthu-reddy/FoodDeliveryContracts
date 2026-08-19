#!/usr/bin/env python3
"""Keep messaging contracts and their producer triggers in agreement on dynamic identifiers.

Contracts assert with $(producer(regex(UUID))); the BaseMessagingClass trigger must emit a
matching UUID. Both halves are rewritten together -- see Phase4_Core_Kafka/validation.md #4.

Usage:  sync_messaging_ids.py [--check]
        --check validates without writing and exits 1 on any problem.
"""
import os
import re
import sys
import uuid

WORKSPACE = "/Users/parthureddy/Documents/Food Delivery.nosync"
UUID_RE = r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"
MATCHER = "$(producer(regex('" + UUID_RE + "')))"

# Identity fields only. Numeric/semantic fields are deliberately excluded.
ID_FIELDS = [
    "eventId", "userId", "customerId", "executiveId", "candidateId", "transactionId",
    "paymentId", "chatId", "senderId", "networkOrderId", "itemId",
]
FIELD_ALT = "|".join(ID_FIELDS)

# Groovy:  eventId: "log-444"        ->  eventId: $(producer(regex(...)))
GROOVY_RE = re.compile(r'\b(' + FIELD_ALT + r')(\s*:\s*)"([^"]*)"')
# Java JSON text block:  "eventId": "log-444"  ->  "eventId": "<uuid>"
JAVA_RE = re.compile(r'"(' + FIELD_ALT + r')"(\s*:\s*)"([^"]*)"')

CHECK = "--check" in sys.argv
problems = []
edits = 0


def stable_uuid(literal):
    """Deterministic per literal, so the same entity keeps one identity across services."""
    if re.fullmatch(UUID_RE, literal):
        return literal
    return str(uuid.uuid5(uuid.NAMESPACE_OID, literal))


def contracts():
    for root, dirs, files in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if d not in {".git", "target", "node_modules", "venv"}]
        if root.endswith(os.path.join("resources", "contracts", "messaging")):
            for f in sorted(files):
                if f.endswith(".groovy"):
                    yield os.path.join(root, f)


def base_classes():
    for root, dirs, files in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if d not in {".git", "target", "node_modules", "venv"}]
        for f in sorted(files):
            if f == "BaseMessagingClass.java":
                yield os.path.join(root, f)


print("== 1. Messaging contracts: identifiers must use a regex matcher ==")
for path in contracts():
    rel = os.path.relpath(path, WORKSPACE)
    src = open(path).read()
    hits = GROOVY_RE.findall(src)
    if CHECK:
        if hits:
            for field, _, literal in hits:
                print(f'  FAIL {rel}: {field} still hardcoded as "{literal}"')
                problems.append(rel)
        else:
            print(f"  OK   {rel}")
    else:
        updated = GROOVY_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{MATCHER}", src)
        if updated != src:
            open(path, "w").write(updated)
            edits += len(hits)
            print(f"  updated ({len(hits)}x) {rel}")

print("== 2. Trigger payloads: identifiers must emit a real UUID ==")
for path in base_classes():
    rel = os.path.relpath(path, WORKSPACE)
    src = open(path).read()
    bad = [(f, v) for f, _, v in JAVA_RE.findall(src) if not re.fullmatch(UUID_RE, v)]
    if CHECK:
        if bad:
            for field, literal in bad:
                print(f'  FAIL {rel}: {field} emits non-UUID "{literal}"')
                problems.append(rel)
        else:
            print(f"  OK   {rel}")
    else:
        updated = JAVA_RE.sub(
            lambda m: f'"{m.group(1)}"{m.group(2)}"{stable_uuid(m.group(3))}"', src)
        if updated != src:
            open(path, "w").write(updated)
            edits += len(bad)
            print(f"  updated ({len(bad)}x) {rel}")

print("== 3. Every triggeredBy('fireX()') resolves to a real trigger method ==")
base_src = {}
for path in base_classes():
    # BaseMessagingClass lives at <Service>/src/test/java/...; recover the service root.
    service = os.path.relpath(path, WORKSPACE).split(os.sep)[0]
    base_src[service] = open(path).read()
for path in contracts():
    rel = os.path.relpath(path, WORKSPACE)
    service = rel.split(os.sep)[0]
    src = open(path).read()
    for trigger in re.findall(r"triggeredBy\('(\w+)\(\)'\)", src):
        if service not in base_src:
            print(f"  FAIL {rel}: no BaseMessagingClass in {service}")
            problems.append(rel)
        elif f"public void {trigger}()" not in base_src[service]:
            print(f"  FAIL {rel}: {service} BaseMessagingClass has no {trigger}()")
            problems.append(rel)
        else:
            print(f"  OK   {rel} -> {trigger}()")

print("== 4. Every sentTo(...) destination is reachable in the test harness ==")
for path in contracts():
    rel = os.path.relpath(path, WORKSPACE)
    service = rel.split(os.sep)[0]
    dest = re.search(r"sentTo\('([^']+)'\)", open(path).read())
    if not dest:
        continue
    dest = dest.group(1)
    src = base_src.get(service, "")
    topics = re.search(r"@EmbeddedKafka\([^)]*topics\s*=\s*\{([^}]*)\}", src)
    declared = re.findall(r'"([^"]+)"', topics.group(1)) if topics else []
    # A colon is illegal in a Kafka topic, so such destinations use a direct in-memory publish.
    direct = ":" in dest and "publishDirect" in src
    if dest in declared or direct:
        how = "direct publish" if direct else "@EmbeddedKafka"
        print(f"  OK   {rel} -> {dest} ({how})")
    else:
        print(f"  FAIL {rel}: destination {dest} not registered in {service}")
        problems.append(rel)

if CHECK:
    print(f"\n{'VALIDATION FAILED: ' + str(len(problems)) + ' problem(s).' if problems else 'VALIDATION PASSED.'}")
    sys.exit(1 if problems else 0)
print(f"\nRewrote {edits} identifier(s). Re-run with --check to validate.")
