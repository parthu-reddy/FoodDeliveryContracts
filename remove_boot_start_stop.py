#!/usr/bin/env python3
"""Remove spring-boot-maven-plugin start/stop executions that break `mvn install`.

They boot the app during pre-integration-test and collide on the JMX port
("Failed to connect to MBean server at port 9001"), failing the build before stubs are installed.
Verified safe: no maven-failsafe-plugin and no *IT.java exist anywhere in the workspace, so nothing
runs against the booted app. Contract verification uses @SpringBootTest/standaloneSetup directly.
This is the resolution already documented in Phase 3.1's mistakes file.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

WORKSPACE = "/Users/parthureddy/Documents/Food Delivery.nosync"
BLOCK = re.compile(
    r"\s*<executions>\s*<execution>\s*<id>pre-integration-test</id>.*?</executions>",
    re.S)

changed, failed = [], []
for name in sorted(os.listdir(WORKSPACE)):
    p = os.path.join(WORKSPACE, name, "pom.xml")
    if not os.path.isfile(p):
        continue
    src = open(p).read()
    if "<id>pre-integration-test</id>" not in src:
        continue
    updated, n = BLOCK.subn("", src, count=1)
    if n == 0 or "<id>pre-integration-test</id>" in updated:
        failed.append(name)
        continue
    try:
        ET.fromstring(updated)          # must still parse as XML
    except ET.ParseError as exc:
        failed.append(f"{name} (XML broken: {exc})")
        continue
    open(p, "w").write(updated)
    changed.append(name)

print("removed from:", ", ".join(changed) or "none")
if failed:
    print("NEEDS MANUAL REVIEW:", ", ".join(failed))
    sys.exit(1)
