#!/usr/bin/env python3
"""
Validate HTTP contracts against the Feign clients that consume them.

Repointed 2026-08-21. This script used to read the abandoned git-broker stub tree at
FoodDeliveryContracts/META-INF/. That tree was deleted (it could never be wired up -- the
workspace path contains a space, which Spring Cloud Contract cannot parse in a git://file:///
URL -- and it had diverged from the live contracts in both directions). The source of truth is
each service's own src/test/resources/contracts/.

Two checks:

  A. Every @FeignClient(name = "...") resolves to a service that actually registers that name
     as its spring.application.name. A client naming a service nobody registers fails at
     runtime with "No instances available", unless it declares a url = ... override (which is
     how genuinely external services are addressed).

  B. Every HTTP contract's request URL matches a path declared by some Feign client that
     targets the contract's producing service. A contract nobody calls, or a caller whose path
     drifted from the contract, shows up here.

Exits non-zero on any failure. Also exits non-zero if it finds no HTTP contracts at all --
the previous version silently reported success against an empty directory, which is the
failure mode this file now exists to avoid.
"""

import os
import re
import sys
import glob

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAPPING_RE = re.compile(
    r'@(?:Get|Post|Put|Delete|Patch)Mapping\s*\(\s*(?:value\s*=\s*)?(?:path\s*=\s*)?["\']([^"\']+)["\']'
)
APP_NAME_RE = re.compile(r'application:\s*\n\s*name:\s*([A-Za-z0-9._-]+)')
FEIGN_RE = re.compile(r'@FeignClient\s*\(([^)]*)\)', re.DOTALL)
URL_RE = re.compile(r'\burl(?:Path)?\s*\(\s*["\']([^"\']+)["\']')


def read(path):
    with open(path, encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def registered_names():
    """module directory -> the name the service registers in Eureka."""
    names = {}
    for cfg in glob.glob(f"{REPO}/*/src/main/resources/application.yml"):
        module = os.path.relpath(cfg, REPO).split(os.sep)[0]
        found = APP_NAME_RE.search(read(cfg))
        if found:
            names[module] = found.group(1)
    return names


def feign_clients():
    """service name -> {"paths": set, "callers": [(module, file, has_url_override)]}"""
    clients = {}
    # Two glob depths on purpose. CommonLibrary became an aggregator of six modules on 2026-09-12,
    # so every @FeignClient it publishes now sits at <repo>/CommonLibrary/common-web/src/main/java/...
    # -- one level deeper than the single `*` reaches. Without the second pattern this validator saw
    # only the clients services declare themselves, and reported three contracts as matching no Feign
    # path when the paths were simply out of view.
    sources = (glob.glob(f"{REPO}/*/src/main/java/**/*.java", recursive=True)
               + glob.glob(f"{REPO}/*/*/src/main/java/**/*.java", recursive=True))
    for src in sources:
        body = read(src)
        if "@FeignClient" not in body:
            continue
        decl = FEIGN_RE.search(body)
        if not decl:
            continue
        attrs = decl.group(1)
        name = re.search(r'name\s*=\s*"([^"]+)"', attrs)
        if not name:
            continue
        name = name.group(1)
        base = re.search(r'path\s*=\s*"([^"]+)"', attrs)
        base = base.group(1) if base else ""
        entry = clients.setdefault(name, {"paths": set(), "callers": []})
        entry["paths"].update(base + p for p in MAPPING_RE.findall(body))
        entry["callers"].append((
            os.path.relpath(src, REPO).split(os.sep)[0],
            os.path.basename(src),
            bool(re.search(r'\burl\s*=\s*"', attrs)),
        ))
    return clients


def path_matches(contract_url, feign_path):
    """Feign paths carry {placeholders}; contracts carry concrete values."""
    return re.match("^" + re.sub(r"\{[^}]+\}", r"[^/]+", feign_path) + "$", contract_url) is not None


def main():
    names = registered_names()
    clients = feign_clients()
    registered = set(names.values())
    failures = []

    # --- Check A: Feign names resolve to something that registers them -------------------
    print("== A. Feign client names vs registered service names ==")
    for name in sorted(clients):
        callers = clients[name]["callers"]
        if name in registered:
            print(f"  OK       {name}")
            continue
        unresolvable = [c for c in callers if not c[2]]
        if not unresolvable:
            print(f"  external {name}  (all callers pin url=, no discovery needed)")
            continue
        print(f"  FAIL     {name}  -- no service registers this name")
        for module, filename, _ in unresolvable:
            print(f"             caller {module}/{filename} has no url= override")
            failures.append(f"{module}/{filename} calls unregistered service '{name}'")

    # --- Check B: contract URLs are covered by a Feign client on the producer ------------
    print("\n== B. HTTP contract URLs vs consuming Feign client paths ==")
    if failures:
        print("  NOTE: check A failed. A client that names the wrong service still declares real")
        print("        paths, but they get attributed to a service nobody registers -- so the")
        print("        producer looks uncovered here. Fix check A before trusting these results.")
    http_contracts = 0
    for module, service in sorted(names.items()):
        pattern = f"{REPO}/{module}/src/test/resources/contracts/**/*.groovy"
        for contract in sorted(glob.glob(pattern, recursive=True)):
            found = URL_RE.search(read(contract))
            if not found:
                continue  # messaging contract: no URL to check
            http_contracts += 1
            url = found.group(1)
            label = os.path.basename(contract)
            paths = clients.get(service, {}).get("paths", set())
            if not paths:
                print(f"  WARN     {service:32} {label:34} {url}")
                print(f"             no Feign client targets '{service}' -- contract is unconsumed")
                continue
            if any(path_matches(url, p) for p in paths):
                print(f"  OK       {service:32} {label:34} {url}")
            else:
                print(f"  FAIL     {service:32} {label:34} {url}")
                print(f"             no Feign path on '{service}' matches; declared: {sorted(paths)}")
                failures.append(f"{label}: {url} matches no Feign path on '{service}'")

    # --- Verdict ------------------------------------------------------------------------
    print(f"\nHTTP contracts checked: {http_contracts}")
    if http_contracts == 0:
        print("FAIL: no HTTP contracts found. Either the contract layout moved or this script "
              "is pointed at the wrong tree -- refusing to report success on an empty corpus.")
        return 2
    if failures:
        print(f"FAIL: {len(failures)} problem(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS: every Feign name resolves and every HTTP contract URL is covered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
