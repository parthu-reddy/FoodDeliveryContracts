#!/usr/bin/env python3
"""Every dead-lettered record must be logged with the position the admin DLQ retry endpoints replay by.

The retry endpoints (POST /api/v1/internal/admin/{wallet|payments|orders}/dlq/retry) take
{"dltTopic", "partition", "offset"}. Records reach a DLT two ways, and both must print that body:

  * @RetryableTopic listeners -> <topic>-dlt, consumed by the listener's @DltHandler. The handler sees
    the record's own position and must log it through KafkaHeaderUtils.deadLetterPosition.
  * listeners without @RetryableTopic -> the shared DefaultErrorHandler in common-messaging KafkaConfig
    -> <topic>.DLT, which nothing consumes. KafkaConfig's recoverer must log the written position, and
    must let Kafka choose the partition: it creates each .DLT with ONE partition, so routing to the
    failed record's own partition fails for anything not read from partition 0.

Annotations are matched qualified or not (@DltHandler and @org.springframework.kafka.annotation.DltHandler
both occur); a pattern that misses the qualified form undercounts silently.

Run from the workspace root: python3 FoodDeliveryContracts/validate_dlt_positions.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"target", "node_modules", ".git", "venv"}
KAFKA_CONFIG = ROOT / "CommonLibrary/common-messaging/src/main/java/com/fooddelivery/common/config/KafkaConfig.java"


def ann(name):
    return re.compile(r"@(?:[\w.]*\.)?" + name + r"\b")


def strip_comments(src):
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def method_bodies_after(src, annotation):
    """(line, signature, body) for each method carrying the annotation."""
    out = []
    for m in annotation.finditer(src):
        sig = re.compile(r"\b(?:public|protected|private)?\s*void\s+(\w+)\s*\(").search(src, m.end())
        if not sig:
            continue
        brace = src.index("{", sig.end())
        depth, i = 1, brace + 1
        while depth and i < len(src):
            depth += {"{": 1, "}": -1}.get(src[i], 0)
            i += 1
        out.append((src.count("\n", 0, m.start()) + 1, sig.group(1), src[brace + 1:i - 1]))
    return out


failures, handlers, retryable_files = [], 0, 0
for path in sorted(ROOT.glob("*/src/main/**/*.java")):
    if SKIP & set(path.relative_to(ROOT).parts):
        continue
    src = strip_comments(path.read_text(encoding="utf-8"))
    rel = path.relative_to(ROOT)
    listeners = len(ann("KafkaListener").findall(src))
    if not listeners:
        continue
    dlt = method_bodies_after(src, ann("DltHandler"))
    handlers += len(dlt)
    if len(ann("RetryableTopic").findall(src)) >= listeners:
        retryable_files += 1
        if len(dlt) < listeners:
            failures.append(f"V3 {rel}: @RetryableTopic listener without a @DltHandler -- its DLT records are "
                            "logged by Spring's default handler, not with a replayable position")
    for line, name, body in dlt:
        if "deadLetterPosition(" not in body:
            failures.append(f"V1 {rel}:{line} {name}(): does not log KafkaHeaderUtils.deadLetterPosition(...)")
        if re.search(r"System\.(err|out)\.print", body):
            failures.append(f"V2 {rel}:{line} {name}(): writes to System.err/out, outside the JSON log stream")

if handlers == 0 or retryable_files == 0:
    failures.append(f"SELF found {handlers} @DltHandlers in {retryable_files} @RetryableTopic files -- the walk read nothing")

config = strip_comments(KAFKA_CONFIG.read_text(encoding="utf-8"))
if re.search(r"new\s+(?:[\w.]*\.)?TopicPartition\s*\([^;]*\.partition\(\)", config):
    failures.append("V4 KafkaConfig: DLT resolver routes to the failed record's partition; each .DLT has one partition")
if "PositionLoggingDeadLetterPublishingRecoverer" not in config:
    failures.append("V4 KafkaConfig: DefaultErrorHandler recoverer does not log the written DLT position")

print(f"checked {handlers} @DltHandlers ({retryable_files} @RetryableTopic listener files) and KafkaConfig")
for f in failures:
    print("FAIL", f)
print("OK" if not failures else f"FAILED: {len(failures)} problem(s)")
sys.exit(1 if failures else 0)
