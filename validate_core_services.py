#!/usr/bin/env python3
"""
Structural validator for CoreServicesReview_2026-08-22.

Every check corresponds to a finding in ../02_Issues/00_issues-register.md and is written so that
it FAILS while the finding is open and PASSES once it is fixed. Run it from anywhere:

    python3 FoodDeliveryContracts/validate_core_services.py

Exit code 0 = every check passed. 1 = at least one finding is still open.

Deliberately has no third-party dependencies and does not need a database, a broker or a build.
"""
from __future__ import annotations
import os, re, sys, json, argparse
from pathlib import Path

def _find_workspace_root() -> Path:
    """Locate the workspace root so this runs in CI as well as on a laptop.

    Order: explicit override, then walk up from this file looking for the marker
    directories, then the current working directory. An absolute path hardcoded here
    would work on exactly one machine -- which is what it did until 2026-08-23.
    """
    env = os.environ.get("FOOD_DELIVERY_ROOT")
    if env:
        return Path(env).resolve()
    markers = {"CommonLibrary", "CustomerApplication", "RestaurantApplication"}
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if markers.issubset({c.name for c in candidate.iterdir() if c.is_dir()}):
            return candidate
    return Path.cwd().resolve()


ROOT = _find_workspace_root()
APPS = ["CustomerApplication", "RestaurantApplication",
        "DeliveryExecutiveApplication", "MapsIntegration"]
MODULES = APPS + ["CommonLibrary"]
UI = ROOT / "FoodDeliveryAppUI"

results: list[tuple[str, str, bool, str]] = []


def check(fid: str, name: str, ok: bool, detail: str = "") -> None:
    results.append((fid, name, ok, detail))


def main_java(mod: str):
    base = ROOT / mod / "src/main"
    if not base.exists():
        return
    for p in base.rglob("*.java"):
        yield p


def test_java(mod: str):
    base = ROOT / mod / "src/test"
    if not base.exists():
        return
    for p in base.rglob("*.java"):
        yield p


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------- I-1
def check_i1():
    p = ROOT / "CustomerApplication/src/main/java/com/fooddelivery/order/controller/AdminOrderManualController.java"
    if not p.exists():
        return check("I-1", "reversal catch block does not claim success", False, "file missing")
    lines = read(p).split("\n")
    bad = []
    has_transactional = "@org.springframework.transaction.annotation.Transactional" in read(p)
    for i, l in enumerate(lines):
        if re.search(r"catch\s*\(", l):
            for j in range(i + 1, min(i + 4, len(lines))):
                s = lines[j].strip()
                if s == "}":
                    break
                if "ResponseEntity.ok" in s:
                    bad.append(f"{rel(p)}:{j+1}")
    ok = not bad and has_transactional
    check("I-1", "reversal catch block does not fall through and is transactional", ok, "; ".join(bad) if bad else "not @Transactional")


# ---------------------------------------------------------------- I-2/I-13/I-14 + authz coverage
MAPPING = re.compile(r"@(?:org\.springframework\.web\.bind\.annotation\.)?(Get|Post|Put|Delete|Patch)Mapping")
AUTHZ = re.compile(r"@(PreAuthorize|PostAuthorize|Secured|RolesAllowed)")
CLASSDECL = re.compile(r"^\s*(public\s+)?(abstract\s+)?(final\s+)?class\s+\w+")

# Endpoints the platform intends to be anonymous, keyed by the mapping's own path.
#
# Allowlisting by *class* is wrong and was the first version of this check: it swept in
# RestaurantOutletController's "/api/v1/internal/admin/restaurants/all-with-location", an admin
# endpoint that happens to live in a class whose other endpoints are public catalog reads. Match
# the path, so a new endpoint in a public controller is reported until someone decides otherwise.
INTENTIONALLY_PUBLIC_PATHS = (
    "/api/v1/restaurants/{restaurantId}/catalog/items",
    "/api/v1/restaurants/{restaurantId}/menu/batch",
    "/api/v1/categories",
    "/api/v1/brands/{brandId}/categories",
    "/api/v1/outlets/{outletId}/categories/{categoryId}/timings",
    "/api/v1/brands/{brandId}/categories/{categoryId}/timings",
    "/api/v1/restaurants/{id}",
    "/api/v1/restaurants/nearby",
    "/api/v1/restaurants/brands/{brandId}/outlets",
)


