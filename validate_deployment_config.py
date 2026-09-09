#!/usr/bin/env python3
"""Deployment/ config: placeholders resolve, prod credentials have no fallback, no debug profile.

These six assertions lived in LedgerService as DeploymentConfigResolvesTest and DeploymentProfileTest.
They assert facts about the *Deployment* repository, which is a separate repo, so they made one
service's build depend on another repo being checked out beside it. It never was: the individual
service workflow checks out only the service, ParentPOM, IdentitySigning and CommonLibrary, so all
six errored with "Cannot locate Deployment/" in the CI run of 2026-09-09 — and would have in any of
the other twenty service builds had they carried the same tests.

They belong with the other fleet gates, which the reactor workflow runs as its "Static validators"
step, after checking Deployment out to workspace/Deployment.

Run from the workspace root:
    python3 FoodDeliveryContracts/validate_deployment_config.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPLOYMENT = ROOT / "Deployment"
COMPOSE = DEPLOYMENT / "docker-compose.yml"

MONEY_SERVICES = ["ledger-service", "payment-gateway", "wallet-service", "customer-service"]
SERVICE_CONFIGS = ["payment-service.yml", "ledger-service.yml", "customer-service.yml"]

PLACEHOLDER = re.compile(r"\$\{([A-Za-z0-9_.]+)(:[^}]*)?\}")

failures = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        failures.append(name)
        for line in str(detail).splitlines():
            print(f"        {line}")


def strip_comments(yaml_text):
    """Comments are prose. A comment explaining a placeholder is not a placeholder -- this check
    first flagged its own explanatory note in payment-service.yml."""
    return re.sub(r"(?m)^\s*#[^\n]*", "", yaml_text)


def compose_supplied_vars(compose):
    return set(re.findall(r"^\s*-\s*([A-Z][A-Z0-9_]*)=", compose, re.MULTILINE))


def main():
    if not DEPLOYMENT.is_dir():
        print(f"FAIL: cannot locate Deployment/ at {DEPLOYMENT}")
        return 1
    if not COMPOSE.exists():
        print(f"FAIL: cannot locate {COMPOSE}")
        return 1

    compose = COMPOSE.read_text(encoding="utf-8")

    # -- the locator is reading what it thinks it is ------------------------------------------
    check("0 compose carries the services these checks claim to check",
          bool(compose.strip()) and "payment-gateway" in compose and "SPRING_PROFILES_ACTIVE" in compose,
          "compose file does not mention payment-gateway or sets no profiles at all")

    # -- every non-prod placeholder resolves ---------------------------------------------------
    supplied = compose_supplied_vars(compose)
    unresolvable = {}
    for name in SERVICE_CONFIGS:
        f = DEPLOYMENT / name
        if not f.exists():
            continue
        for doc in re.split(r"(?m)^---\s*$", strip_comments(f.read_text(encoding="utf-8"))):
            if "on-profile: prod" in doc or 'on-profile: "prod"' in doc:
                continue
            missing = [m.group(1) for m in PLACEHOLDER.finditer(doc)
                       if m.group(2) is None and m.group(1) not in supplied]
            if missing:
                unresolvable.setdefault(name, []).extend(missing)
    check("1 every non-prod placeholder resolves without secrets", not unresolvable,
          f"no default and not supplied by docker-compose, so the service cannot start outside prod: {unresolvable}")

    # -- prod credentials must not be able to boot on a placeholder ----------------------------
    payment = DEPLOYMENT / "payment-service.yml"
    if payment.exists():
        prod_doc = None
        for doc in re.split(r"(?m)^---\s*$", strip_comments(payment.read_text(encoding="utf-8"))):
            if "on-profile: prod" in doc:
                prod_doc = doc
        if prod_doc is None:
            check("2 prod gateway credentials have no defaults", False,
                  "payment-service.yml has no prod profile document")
        else:
            with_defaults = [m.group(1) for m in PLACEHOLDER.finditer(prod_doc)
                             if m.group(2) is not None
                             and ("KEY" in m.group(1) or "SECRET" in m.group(1) or "CLIENT_ID" in m.group(1))]
            check("2 prod gateway credentials have no defaults", not with_defaults,
                  f"these prod credentials have a fallback, so the service would boot on a placeholder: {with_defaults}")

    # -- no service is deployed with the debug profile -----------------------------------------
    offenders, current = [], None
    for line in compose.split("\n"):
        m = re.match(r"^ {2}([a-z0-9-]+):\s*$", line)
        if m:
            current = m.group(1)
        if "SPRING_PROFILES_ACTIVE" in line and not line.strip().startswith("#"):
            value = line[line.index("SPRING_PROFILES_ACTIVE") + len("SPRING_PROFILES_ACTIVE"):]
            if "debug" in value:
                offenders.append(f"{current or '?'} -> {line.strip()}")
    check("3 no money service appends debug to its profile list", not offenders,
          "the debug profile registers the mock gateway strategies and marks every order paid "
          "without taking money:\n" + "\n".join(offenders))

    # -- and each takes its profile from the environment ----------------------------------------
    missing = []
    for service in MONEY_SERVICES:
        at = compose.find("\n  " + service + ":")
        if at < 0:
            continue
        block = compose[at:at + 6000]
        # Trim at the next top-level service so a neighbour's setting cannot satisfy this one.
        nxt = -1
        for i in range(1, len(block) - 3):
            if block[i] == "\n" and block[i + 1:i + 3] == "  " and block[i + 3] not in (" ", "#"):
                nxt = i
                break
        own = block[:nxt] if nxt > 0 else block
        if "SPRING_PROFILES_ACTIVE=${SPRING_PROFILES_ACTIVE" not in own:
            missing.append(service)
    check("4 every money service takes its profile from the environment", not missing,
          f"these money services do not take SPRING_PROFILES_ACTIVE from the environment: {missing}")

    print(f"\n{5 - len(failures)}/5 deployment config checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
