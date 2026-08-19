#!/usr/bin/env python3
"""Move every service from a file:// git broker to ~/.m2 stub resolution.

The workspace path contains a space; Spring Cloud Contract decodes %20 then re-parses it, so a
file:// repositoryRoot fails in the Maven plugin AND in BatchStubRunner at runtime. Local
development therefore resolves stubs from the local Maven repository instead. The GitHub broker is
reintroduced for CI only (Phase 8). See Phase1_Foundation/validation.md section 6.
"""
import os
import re
import sys

import yaml

WORKSPACE = "/Users/parthureddy/Documents/Food Delivery.nosync"
SKIP = {".git", "target", "node_modules", "venv", "dist", ".venv"}
changed = []


def walk(pred):
    for root, dirs, files in os.walk(WORKSPACE):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in files:
            if pred(f):
                yield os.path.join(root, f)


# 1. YAML: stubsMode LOCAL, drop repositoryRoot.
for path in sorted(walk(lambda f: f == "application-test.yml")):
    doc = yaml.safe_load(open(path)) or {}
    sr = doc.get("stubrunner")
    if not isinstance(sr, dict):
        continue
    before = dict(sr)
    sr["stubsMode"] = "LOCAL"
    sr.pop("repositoryRoot", None)
    if sr != before:
        yaml.safe_dump(doc, open(path, "w"), default_flow_style=False, sort_keys=False)
        changed.append(os.path.relpath(path, WORKSPACE))

# 2. Java: drop the repositoryRoot attribute; LOCAL mode needs only ids.
ATTR = re.compile(r',\s*repositoryRoot\s*=\s*"[^"]*"')
for path in sorted(walk(lambda f: f.endswith(".java"))):
    src = open(path).read()
    if "repositoryRoot" not in src:
        continue
    updated = ATTR.sub("", src)
    # StubsMode.REMOTE without a broker cannot resolve; these tests must use LOCAL.
    updated = updated.replace("StubRunnerProperties.StubsMode.REMOTE",
                              "StubRunnerProperties.StubsMode.LOCAL")
    if updated != src:
        open(path, "w").write(updated)
        changed.append(os.path.relpath(path, WORKSPACE))

for c in changed:
    print("  updated", c)
print(f"\n{len(changed)} file(s) switched to ~/.m2 stub resolution.")
