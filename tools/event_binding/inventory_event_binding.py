#!/usr/bin/env python3
"""Measure how much of the Kafka consumer surface still reads JSON by string key, and ratchet it.

Two jobs:

  --baseline   write baseline.json: the per-consumer read counts as they are RIGHT NOW.
  (default)    re-measure and FAIL if any consumer reads more string keys than its baseline,
               or if a consumer marked BOUND has regressed to reading any.

The ratchet is what makes this plan forward-only. A phase lowers a consumer's ceiling by editing
baseline.json; nothing may raise it. A rebind that gets reverted, a new `.path("x")` added to a
bound consumer, a delegate that grows a fresh string key -- each fails this check.

MEASUREMENT RULES, each one written because guessing here has already cost this codebase findings:

  * Walk the tree. Never glob. `*/src/main/**` misses CommonLibrary's six modules, which live at
    `CommonLibrary/common-*/src/main/`, and it does not error -- it counts less. That silently
    broke three validators on 2026-09-13 and it is why audit_consumer_contract_shapes.py currently
    sees 3 of 23 consumers.
  * Strip comments before concluding anything. `grep -l @KafkaListener` reports 24 consumer
    classes; one of them is OrderSagaOrchestrator, whose only match is a comment saying it has no
    listener. The real count is 23.
  * Discover constant files by name, never by hardcoded path. A hardcoded path is exactly how the
    existing audit broke.
  * Delegation is DECLARED, not inferred. A listener that hands a JsonNode to another package is
    still reading by string key, one frame deeper -- binding the listener alone just moves the
    untyped read. Each delegate below was read and confirmed. If a declared delegate path stops
    existing, this tool fails rather than quietly measuring less.
"""
import argparse
import json
import os
import re
import sys

WS = os.environ.get("FD_WORKSPACE", "/Users/parthureddy/Documents/Food Delivery.nosync")
HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, "baseline.json")

SKIP_DIRS = {".git", "target", "node_modules", "venv", ".hypothesis", ".schemathesis",
             "generated-test-sources", "build"}

# consumer class -> package roots it hands the JsonNode to. Confirmed by reading each one.
DELEGATES = {
    "RestaurantApplication/OrderEventConsumer": [
        "RestaurantApplication/src/main/java/com/fooddelivery/restaurant/service/state",
    ],
    "CustomerApplication/OrderEventConsumer": [
        "CustomerApplication/src/main/java/com/fooddelivery/order/service/state",
    ],
    "CustomerApplication/PaymentEventConsumer": [
        "CustomerApplication/src/main/java/com/fooddelivery/order/service/state",
    ],
    "DeliveryExecutiveApplication/OrderEventConsumer": [
        "DeliveryExecutiveApplication/src/main/java/com/fooddelivery/delivery/service/strategy",
    ],
}

READ_RE = r'\.(?:get|path|has|findValue|findPath|required)\(\s*'


