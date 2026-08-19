#!/usr/bin/env python3
"""Audit every @KafkaListener's field reads against the contract for the topic it consumes.

Finds the bug class that has already produced four silent production defects: the producer emits a
flat DTO, the consumer expects an {eventType, payload} envelope (or reads a field at the wrong
nesting/casing), and the mismatch fails with no exception and no DLQ entry.

Specified in Phase5_Messaging_Realignment/validation.md section 2.

STATIC ANALYSIS - treat output as a list to verify by reading, not as a verdict. It cannot follow
fields resolved through helper methods or DTO binding.
"""
import os
import re
import sys
from collections import defaultdict

WS = "/Users/parthureddy/Documents/Food Delivery.nosync"
SKIP = {".git", "target", "node_modules", "venv"}

# ---------- resolve topic constants ----------
consts = {}
for rel in ["CommonLibrary/src/main/java/com/fooddelivery/common/constants/KafkaConstants.java",
            "ONDCIntegrationService/src/main/java/com/fooddelivery/ondc/config/OndcKafkaConfig.java"]:
    p = os.path.join(WS, rel)
    if os.path.exists(p):
        for m in re.finditer(r'String\s+(TOPIC_[A-Z_]+)\s*=\s*"([^"]+)"', open(p).read()):
            consts[m.group(1)] = m.group(2)


def body_block(src):
    """Extract the text inside outputMessage's body([...]) with bracket matching."""
    i = src.find("body([")
    if i < 0:
        return ""
    j = i + len("body(")
    depth, k = 0, j
    while k < len(src):
        if src[k] == "[":
            depth += 1
        elif src[k] == "]":
            depth -= 1
            if depth == 0:
                break
        k += 1
    return src[j:k + 1]


def contract_keys(src):
    """Return (root_keys, all_keys) for a contract body, tracking bracket depth."""
    blk = body_block(src)
    root, allk, depth = set(), set(), 0
    for tok in re.finditer(r'\[|\]|(\w+)\s*:', blk):
        if tok.group(0) == "[":
            depth += 1
        elif tok.group(0) == "]":
            depth -= 1
        elif tok.group(1):
            allk.add(tok.group(1))
            if depth == 1:
                root.add(tok.group(1))
    return root, allk


# ---------- index contracts by topic ----------
by_topic = defaultdict(list)
for root_, dirs, files in os.walk(WS):
    dirs[:] = [d for d in dirs if d not in SKIP]
    if not root_.endswith(os.path.join("resources", "contracts", "messaging")):
        continue
    for f in sorted(files):
        if not f.endswith(".groovy"):
            continue
        src = open(os.path.join(root_, f)).read()
        m = re.search(r"sentTo\('([^']+)'\)", src)
        if m:
            rk, ak = contract_keys(src)
            by_topic[m.group(1)].append((f, rk, ak))


def method_body(src, idx):
    """Body of the method whose @KafkaListener starts at idx."""
    i = src.find("{", src.find("public", idx))
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return src[i:j]


findings = []
print(f"{'consumer':<34}{'topic':<30}status")
print("-" * 96)

for root_, dirs, files in os.walk(WS):
    dirs[:] = [d for d in dirs if d not in SKIP]
    if "/src/main/java" not in root_.replace(os.sep, "/"):
        continue
    for f in sorted(files):
        if not f.endswith(".java"):
            continue
        p = os.path.join(root_, f)
        src = open(p).read()
        for m in re.finditer(r'@KafkaListener\([^)]*topics\s*=\s*(?:\{\s*)?([^,)}]+)', src):
            raw = m.group(1).strip()
            topic = raw.strip('"') if raw.startswith('"') else consts.get(raw.split(".")[-1])
            if not topic:
                continue
            variants = by_topic.get(topic)
            svc = os.path.relpath(p, WS).split(os.sep)[0]
            name = f[:-5]
            if not variants:
                print(f"{name:<34}{topic:<30}no contract - skipped")
                continue

            body = method_body(src, m.start())
            # .get()/.path() are required reads; .has() is an existence probe, so a field only
            # ever probed is optional by construction and must not count as a mismatch.
            reads = set(re.findall(r'\.(?:get|path)\(\s*"([^"]+)"', body))
            probes = set(re.findall(r'\.has\(\s*"([^"]+)"', body))
            # A consumer that probes before reading tolerates absence -- treat as optional.
            reads -= probes

            # Requires an envelope only if it *reads* payload without a tolerant fallback.
            wants_envelope = "payload" in re.findall(r'\.get\(\s*"([^"]+)"', body)
            if re.search(r'has\("payload"\)\s*\?', body):
                wants_envelope = False  # ternary fallback: accepts flat too
            issues = []
            # a consumer is OK if ANY contract variant on the topic satisfies it
            ok_any = False
            for cname, rk, ak in variants:
                v = []
                if wants_envelope and "payload" not in rk:
                    v.append("expects a 'payload' envelope the contract does not have")
                unknown = {r for r in reads
                           if not r.startswith("FIELD_") and r not in ak
                           and r not in {"payload", "eventType"}}
                if unknown:
                    v.append("reads field(s) absent from contract: " + ", ".join(sorted(unknown)))
                if not v:
                    ok_any = True
                    break
            if ok_any:
                print(f"{name:<34}{topic:<30}OK")
            else:
                _, rk, ak = variants[0]
                detail = []
                if wants_envelope and "payload" not in rk:
                    detail.append("expects {eventType,payload} envelope; contract is FLAT")
                unknown = {r for r in reads
                           if not r.startswith("FIELD_") and r not in ak
                           and r not in {"payload", "eventType"}}
                if unknown:
                    detail.append("reads absent field(s): " + ", ".join(sorted(unknown)))
                print(f"{name:<34}{topic:<30}MISMATCH")
                for d in detail:
                    print(f"{'':<64}- {d}")
                findings.append((svc, name, topic, detail))

print()
print(f"{len(findings)} consumer(s) flagged. Verify each by reading before acting.")
sys.exit(1 if findings else 0)
