#!/usr/bin/env python3
"""Make messaging producer contract tests boot a minimal context instead of the whole service.

@TestConfiguration is treated as *additional* config, so Spring Boot still climbs to the real
@SpringBootApplication and starts JPA/Flyway/Redis/controllers -- which fails on H2 (postgis,
unknown data types) and on missing Redis beans. Promoting TestConfig to @SpringBootConfiguration
makes it the context root, so only Kafka is auto-configured.

Also pins the verifier's Kafka consumer to auto-offset-reset=earliest: the @KafkaListener can be
assigned after the trigger sends, and the default (latest) silently misses the message.

Proven on DeliveryExecutiveApplication (MessagingTest: 2/2 green) before rollout.
"""
import os
import re
import sys

import yaml

WORKSPACE = "/Users/parthureddy/Documents/Food Delivery.nosync"
PROFILE = "contract-test"

BOOT_CONFIG = """    @org.springframework.boot.SpringBootConfiguration
    @org.springframework.boot.autoconfigure.EnableAutoConfiguration(exclude = {
            org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration.class,
            org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration.class,
            org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration.class,
            org.springframework.boot.autoconfigure.data.redis.RedisRepositoriesAutoConfiguration.class,
            org.springframework.boot.autoconfigure.flyway.FlywayAutoConfiguration.class
    })
    static class TestConfig {"""

changed = []

for root, dirs, files in os.walk(WORKSPACE):
    dirs[:] = [d for d in dirs if d not in {".git", "target", "node_modules", "venv"}]
    if "BaseMessagingClass.java" not in files:
        continue
    path = os.path.join(root, "BaseMessagingClass.java")
    service = os.path.relpath(path, WORKSPACE).split(os.sep)[0]
    src = open(path).read()
    before = src

    # 1. Promote the nested test config to a context root.
    src = re.sub(
        r"    @org\.springframework\.boot\.test\.context\.TestConfiguration\s*\n\s*\n?    static class TestConfig \{",
        BOOT_CONFIG, src, count=1)

    # 2. Force the contract-test profile (replacing any other profile choice).
    if "@ActiveProfiles" in src or "ActiveProfiles(" in src:
        src = re.sub(r'@(?:org\.springframework\.test\.context\.)?ActiveProfiles\("[^"]*"\)',
                     f'@org.springframework.test.context.ActiveProfiles("{PROFILE}")', src)
    else:
        src = src.replace("@AutoConfigureMessageVerifier",
                          f'@org.springframework.test.context.ActiveProfiles("{PROFILE}")\n@AutoConfigureMessageVerifier', 1)

    if src != before:
        open(path, "w").write(src)
        changed.append(service)
        print(f"  patched {service}/.../BaseMessagingClass.java")

    # 3. Ensure the profile pins the verifier's Kafka consumer to earliest.
    prof = os.path.join(WORKSPACE, service, "src/test/resources", f"application-{PROFILE}.yml")
    doc = {}
    if os.path.exists(prof):
        doc = yaml.safe_load(open(prof)) or {}
    spring = doc.setdefault("spring", {})
    consumer = spring.setdefault("kafka", {}).setdefault("consumer", {})
    if consumer.get("auto-offset-reset") != "earliest":
        consumer["auto-offset-reset"] = "earliest"
        consumer["group-id"] = "contract-test-verifier"
        yaml.safe_dump(doc, open(prof, "w"), default_flow_style=False, sort_keys=False)
        print(f"  pinned  {service}/src/test/resources/application-{PROFILE}.yml")

print(f"\nPatched {len(changed)} base class(es): {', '.join(changed) or 'none'}")