def strip_comments(src):
    """Remove // and /* */ comments, preserving string literals verbatim."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == '"':
            j = i + 1
            while j < n and not (src[j] == '"' and src[j - 1] != "\\"):
                j += 1
            out.append(src[i:j + 1]); i = j + 1; continue
        if c == "'":
            j = i + 1
            while j < n and not (src[j] == "'" and src[j - 1] != "\\"):
                j += 1
            out.append(src[i:j + 1]); i = j + 1; continue
        if src.startswith("//", i):
            j = src.find("\n", i); i = n if j < 0 else j; continue
        if src.startswith("/*", i):
            j = src.find("*/", i); i = n if j < 0 else j + 2; continue
        out.append(c); i += 1
    return "".join(out)


def java_files(subpath="/src/main/java"):
    for root, dirs, files in os.walk(WS):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if subpath not in root.replace(os.sep, "/"):
            continue
        for f in files:
            if f.endswith(".java"):
                yield os.path.join(root, f)


def load_constants():
    """TOPIC_* and payload-key constants, found wherever they actually live."""
    topics, payload_keys = {}, {}
    for p in java_files():
        base = os.path.basename(p)
        if base in ("KafkaConstants.java", "OndcKafkaConfig.java"):
            src = strip_comments(open(p).read())
            for m in re.finditer(r'String\s+(TOPIC_[A-Z_0-9]+)\s*=\s*"([^"]+)"', src):
                topics[m.group(1)] = m.group(2)
        elif base == "EventPayloadConstants.java":
            src = strip_comments(open(p).read())
            for m in re.finditer(r'String\s+([A-Z_0-9]+)\s*=\s*"([^"]+)"', src):
                payload_keys[m.group(1)] = m.group(2)
    if not topics:
        sys.exit("FATAL: no TOPIC_* constants found. The constant file moved; fix this tool "
                 "rather than letting it measure less.")
    return topics, payload_keys


def string_key_reads(src, payload_keys):
    """Every JSON field read by string key: literals plus EventPayloadConstants indirection."""
    reads = re.findall(READ_RE + r'"([^"]+)"\s*\)', src)
    for const in re.findall(READ_RE + r'(?:EventPayloadConstants\.)?([A-Z][A-Z_0-9]{2,})\s*\)', src):
        if const in payload_keys:
            reads.append(payload_keys[const])
    # locally-declared field-name constants, e.g. `private static final String FIELD_ORDER_ID = "orderId";`
    local = dict(re.findall(r'String\s+([A-Z][A-Z_0-9]+)\s*=\s*"([^"]+)"', src))
    for const in re.findall(READ_RE + r'([A-Z][A-Z_0-9]+)\s*\)', src):
        if const in local:
            reads.append(local[const])
    return reads


def scan_dir(rel_dir, payload_keys):
    """Total string-key reads under a declared delegate package."""
    abs_dir = os.path.join(WS, rel_dir)
    if not os.path.isdir(abs_dir):
        sys.exit(f"FATAL: declared delegate path is gone: {rel_dir}\n"
                 "Something moved. Re-enumerate every consumer's delegates and update DELEGATES "
                 "before trusting any number this tool prints.")
    total, detail = 0, {}
    for root, dirs, files in os.walk(abs_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in sorted(files):
            if not f.endswith(".java"):
                continue
            src = strip_comments(open(os.path.join(root, f)).read())
            r = string_key_reads(src, payload_keys)
            if r:
                total += len(r)
                detail[os.path.relpath(os.path.join(root, f), WS)] = len(r)
    return total, detail


def collect():
    topics, payload_keys = load_constants()
    consumers = {}
    for p in java_files():
        src = strip_comments(open(p).read())
        if "@KafkaListener" not in src:
            continue
        rel = os.path.relpath(p, WS)
        svc = rel.split(os.sep)[0]
        cls = os.path.basename(p)[:-5]
        key = f"{svc}/{cls}"

        resolved, unresolved = set(), set()
        for m in re.finditer(r'@KafkaListener\s*\(', src):
            # brace-match the annotation args (they contain nested parens)
            i, depth = m.end() - 1, 0
            while i < len(src):
                if src[i] == "(":
                    depth += 1
                elif src[i] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            args = src[m.end():i]
            topics_arg = re.search(r'topics\s*=\s*(?:\{)?(.*?)(?:\}|,\s*groupId|$)', args, re.S)
            blob = topics_arg.group(1) if topics_arg else ""
            for lit in re.findall(r'"([^"]+)"', blob):
                if lit.startswith("${"):
                    continue
                resolved.add(lit)
            for const in re.findall(r'\.(TOPIC_[A-Z_0-9]+)', blob):
                (resolved if const in topics else unresolved).add(topics.get(const, const))

        own = string_key_reads(src, payload_keys)
        delegate_total, delegate_detail = 0, {}
        for d in DELEGATES.get(key, []):
            t, detail = scan_dir(d, payload_keys)
            delegate_total += t
            delegate_detail.update(detail)

        consumers[key] = {
            "path": rel,
            "topics": sorted(resolved),
            "unresolved_topics": sorted(unresolved),
            "event_types": sorted(set(re.findall(r'EventType\.([A-Z_0-9]+)', src))),
            "own_reads": len(own),
            "own_fields": sorted(set(own)),
            "delegate_reads": delegate_total,
            "delegate_detail": delegate_detail,
            "total_reads": len(own) + delegate_total,
            "binds_typed": bool(re.search(r'(?:readValue|bind|bindIf)\s*\(', src)),
        }
    return consumers


def report(consumers):
    print(f"{'consumer':<52}{'own':>5}{'deleg':>7}{'total':>7}  {'bound':>6}  topics")
    print("-" * 118)
    for k in sorted(consumers, key=lambda x: -consumers[x]["total_reads"]):
        c = consumers[k]
        print(f"{k:<52}{c['own_reads']:>5}{c['delegate_reads']:>7}{c['total_reads']:>7}"
              f"  {'Y' if c['binds_typed'] else '.':>6}  {','.join(c['topics']) or '(none)'}")
        if c["unresolved_topics"]:
            print(f"{'':<52}!! unresolved topic constant: {', '.join(c['unresolved_topics'])}")
    print()
    print(f"consumer classes: {len(consumers)}"
          f"   services: {len({k.split('/')[0] for k in consumers})}"
          f"   string-keyed reads (listeners + declared delegates): "
          f"{sum(c['total_reads'] for c in consumers.values())}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true", help="write baseline.json from current state")
    ap.add_argument("--report", action="store_true", help="print the table and exit 0")
    args = ap.parse_args()

    consumers = collect()

    if args.report:
        report(consumers)
        return 0

    if args.baseline:
        report(consumers)
        payload = {k: {"ceiling": v["total_reads"], "bound": False, "path": v["path"]}
                   for k, v in consumers.items()}
        json.dump(payload, open(BASELINE, "w"), indent=1, sort_keys=True)
        print(f"\nwrote {BASELINE} with {len(payload)} consumers")
        return 0

    if not os.path.exists(BASELINE):
        sys.exit(f"FATAL: no baseline at {BASELINE}. Run with --baseline first (Phase 1).")
    base = json.load(open(BASELINE))

    failures = []
    for k, want in sorted(base.items()):
        got = consumers.get(k)
        if got is None:
            failures.append(f"{k}: consumer disappeared. If it was deliberately deleted, remove it "
                            f"from baseline.json in the same change.")
            continue
        if got["total_reads"] > want["ceiling"]:
            failures.append(f"{k}: {got['total_reads']} string-keyed reads, ceiling is "
                            f"{want['ceiling']}. The ratchet only turns one way.")
        if want.get("bound") and got["total_reads"] != 0:
            # Name WHERE, not just how many. A bound consumer usually regresses in a delegate
            # package rather than in the listener file, and own_fields is empty in that case --
            # the first version of this message printed "still reads 1 field(s) by string key: "
            # with nothing after the colon, which tells the next person nothing.
            where = ", ".join(f"{os.path.basename(f)}({n})"
                              for f, n in sorted(got["delegate_detail"].items()))
            detail = f"in this listener: {', '.join(got['own_fields'][:6])}" if got["own_fields"] else ""
            if where:
                detail = (detail + "; " if detail else "") + f"in delegates: {where}"
            failures.append(f"{k}: marked BOUND but still reads {got['total_reads']} field(s) by "
                            f"string key -- {detail or 'source unclear, run --report'}")
        if want.get("bound") and not got["binds_typed"]:
            failures.append(f"{k}: marked BOUND but has no readValue(...) call.")
    for k in sorted(set(consumers) - set(base)):
        failures.append(f"{k}: new consumer not in baseline. Add it with its measured ceiling.")
    for k, c in sorted(consumers.items()):
        if c["unresolved_topics"]:
            failures.append(f"{k}: topic constant did not resolve ({', '.join(c['unresolved_topics'])}). "
                            f"A consumer whose topic cannot be resolved is a consumer nothing checks.")

    report(consumers)
    print()
    if failures:
        for f in failures:
            print("FAIL:", f)
        print(f"\n{len(failures)} ratchet violation(s).")
        return 1
    total = sum(c["total_reads"] for c in consumers.values())
    ceiling = sum(v["ceiling"] for v in base.values())
    bound = sum(1 for v in base.values() if v.get("bound"))
    print(f"OK: {total}/{ceiling} reads against ceiling, {bound}/{len(base)} consumers bound.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
