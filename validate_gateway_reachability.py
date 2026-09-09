#!/usr/bin/env python3
"""Every path the browser calls must be routed, served, and authorised.

Three layers have to agree for a request from the UI to reach a handler:

  1. the ApiGateway has a Path predicate matching it,
  2. some service's openapi.json actually declares it,
  3. GlobalJwtAuthFilter lets it through -- an rbac rule for some role, or a public/admin carve-out.

Nothing checked any of this. On 2026-09-09 an audit found 50 browser paths with no gateway route at
all (/api/v1/orders/**, /api/v1/restaurants/**, /api/v1/delivery/**, /api/v1/chat/** among them),
payment webhooks unroutable, the admin user-management screen refused by the internal-path filter,
and a customer refund call with no rbac rule. Every one of those call sites swallowed its failure,
so the screens showed empty states rather than errors.

Run from the workspace root:
    python3 FoodDeliveryContracts/validate_gateway_reachability.py
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GW = ROOT / "ApiGateway/src/main/resources/application.yml"
UI = ROOT / "FoodDeliveryAppUI/src"

# Served by the gateway itself or the UI's own express server, never routed downstream.
LOCAL = ("/api/config", "/api/logs")
# GlobalJwtAuthFilter's public list.
# Mirrors GlobalJwtAuthFilter: the public list, plus the /internal/auth carve-outs it names
# explicitly (initiate, verify, admin/otp, logout, sessions and sessions/*).
PUBLIC = ("/api/v1/webhooks/", "/webhooks/", "/olamaps/", "/actuator/", "/api/test/",
          "/api/v1/internal/auth/initiate", "/api/v1/internal/auth/verify",
          "/api/v1/internal/auth/admin/otp", "/api/v1/internal/auth/logout",
          "/api/v1/internal/auth/sessions")
# ONDC is parked (compile-and-run only); its adapter is not browser-facing.
SKIP_SERVICES = {"ONDCIntegrationService", "ApiGateway", "EurekaServer"}


def ant(pattern):
    rx = re.escape(pattern)
    rx = rx.replace(r"/\*\*", "(/.*)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.compile("^" + re.sub(r"\\\{[^}]*\\\}", "[^/]+", rx) + "$")


def load_gateway():
    routes, rbac = [], {}
    for doc in yaml.safe_load_all(GW.read_text()):
        if not doc:
            continue
        if "rbac" in doc:
            rbac = doc["rbac"].get("rules", {})
        try:
            rs = doc["spring"]["cloud"]["gateway"]["routes"]
        except (KeyError, TypeError):
            continue
        for r in rs:
            svc = str(r.get("uri", "")).replace("lb://", "")
            for p in r.get("predicates", []):
                if isinstance(p, str) and p.startswith("Path="):
                    for pat in p[len("Path="):].split(","):
                        routes.append((r["id"], svc, ant(pat.strip())))
    return routes, rbac


def load_served():
    served = []
    for spec in sorted(ROOT.glob("*/openapi.json")):
        if spec.parent.name in SKIP_SERVICES:
            continue
        try:
            paths = json.loads(spec.read_text()).get("paths", {})
        except (ValueError, OSError):
            continue
        for p in paths:
            served.append((spec.parent.name, re.compile(
                "^" + re.sub(r"\\\{[^}]*\\\}", "[^/]+", re.escape(p)) + "$")))
    return served


def browser_calls():
    """Literals passed to a client method or fetch/WebSocket -- not every string in the tree.

    Matching bare literals also caught things like the `url.includes('/api/v1/internal/auth/')`
    guard in zodiosConfig.ts, which is a substring test and not a request.
    """
    calls = defaultdict(set)
    call_rx = re.compile(
        r"""\.(?:get|post|put|patch|delete)\s*\(\s*['"`](/(?:api|ws)[^'"`\s${]*)['"`]""")
    raw_rx = re.compile(r"""(?:fetch|new WebSocket)\s*\(\s*[`'"]([^`'"$]*?)(?:\?|[`'"])""")
    for f in UI.rglob("*.ts*"):
        sf = str(f)
        if "/generated/" in sf or "/mocks/" in sf or ".test." in f.name or ".spec." in f.name:
            continue
        txt = f.read_text(errors="replace")
        for m in call_rx.finditer(txt):
            calls[m.group(1)].add(str(f.relative_to(ROOT)))
        for m in raw_rx.finditer(txt):
            if m.group(1).startswith(("/api", "/ws")):
                calls[m.group(1)].add(str(f.relative_to(ROOT)))
    return calls


def main():
    routes, rbac = load_gateway()
    served = load_served()
    calls = browser_calls()

    findings = []
    for path in sorted(calls):
        probe = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", "X", path)
        where = sorted(calls[path])[0]

        if probe.startswith(LOCAL):
            continue

        if not any(rx.match(probe) for _, _, rx in routes):
            findings.append(("NO GATEWAY ROUTE", path, where))
            continue

        if not any(rx.match(probe) for _, rx in served):
            findings.append(("ROUTED BUT NO SERVICE SERVES IT", path, where))
            continue

        if probe.startswith(PUBLIC) or probe.startswith("/api/v1/internal/admin/"):
            continue

        # GlobalJwtAuthFilter 403s /api/v1/internal/** outside the admin and auth carve-outs.
        if probe.startswith("/api/v1/internal/"):
            findings.append(("BLOCKED: /internal/ outside the admin carve-out", path, where))
            continue

        if not any(probe == a or probe.startswith(a + "/")
                   for paths in rbac.values() for a in paths):
            findings.append(("NO RBAC RULE FOR ANY ROLE", path, where))

    for kind, path, where in findings:
        print(f"[FAIL] {kind}\n         {path}\n         called in {where}")
    print(f"\n{len(calls) - len(findings)}/{len(calls)} browser paths are routed, served and authorised")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
