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
            # A topic carries many event types. Comparing a consumer against a contract for a
            # DIFFERENT event type on the same topic is meaningless -- it produced a MISMATCH on the
            # money path (RefundCreditConsumer, 2026-09-12) where the real producer sends every field
            # the consumer reads. A gate that cries wolf there is worse than no gate.
            et = re.search(r"header\(\s*'eventType'\s*,\s*'([A-Z_]+)'\s*\)", src)
            body_et = re.search(r"eventType\s*:\s*['\"]([A-Z_]+)['\"]", src)
            event_type = et.group(1) if et else (body_et.group(1) if body_et else None)
            by_topic[m.group(1)].append((f, rk, ak, event_type))


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




# ---------- resolving what a consumer really reads ----------

def _payload_constants():
    """EventPayloadConstants.FOO -> "foo".

    A consumer keyed on shared constants instead of string literals is invisible to a naive scan.
    ReviewEventConsumer became exactly that on 2026-09-12 when its payload keys moved into
    EventPayloadConstants so a rename would break producer and consumer together -- a good change
    that made this audit read it as touching no fields at all.
    """
    out = {}
    path = os.path.join(WS, "CommonLibrary/src/main/java/com/fooddelivery/common/constants/"
                            "EventPayloadConstants.java")
    try:
        src = open(path).read()
    except OSError:
        return out
    for m in re.finditer(r'String\s+([A-Z_]+)\s*=\s*"([^"]+)"', src):
        out[m.group(1)] = m.group(2)
    return out


PAYLOAD_CONSTANTS = _payload_constants()


def _block_after(src, start):
    """The brace-balanced block beginning at the first '{' at or after `start`."""
    i = src.find("{", start)
    if i == -1:
        return ""
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
    return src[i:]


def field_reads(body, src, pattern=r'\.(?:get|path)\(\s*'):
    """Every field the listener reads, following one level of same-file delegation.

    A listener that hands the JSON node to a helper reads whatever that helper reads.
    RestaurantApplication's OrderEventConsumer reads one field directly and seventeen more inside the
    helpers it delegates to -- so without following those calls, the event that opens a cash order in
    a kitchen was verified against `orderId` alone.

    Three boundaries, all deliberate:

      * **One level.** The callee is scanned with `direct()`, not with `field_reads()`, so a helper
        that calls a second helper contributes only its own literals.
      * **Same file.** The callee is looked up in `src`, this file's text. A consumer that dispatches
        to strategy classes in another package is invisible -- DeliveryExecutiveApplication's
        OrderEventConsumer reads nothing as far as this function can see, and is reported as reading
        nothing rather than as OK.
      * **Every literal in the callee counts**, including a read of a node other than the one passed
        in. `direct()` matches `.get("x")` regardless of receiver.

    The third can over-report. That is the safe direction: over-reporting surfaces as a MISMATCH a
    human resolves by reading, per this script's banner, while under-reporting is a silent false OK.
    Over-reporting is currently unexercised -- RestaurantApplication's OrderEventConsumer is the only
    consumer in the workspace where delegation adds anything (1 -> 18), and its helpers read only the
    node they are handed.

    This function does not under-report. The *pipeline* did, once, and elsewhere: `reads -= probes`
    treated a fail-fast `if (!node.has("x")) throw` as evidence that x was optional. Fixed at the
    call site by exempting negated probes; see the comment there.
    """
    def direct(block):
        found = set(re.findall(pattern + r'"([^"]+)"', block))
        for const in re.findall(pattern + r'EventPayloadConstants\.([A-Z_]+)', block):
            if const in PAYLOAD_CONSTANTS:
                found.add(PAYLOAD_CONSTANTS[const])
        return found

    reads = direct(body)

    root_vars = set(re.findall(r'JsonNode\s+(\w+)\s*=', body))
    for var in root_vars:
        for callee in set(re.findall(r'\b(\w+)\s*\([^)]*\b' + re.escape(var) + r'\b', body)):
            if callee in ("if", "while", "for", "switch", "return", "readTree", "equals", "valueOf"):
                continue
            dm = re.search(r'\b(?:private|public|protected)[^;{]*\b' + re.escape(callee)
                           + r'\s*\([^)]*\)\s*(?:throws [^{]*)?\{', src)
            if dm:
                reads |= direct(_block_after(src, dm.end() - 1))
    return reads


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
            all_variants = by_topic.get(topic) or []
            svc = os.path.relpath(p, WS).split(os.sep)[0]
            name = f[:-5]

            body = method_body(src, m.start())

            # Which event types does this listener actually act on? Anything it returns early for
            # is not its concern, and a contract for it says nothing about this consumer.
            handled = set(re.findall(r'EventType\.([A-Z_]+)\.name\(\)', body))
            handled |= set(re.findall(r'case\s+([A-Z_]+)\s*:', body))
            if handled:
                # A contract that declares no eventType is untyped -- the type is not part of what it
                # pins -- so it is a candidate for whatever the consumer handles. Excluding it
                # invented a gap for MapsIntegration's DispatchEventConsumer, whose only contract
                # (logistics_dispatch.groovy) carries no eventType header.
                variants = [v for v in all_variants if v[3] is None or v[3] in handled]
            else:
                variants = all_variants

            if not variants:
                why = ("no contract - skipped" if not all_variants
                       else f"no contract for {', '.join(sorted(handled))} - skipped")
                print(f"{name:<34}{topic:<30}{why}")
                continue
            # .get()/.path() are required reads; .has() is an existence probe, so a field only
            # ever probed is optional by construction and must not count as a mismatch.
            reads = field_reads(body, src)
            probes = field_reads(body, src, pattern=r'\.has\(\s*')
            # ...unless the probe is negated. `if (!node.has("x")) throw` is a fail-fast: it makes x
            # REQUIRED, and subtracting it was the one way this audit could under-report. It dropped
            # all four coordinate fields from MapsIntegration's DispatchEventConsumer, which throws
            # when they are missing, leaving its OK earned on orderId and deliveryAddress alone.
            fail_fast = field_reads(body, src, pattern=r'!\s*\w+\.has\(\s*')
            # A consumer that probes before reading tolerates absence -- treat as optional.
            reads -= (probes - fail_fast)

            # Requires an envelope only if it *reads* payload without a tolerant fallback.
            wants_envelope = "payload" in re.findall(r'\.get\(\s*"([^"]+)"', body)
            if re.search(r'has\("payload"\)\s*\?', body):
                wants_envelope = False  # ternary fallback: accepts flat too
            issues = []
            # a consumer is OK if ANY contract variant on the topic satisfies it
            ok_any = False
            for cname, rk, ak, _et in variants:
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
            if not reads:
                # Either way there is no required shape here, so a contract can neither confirm nor
                # deny one -- and OK would be a pass earned by reading nothing. Both of these were
                # reporting OK before 2026-09-12.
                why = ("every field is probed before use - none required" if probes
                       else "reads no fields here - delegates or only logs")
                print(f"{name:<34}{topic:<30}{why}")
                continue
            if ok_any:
                print(f"{name:<34}{topic:<30}OK")
            else:
                _, rk, ak, _et = variants[0]
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