def _is_public(endpoint) -> bool:
    m = re.search(r'"([^"]+)"', endpoint["text"])
    return bool(m) and m.group(1) in INTENTIONALLY_PUBLIC_PATHS


def endpoints():
    for mod in APPS:
        for p in main_java(mod):
            src = read(p)
            lines = src.split("\n")
            ci = next((i for i, l in enumerate(lines) if CLASSDECL.match(l)), len(lines))
            head = "\n".join(lines[:ci])
            if "@RestController" not in head and "@Controller" not in head:
                continue
            class_level = bool(AUTHZ.search(head))
            for i in range(ci, len(lines)):
                if not MAPPING.search(lines[i]):
                    continue
                method_level = bool(AUTHZ.search(lines[i]))
                j = i - 1
                while j > ci:
                    s = lines[j].strip()
                    if s.startswith("@"):
                        if AUTHZ.search(s):
                            method_level = True
                        j -= 1
                        continue
                    if s == "" or s.startswith("//") or s.startswith("*") or s.startswith("/*"):
                        j -= 1
                        continue
                    break
                k = i + 1
                while k < len(lines) and lines[k].strip().startswith("@"):
                    if AUTHZ.search(lines[k]):
                        method_level = True
                    k += 1
                yield dict(mod=mod, file=p, line=i + 1, cls=class_level, mth=method_level,
                           text=lines[i].strip())


def check_authz():
    eps = list(endpoints())
    unprot = [e for e in eps if not e["cls"] and not e["mth"]]
    flagged = [e for e in unprot if not _is_public(e)]
    check("AUTHZ", f"every endpoint has authorization or is allowlisted ({len(eps)} endpoints scanned)",
          not flagged,
          "; ".join(f"{rel(e['file'])}:{e['line']}" for e in flagged[:12]) +
          (f" … +{len(flagged)-12} more" if len(flagged) > 12 else ""))

    kyc = ROOT / "RestaurantApplication/src/main/java/com/fooddelivery/restaurant/controller/RestaurantKycController.java"
    hit = [e for e in unprot if e["file"] == kyc]
    check("I-2", "KYC verification callback is authorized", not hit,
          "; ".join(f"{rel(e['file'])}:{e['line']}" for e in hit))

    inv = ROOT / "CustomerApplication/src/main/java/com/fooddelivery/customer/controller/InternalOrderController.java"
    par = ROOT / "CustomerApplication/src/main/java/com/fooddelivery/order/controller/InternalOrderController.java"
    hit = [e for e in unprot if e["file"] in (inv, par)]
    check("I-13", "order invoice and participants are authorized", not hit,
          "; ".join(f"{rel(e['file'])}:{e['line']}" for e in hit))

    sus = ROOT / "DeliveryExecutiveApplication/src/main/java/com/fooddelivery/delivery/controller/InternalDeliveryController.java"
    fle = ROOT / "MapsIntegration/src/main/java/com/fooddelivery/mapsintegration/controller/IntegrationController.java"
    hit = [e for e in unprot if e["file"] in (sus, fle)]
    check("I-14", "driver suspension and fleet mutation are authorized", not hit,
          "; ".join(f"{rel(e['file'])}:{e['line']}" for e in hit))


# ---------------------------------------------------------------- I-3
def check_i3():
    p = ROOT / "CommonLibrary/src/main/java/com/fooddelivery/common/security/CommonSecurityConfig.java"
    src = read(p) if p.exists() else ""
    bad = 'requestMatchers("/api/v1/internal/**").permitAll()' in src.replace(" ", "").replace(
        'requestMatchers("/api/v1/internal/**").permitAll()', 'requestMatchers("/api/v1/internal/**").permitAll()')
    bad = re.search(r'requestMatchers\(\s*"/api/v1/internal/\*\*"\s*\)\s*\.permitAll\(\)', src) is not None
    check("I-3a", "/api/v1/internal/** is not blanket permitAll", not bad,
          f"{rel(p)}: carve-out still present" if bad else "")

    f = ROOT / "CommonLibrary/src/main/java/com/fooddelivery/common/security/SecurityContextFilter.java"
    fsrc = read(f) if f.exists() else ""
    verified = any(t in fsrc for t in ("verify", "Signature", "AuctionTokenService", "Hmac", "hmac"))
    check("I-3b", "SecurityContextFilter verifies the identity it trusts", verified,
          f"{rel(f)}: builds Authentication from unsigned headers" if not verified else "")


# ---------------------------------------------------------------- I-4
def check_i4():
    handlers = [
        ROOT / "MapsIntegration/src/main/java/com/fooddelivery/mapsintegration/websocket/TrackingWebSocketHandler.java",
        ROOT / "DeliveryExecutiveApplication/src/main/java/com/fooddelivery/delivery/websocket/LocationTrackingWebSocketHandler.java",
    ]
    bad = []
    for p in handlers:
        if not p.exists():
            continue
        src = read(p)
        m = re.search(r"handleTextMessage\s*\([^)]*\)\s*(?:throws[^{]*)?\{(.*?)\n    \}", src, re.S)
        body = m.group(1) if m else ""
        reads_driver = "driverId" in body
        compares = bool(re.search(r'getAttributes\(\)\.get\("userId"\)', body)) or "sessionUser" in body
        if reads_driver and not compares:
            bad.append(rel(p))
    check("I-4", "WebSocket handlers bind driverId to the session user", not bad, "; ".join(bad))


# ---------------------------------------------------------------- I-5
def check_i5():
    p = ROOT / "CommonLibrary/src/main/java/com/fooddelivery/common/outbox/service/OutboxProcessor.java"
    src = read(p) if p.exists() else ""
    sets = bool(re.search(r'headers\(\)\.add\(\s*(HEADER_EVENT_ID|"eventId")', src))
    check("I-5a", "OutboxProcessor publishes an eventId header", sets,
          f"{rel(p)}: only eventType and aggregateType are set" if not sets else "")

    readers, randoms = [], []
    for mod in MODULES:
        for f in main_java(mod):
            src = read(f)
            if '"eventId"' in src:
                readers.append(rel(f))
            if re.search(r'topic\s*\+\s*"-"\s*\+\s*partition|nameUUIDFromBytes', src):
                randoms.append(rel(f))
    check("I-5b", "no consumer falls back to a random idempotency key", not randoms,
          "; ".join(randoms))
    check("I-5c", f"{len(readers)} consumers read the eventId header", True,
          "informational: " + ", ".join(Path(r).name for r in readers))


# ---------------------------------------------------------------- I-8
def check_i8():
    defs = []
    for mod in MODULES:
        d = ROOT / mod / "src/main/resources/db/migration"
        if not d.exists():
            continue
        for p in d.rglob("*.sql"):
            src = read(p)
            for i, l in enumerate(src.split("\n")):
                if re.search(r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?outbox_events", l, re.I):
                    defs.append(f"{rel(p)}:{i+1}")
    check("I-8", "outbox_events is created by exactly one migration", len(defs) <= 1,
          f"{len(defs)} definitions: " + "; ".join(defs))


# ---------------------------------------------------------------- I-9
def check_i9():
    p = ROOT / "MapsIntegration/src/main/java/com/fooddelivery/mapsintegration/config/SecurityConfig.java"
    src = read(p) if p.exists() else ""
    bad = "web.ignoring()" in src.replace(" ", "")
    check("I-9a", "MapsIntegration does not bypass the filter chain", not bad,
          f"{rel(p)}: web.ignoring() present" if bad else "")
    ic = ROOT / "MapsIntegration/src/main/java/com/fooddelivery/mapsintegration/controller/IntegrationController.java"
    isrc = read(ic) if ic.exists() else ""
    leaks = "maps-key" in isrc and "olaMapsApiKey" in isrc
    check("I-9b", "no endpoint returns the Maps API key to the client", not leaks,
          f"{rel(ic)}: /config/maps-key returns the raw key" if leaks else "")


# ---------------------------------------------------------------- I-10
def check_i10():
    hits = []
    for mod in MODULES:
        for p in main_java(mod):
            src = read(p)
            if "CommandLineRunner" in src and "findAll()" in src:
                hits.append(rel(p))
    check("I-10", "no CommandLineRunner dumps a whole table at boot", not hits, "; ".join(hits))


# ---------------------------------------------------------------- I-15
def check_i15():
    hits = []
    for mod in MODULES:
        for p in main_java(mod):
            if p.name == "AppConstants.java":
                continue
            for i, l in enumerate(read(p).split("\n")):
                if "DEFAULT_CITY_ID" in l:
                    hits.append(f"{rel(p)}:{i+1}")
    check("I-15", "cityId is not hardwired at call sites", not hits,
          f"{len(hits)} sites: " + "; ".join(hits[:6]) + (" …" if len(hits) > 6 else ""))


def check_i16():
    tot = bad = 0
    per = []
    for mod in MODULES:
        m_bad = m_tot = 0
        for p in main_java(mod):
            m_tot += 1
            src = read(p)
            # Generated models are out of scope. openapi-generator output (CommonLibrary's
            # dto/{wallet,payment,maps,governmentid}) carries @Schema and @JsonProperty on every
            # accessor -- metadata Lombok cannot reproduce, so "replacing the boilerplate" would
            # silently strip it from the specs. It was never delomboked Lombok in the first place;
            # this check is about hand-maintained code, and generated sources are edited by
            # regenerating them, not by hand.
            if re.search(r'@Generated\b', src):
                m_tot -= 1
                continue
            acc = len(re.findall(r'\n\s+public\s+[\w<>,\[\].$ ]+\s+(get|set|is)[A-Z]\w*\(', src))
            # a HAND-WRITTEN builder is `public static class <Class>Builder`; the mere
            # presence of a nested class plus the word "Builder" is not evidence of one.
            has_builder = re.search(r'public static class \w+Builder\b', src) is not None
            # annotations may be written fully qualified (@lombok.Data)
            has_lombok = re.search(r'@(lombok\.)?(Getter|Setter|Data|Builder|Value)\b', src) is not None
            fails = (acc >= 6 or has_builder) and not has_lombok
            if fails:
                m_bad += 1
        per.append(f"{mod} {m_bad}/{m_tot}")
        bad += m_bad
        tot += m_tot
    check("I-16", "no delomboked boilerplate in main sources", bad == 0,
          f"{bad}/{tot} files — " + ", ".join(per))


def check_orphan_annotations():
    """An annotation with nothing to annotate. Does not compile.

    Two shapes, both produced by the 2026-08-23 re-lombok pass when it deleted an
    accessor and left the annotations that were attached to it:
      1. annotation ... blank lines ... class-closing brace
      2. annotation ... blank line(s) ... a constructor (e.g. a stranded @Override)
    """
    tail = re.compile(r'@\w[^\n]*\n(?:[ \t]*\n)+\}[ \t]*\n*$')
    hits = []
    for mod in MODULES:
        for p in main_java(mod):
            src = read(p)
            if tail.search(src):
                hits.append(rel(p)); continue
            # an @Override immediately preceding a constructor declaration
            for m in re.finditer(r'@(?:java\.lang\.)?Override[ \t]*\n(?:[ \t]*\n)*[ \t]*(?:public|protected|private)\s+(\w+)\s*\(', src):
                if m.group(1) == p.stem or m.group(1) in src.split("class ")[0]:
                    hits.append(f"{rel(p)} (@Override on a constructor)"); break
                # a nested class constructor
                if re.search(r'class\s+' + re.escape(m.group(1)) + r'\b', src):
                    hits.append(f"{rel(p)} (@Override on a constructor)"); break
    hits = sorted(set(hits))
    check("COMPILE", "no orphaned annotations (dangling after a removed member)", not hits,
          f"{len(hits)} files will not compile: " + "; ".join(hits[:8]))


# ---------------------------------------------------------------- I-17
def check_i17():
    hits = []
    for mod in MODULES:
        for p in test_java(mod):
            src = read(p)
            if re.search(r"assertThat\(true\)\.isTrue\(\)|assertTrue\(true\)|assertEquals\(1,\s*1\)", src):
                hits.append(rel(p))
    check("I-17", "no test asserts a tautology", not hits, f"{len(hits)} files: " +
          "; ".join(Path(h).name for h in hits))

    # the seven that name a package which does not exist
    ghost = ROOT / "CustomerApplication/src/main/java/com/fooddelivery/order/service/strategy"
    tdir = ROOT / "CustomerApplication/src/test/java/com/fooddelivery/order/service/strategy"
    orphan = tdir.exists() and not ghost.exists()
    check("I-17b", "no test package without a corresponding main package", not orphan,
          f"{rel(tdir)} has no main counterpart" if orphan else "")


# ---------------------------------------------------------------- I-18
def check_i18():
    check("I-18a", "a root aggregator pom exists for the CI build step",
          (ROOT / "pom.xml").exists(),
          "no pom.xml at the repository root, but ci-cd.yml runs `mvn clean install` there")
    wf = ROOT / ".github/workflows/ci-cd.yml"
    src = read(wf) if wf.exists() else ""
    check("I-18b", "CI does not reference Testcontainers", "estcontainer" not in src,
          "ci-cd.yml provisions docker:dind for Testcontainers, which are forbidden by project rule")
    check("I-18c", "CI builds the frontend", "setup-node" in src or "npm ci" in src,
          "no Node step in ci-cd.yml; vitest, msw and pacts never run")


# ---------------------------------------------------------------- I-19
def check_i19():
    pkg = UI / "package.json"
    if not pkg.exists():
        return
    j = json.loads(read(pkg))
    scripts = j.get("scripts", {})
    lint = scripts.get("lint", "")
    runs_eslint = "eslint" in lint
    check("I-19a", "an npm script runs ESLint", runs_eslint,
          f'scripts.lint = "{lint}" -- ESLint is never invoked')

    # The debt rules are warnings under a pinned budget; without --max-warnings the budget is
    # not enforced and new warnings cost nothing.
    budgeted = "--max-warnings" in lint
    check("I-19d", "the ESLint warning budget is pinned (ratchet)", (not runs_eslint) or budgeted,
          f'scripts.lint = "{lint}" -- no --max-warnings, so warning count is unbounded')

    ts = json.loads(re.sub(r"//.*", "", read(UI / "tsconfig.json")))
    co = ts.get("compilerOptions", {})
    check("I-19b", "tsconfig enables strict", co.get("strict") is True,
          "compilerOptions.strict is not set")

    # Raw fetch is banned by the project's own ESLint rule, which carries an allowlist of files
    # where no typed client exists (BFF-local routes, WebSocket signalling). Read that allowlist
    # rather than re-implementing the rule: two checks of the same thing that disagree are worse
    # than one. The bare-identifier form and the window/globalThis member form both count -- the
    # member form is how the ban was being bypassed until 2026-08-23.
    cfg = read(UI / "eslint.config.js")
    tail = cfg[cfg.rindex("no-restricted-syntax") - 2000:] if "no-restricted-syntax" in cfg else ""
    allowed = set(re.findall(r'"(src/[^"]+)"', tail))

    def _is_allowed(rel: str) -> bool:
        for a in allowed:
            if a.endswith("/**"):
                if rel.startswith(a[:-3]):
                    return True
            elif rel == a:
                return True
        return False

    fetches = []
    bare = re.compile(r"(?<![\w.])fetch\s*\(")
    member = re.compile(r"\b(?:window|globalThis|self)\s*\.\s*fetch\s*\(")
    for p in (UI / "src").rglob("*.ts*"):
        rel = str(p.relative_to(UI))
        if "/generated/" in rel or _is_allowed(rel):
            continue
        for i, l in enumerate(read(p).split("\n")):
            if "fetchEventSource" in l:
                continue
            if bare.search(l) or member.search(l):
                fetches.append(f"{rel}:{i+1}")
    check("I-19c", f"no unallowlisted raw fetch() in src ({len(allowed)} files allowlisted)",
          not fetches, f"{len(fetches)} call sites, e.g. " + "; ".join(fetches[:4]))


# ---------------------------------------------------------------- I-22
def check_i22():
    p = ROOT / "CommonLibrary/src/main/java/com/fooddelivery/common/outbox/repository/OutboxEventRepository.java"
    declared = "deleteProcessedEventsOlderThan" in (read(p) if p.exists() else "")
    callers = []
    for mod in MODULES:
        for f in main_java(mod):
            if f == p:
                continue
            if "deleteProcessedEventsOlderThan" in read(f):
                callers.append(rel(f))
    check("I-22", "the outbox retention query has a caller", (not declared) or bool(callers),
          "declared in OutboxEventRepository:23 and called from nowhere")


# ---------------------------------------------------------------- I-26
def check_i26():
    """An executor field must be named in a shutdown() call reached from @PreDestroy."""
    hits = []
    for mod in MODULES:
        for p in main_java(mod):
            src = read(p)
            for i, l in enumerate(src.split("\n")):
                m = re.search(r"(\w+)\s*=\s*(java\.util\.concurrent\.)?Executors\.new", l)
                if not m:
                    continue
                field = m.group(1)
                shuts = f"{field}.shutdown()" in src and "@PreDestroy" in src.replace(
                    "@jakarta.annotation.PreDestroy", "@PreDestroy")
                used = len(re.findall(rf"\b{re.escape(field)}\b", src)) > 1
                if not used:
                    hits.append(f"{rel(p)}:{i+1} ({field} is declared and never used)")
                elif not shuts:
                    hits.append(f"{rel(p)}:{i+1} ({field} has no @PreDestroy shutdown)")
    check("I-26", "every executor field is used and shut down", not hits, "; ".join(hits))


# ---------------------------------------------------------------- I-27 / I-29
def check_i27_i29():
    interrupted, empties = [], []
    EMPTY = re.compile(r"catch\s*\(([^)]*)\)\s*\{\s*\}", re.S)
    for mod in MODULES:
        for p in main_java(mod):
            src = read(p)
            for m in EMPTY.finditer(src):
                ln = src[:m.start()].count("\n") + 1
                if "InterruptedException" in m.group(1):
                    interrupted.append(f"{rel(p)}:{ln}")
                else:
                    empties.append(f"{rel(p)}:{ln}")
    check("I-27", "InterruptedException always restores the interrupt flag", not interrupted,
          "; ".join(interrupted))
    check("I-29", "no empty catch blocks", not empties,
          f"{len(empties)}: " + "; ".join(empties[:8]))


# ---------------------------------------------------------------- I-28
def check_i28():
    p = ROOT / "CommonLibrary/src/main/java/com/fooddelivery/common/outbox/service/OutboxProcessor.java"
    src = read(p) if p.exists() else ""
    bad = re.search(r"kafkaTemplate\.send\([^)]*\)\.get\(\s*\)", src) is not None
    check("I-28", "outbox send is awaited with a timeout", not bad,
          f"{rel(p)}: send().get() with no timeout blocks the scheduler and the transaction")


# ---------------------------------------------------------------- I-31
def check_i31():
    hits = []
    for mod in MODULES:
        for p in (ROOT / mod).rglob("*.java"):
            if "/target/" in str(p):
                continue
            if " " in p.name or re.search(r" \d+\.java$", p.name):
                hits.append(rel(p))
            elif p.stat().st_size == 0:
                hits.append(rel(p) + " (0 bytes)")
        stray = ROOT / mod / "patch.java"
        if stray.exists():
            hits.append(rel(stray) + " (outside any source set)")
    check("I-31", "no zero-byte, duplicate-named or stray .java files", not hits, "; ".join(hits))


# ---------------------------------------------------------------- I-32
def check_i32():
    p = ROOT / "ApiGateway/src/main/java/com/fooddelivery/apigateway/filter/GlobalJwtAuthFilter.java"
    src = read(p) if p.exists() else ""
    bounded = 'allowedPath + "/"' in src or "path.equals(allowedPath)" in src
    check("I-32", "gateway RBAC prefix match checks a path boundary", bounded,
          f"{rel(p)}: startsWith(allowedPath) with no boundary check")


# ---------------------------------------------------------------- I-34
def check_i34():
    """I-34's intent is 'a service that cannot read its configuration must not start'.

    `optional:` on the configserver import is NOT the right lever: without it the location
    is fatal in every environment lacking a Config Server -- including every test JVM -- and
    no test-side property can undo it, because ConfigServerConfigDataLoader throws on
    'not optional' before fail-fast is consulted. The mechanism Spring provides for this is
    `spring.cloud.config.fail-fast: true`, which tests switch off and production leaves on.
    """
    bad = []
    for mod in MODULES + ["ApiGateway"]:
        p = ROOT / mod / "src/main/resources/application.yml"
        if not p.exists():
            continue
        src = read(p)
        if "configserver" not in src:
            continue
        if not re.search(r'config:\s*\n\s*fail-fast:\s*true', src):
            bad.append(f"{mod} (no spring.cloud.config.fail-fast: true)")
    check("I-34", "an unreachable Config Server fails startup (fail-fast)", not bad,
          ", ".join(bad))


# ---------------------------------------------------------------- I-35
def check_i35():
    p = ROOT / "CommonLibrary/src/main/resources/db/migration/common/V20260811150000__add_common_entities.sql"
    src = read(p) if p.exists() else ""
    bad = "'PENDING'" in src
    check("I-35", "outbox status default is a real OutboxStatus", not bad,
          f"{rel(p)}: DEFAULT 'PENDING' is not in {{UNPROCESSED, IN_PROGRESS, PROCESSED, FAILED, DLQ}}")


# ---------------------------------------------------------------- I-36
def check_i36():
    p = UI / "server.ts"
    src = read(p) if p.exists() else ""
    open_cors = re.search(r"app\.use\(\s*cors\(\s*\)\s*\)", src) is not None
    check("I-36a", "BFF CORS restricts origins", not open_cors, "server.ts: app.use(cors()) with no options")
    m = re.search(r"app\.post\(\s*['\"]/api/logs['\"]", src)
    body = ""
    if m:
        # the handler body only, up to the closing `});` of app.post
        end = src.find("\n});", m.start())
        body = src[m.start():end if end > 0 else m.start() + 600]
    guarded = bool(m) and re.search(r"req\.headers\.authorization|verifyToken|requireAuth|401", body) is not None
    check("I-36b", "the log-ingest endpoint is authenticated", (not m) or guarded,
          "server.ts: POST /api/logs accepts unauthenticated input and spreads it into pino output")


# ---------------------------------------------------------------- I-37
def check_i37():
    hits = []
    for mod in MODULES:
        for p in main_java(mod):
            src = read(p)
            for i, l in enumerate(src.split("\n")):
                if 'setAllowedOrigins("*")' in l.replace(" ", "").replace('setAllowedOrigins("*")', 'setAllowedOrigins("*")'):
                    hits.append(f"{rel(p)}:{i+1}")
                elif re.search(r'setAllowedOrigins\(\s*"\*"\s*\)', l):
                    hits.append(f"{rel(p)}:{i+1}")
    hits = sorted(set(hits))
    check("I-37", "no WebSocket handler allows all origins", not hits, "; ".join(hits))



# ---------------------------------------------------------------- G-5 (pact <-> provider routes)
def _controller_routes(module: str):
    """Every (METHOD, path-template) the module's controllers expose."""
    base = ROOT / module / "src/main"
    routes = set()
    if not base.exists():
        return routes
    verb_of = {"Get": "GET", "Post": "POST", "Put": "PUT", "Delete": "DELETE", "Patch": "PATCH"}
    for f in base.rglob("*.java"):
        src = read(f)
        if "@RestController" not in src and "@Controller" not in src:
            continue
        lines = src.split("\n")
        ci = next((i for i, l in enumerate(lines)
                   if re.match(r"^\s*(public\s+)?(abstract\s+|final\s+)?class\s+\w+", l)), len(lines))
        head = "\n".join(lines[:ci])
        m = re.search(r'@RequestMapping\(\s*(?:value\s*=\s*)?"([^"]*)"', head)
        class_path = m.group(1) if m else ""
        for i in range(ci, len(lines)):
            mm = re.search(r'@(?:org\.springframework\.web\.bind\.annotation\.)?(Get|Post|Put|Delete|Patch)Mapping'
                           r'\(\s*(?:value\s*=\s*)?"([^"]*)"', lines[i])
            if mm:
                routes.add((verb_of[mm.group(1)], (class_path + mm.group(2)) or "/"))
                continue
            mm = re.search(r'@(?:org\.springframework\.web\.bind\.annotation\.)?(Get|Post|Put|Delete|Patch)Mapping\s*(\(\s*\))?\s*$',
                           lines[i])
            if mm:
                routes.add((verb_of[mm.group(1)], class_path or "/"))
    return routes


def _matches(actual: str, template: str) -> bool:
    """A concrete pact path against a Spring path template ({id}, {id:regex}, **)."""
    pattern = re.sub(r"\{[^}]*\}", "[^/]+", re.escape(template).replace("\\{", "{").replace("\\}", "}"))
    pattern = pattern.replace("\\*\\*", ".*").replace("\\*", "[^/]*")
    return re.fullmatch(pattern, actual) is not None


def check_pact_routes():
    """REMOVED 2026-08-27 -- Pact was deleted from this platform on purpose.

    This check asserted that every consumer pact interaction hits a route its provider exposes.
    PlatformHardening Phase 7 deleted Pact entirely, on the finding that the five interactions
    only asserted a mock the frontend wrote against expectations the frontend wrote -- nothing
    ever replayed them against a provider. The one thing they checked that Zod does not is field
    PRESENCE, and that is now covered by declaring `required` in the specs, which covers every
    endpoint rather than five.

    Keeping the check would make the build red for not doing something the platform decided
    against. It is no longer registered in main(); the body is kept as the record of why.
    """
    raise NotImplementedError("Pact was removed deliberately; see Phase7_SchemaStrictness")

# The committed openapi.json files are refreshed by hand: the springdoc-openapi-maven-plugin in
# each pom has no <executions>, so no build produces them. They had drifted 35 routes behind the
# controllers by 2026-08-23 -- including a DELETE the UI was calling through the typed client,
# which could not exist because the generator never saw it.
#
# Ratcheted to 0 on 2026-08-27. The gap closed once OpenApiJsonMediaTypeCustomizer was imported
# into every spec-generation context and each module's openapi.json was refreshed from the
# openapi.json its own build produces: 221 controller routes, 0 missing. It was 35 while the
# committed specs were refreshed by hand. The number can only go down -- do not raise it to make
# a build pass; regenerate the spec instead.
SPEC_DRIFT_BUDGET = 0

SPEC_MODULES = ["CustomerApplication", "RestaurantApplication", "DeliveryExecutiveApplication",
                "MapsIntegration", "WalletService", "IdentityService", "PaymentGatewayIntegration",
                "CampaignService", "LedgerService", "CommunicationService"]


def check_spec_matches_controllers():
    def norm(t):
        return re.sub(r"\{[^}]*\}", "{}", t)

    missing, scanned = [], 0
    for mod in SPEC_MODULES:
        spec_path = ROOT / mod / "openapi.json"
        routes = _controller_routes(mod)
        if not spec_path.exists() or not routes:
            continue
        try:
            spec = json.loads(read(spec_path))
        except Exception as e:
            missing.append(f"{mod}: spec unreadable ({e})")
            continue
        declared = set()
        for path, ops in (spec.get("paths") or {}).items():
            for verb in ops:
                if verb.lower() in ("get", "post", "put", "delete", "patch"):
                    declared.add((verb.upper(), norm(path)))
        for method, template in sorted(routes):
            scanned += 1
            if (method, norm(template)) not in declared:
                missing.append(f"{mod}: {method} {template}")

    ok = len(missing) <= SPEC_DRIFT_BUDGET
    check("SPEC-DRIFT",
          f"controller routes present in openapi.json ({scanned} routes, budget {SPEC_DRIFT_BUDGET})",
          ok,
          f"{len(missing)} missing, over budget by {len(missing) - SPEC_DRIFT_BUDGET}: "
          + "; ".join(missing[:6]))


# ---------------------------------------------------------------- G-10
def check_g10():
    f = ROOT / "CommonLibrary/src/main/java/com/fooddelivery/common/filter/IdempotencyFilter.java"
    if not f.exists():
        return
    registered = []
    for mod in MODULES:
        for p in main_java(mod):
            if p == f:
                continue
            src = read(p)
            if "IdempotencyFilter" in src and ("addFilter" in src or "FilterRegistrationBean" in src):
                registered.append(rel(p))
    check("G-10", "IdempotencyFilter is registered in a filter chain", bool(registered),
          "written and tested, added to no chain — HTTP idempotency is off")


def run():
    for fn in (check_i1, check_orphan_annotations, check_authz, check_i3, check_i4, check_i5, check_i8, check_i9,
               check_i10, check_i15, check_i16, check_i17, check_i18, check_i19, check_i22,
               check_i26, check_i27_i29, check_i28, check_i31, check_i32, check_i34,
               check_i35, check_i36, check_i37, check_spec_matches_controllers, check_g10):
        try:
            fn()
        except Exception as e:  # a broken check must not look like a passing one
            check(fn.__name__, "check raised", False, f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="only print failures")
    args = ap.parse_args()

    if not ROOT.exists():
        sys.exit(f"workspace not found: {ROOT}")

    run()
    failed = [r for r in results if not r[2]]
    width = max(len(r[0]) for r in results)
    for fid, name, ok, detail in results:
        if args.quiet and ok:
            continue
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {fid:<{width}}  {name}")
        if detail and not ok:
            print(f"         └─ {detail}")
        elif detail and ok and detail.startswith("informational"):
            print(f"         └─ {detail}")
    print()
    print(f"{len(results) - len(failed)}/{len(results)} checks passed, {len(failed)} findings open")
    sys.exit(1 if failed else 0)
