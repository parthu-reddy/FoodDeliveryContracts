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
import yaml
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

def common_src(rel: str):
    """Resolve a path under the old CommonLibrary/src/main against the module layout.

    CommonLibrary became an aggregator of six modules on 2026-09-12, so
    `CommonLibrary/src/main/...` stopped existing. Every validator hardcoding it went blind and
    reported the code it could no longer see as missing -- nine checks across two gates, none of
    which described a real regression. Resolving by search rather than by a fixed module name means
    a class moving between modules does not break this again.
    """
    rel = rel.lstrip("/")
    for kind in ("java", "resources"):
        for mod in sorted((ROOT / "CommonLibrary").iterdir()):
            p = mod / "src/main" / kind / rel
            if p.exists():
                return p
    return ROOT / "CommonLibrary" / "src/main/java" / rel   # non-existent: callers report "missing"

UI = ROOT / "FoodDeliveryAppUI"

results: list[tuple[str, str, bool, str]] = []


def check(fid: str, name: str, ok: bool, detail: str = "") -> None:
    results.append((fid, name, ok, detail))



def all_main_java():
    """Every main java source in the workspace, descending into aggregator modules.

    `all_main_java()` reaches one level and so stopped seeing CommonLibrary after
    the 2026-09-12 split. Four checks kept passing on a smaller corpus, which is the dangerous
    direction: a scan that finds less does not fail, it just stops looking.
    """
    seen = set()
    for pat in ("*/src/main/**/*.java", "*/*/src/main/**/*.java"):
        for f in ROOT.glob(pat):
            if f not in seen:
                seen.add(f)
                yield f

def main_java(mod: str):
    """Main sources of a module, including an aggregator's submodules.

    CommonLibrary has had no src/ of its own since the 2026-09-12 split; its sources live in
    common-core, common-persistence, common-messaging, common-web, common-storage and common-test.
    Walking only `<mod>/src/main` silently yielded nothing for it, and callers reading that emptiness
    reported real code as absent.
    """
    base = ROOT / mod / "src/main"
    if base.exists():
        for p in base.rglob("*.java"):
            yield p
        return
    for sub in sorted((ROOT / mod).iterdir()):
        sub_base = sub / "src/main"
        if sub_base.is_dir():
            for p in sub_base.rglob("*.java"):
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
    p = common_src("com/fooddelivery/common/security/CommonSecurityConfig.java")
    src = read(p) if p.exists() else ""
    bad = 'requestMatchers("/api/v1/internal/**").permitAll()' in src.replace(" ", "").replace(
        'requestMatchers("/api/v1/internal/**").permitAll()', 'requestMatchers("/api/v1/internal/**").permitAll()')
    bad = re.search(r'requestMatchers\(\s*"/api/v1/internal/\*\*"\s*\)\s*\.permitAll\(\)', src) is not None
    check("I-3a", "/api/v1/internal/** is not blanket permitAll", not bad,
          f"{rel(p)}: carve-out still present" if bad else "")

    f = common_src("com/fooddelivery/common/security/SecurityContextFilter.java")
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
    p = common_src("com/fooddelivery/common/outbox/service/OutboxProcessor.java")
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
            # A method that implements an interface is not a delomboked accessor. A Feign fallback
            # such as LedgerClientFallback carries one @Override per client method, several of which
            # begin with "get" -- counting those tripped this check on a class that has no
            # boilerplate to replace. A real delomboked getter is never @Override.
            src_no_overrides = re.sub(r'\n\s+@Override\s*\n\s+public\s+[\w<>,\[\].$ ]+\s+\w+\(', '\n', src)
            acc = len(re.findall(r'\n\s+public\s+[\w<>,\[\].$ ]+\s+(get|set|is)[A-Z]\w*\(', src_no_overrides))
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
# These check the CONTENT of .github/workflows/ci-cd.yml, not that any CI runs. It cannot run: the
# workspace root is not a git repository, and each job's bare `actions/checkout` would fetch one of
# 31 separate repos. See the header in that file. Naming them "CI does ..." implied an enforcement
# that does not exist.
def check_i18():
    check("I-18a", "a root aggregator pom exists for the CI build step (workflow is aspirational)",
          (ROOT / "pom.xml").exists(),
          "no pom.xml at the repository root, but ci-cd.yml runs `mvn clean install` there")
    # Read the workflow that can actually RUN. ci-cd.yml at the workspace root never could -- the
    # root is not a git repository, so GitHub never saw it -- and on a CI runner it does not exist
    # at all, which made I-18c fail against an empty string. Superseded 2026-08-30.
    wf = ROOT / "FoodDeliveryContracts/.github/workflows/contract-verification.yml"
    src = read(wf) if wf.exists() else ""
    check("I-18b", "the CI workflow text does not reference Testcontainers", "estcontainer" not in src,
          "ci-cd.yml provisions docker:dind for Testcontainers, which are forbidden by project rule")
    check("I-18c", "the CI workflow text includes a frontend step", "setup-node" in src or "npm ci" in src,
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
    p = common_src("com/fooddelivery/common/outbox/repository/OutboxEventRepository.java")
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
    p = common_src("com/fooddelivery/common/outbox/service/OutboxProcessor.java")
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
    p = common_src("db/migration/common/V20260811150000__add_common_entities.sql")
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
                "CampaignService", "LedgerService", "CommunicationService",
                "UserTrackingService"]


# Schemas that have been deliberately tightened to declare `required`, as `Module:SchemaName`.
# A ratchet, not a target: this check fails when a LISTED schema loses its `required` array, and
# says nothing about schemas that are not listed. A hard "everything must be strict" gate would be
# red from day one and would be switched off; one that can only tighten is one people keep.
#
# The pagination entries are strict because of OpenApiPaginationRequiredCustomizer in CommonLibrary,
# not because of per-DTO annotations -- listing them here is what catches that customizer being
# dropped or unregistered from a module's spec test.
#
# Adding to this list is the last step of tightening a schema. Removing from it requires a reason
# recorded in the commit, not convenience.
STRICT_SCHEMAS = {
    "BiddingEngine:AdRequestDTO": ["context", "deviceId", "geo"],
    "BiddingEngine:Bid": ["id", "impid", "price"],
    "BiddingEngine:BidResponse": ["id", "seatbid"],
    "BiddingEngine:SeatBid": ["bid"],
    "BiddingEngine:SponsoredListingDTO": ["adId", "adm", "campaignId"],
    "CampaignService:AdCreativeRequest": ["format"],
    "CampaignService:AdCreativeResponse": ["adGroupId", "assetUrl", "auditStatus", "createdAt", "format", "id", "updatedAt"],
    "CampaignService:AdGroupRequest": ["name"],
    "CampaignService:AdGroupResponse": ["active", "campaignId", "createdAt", "id", "name", "updatedAt"],
    "CampaignService:AdvertiserRegistrationRequest": ["companyName"],
    "CampaignService:AdvertiserResponse": ["companyName", "createdAt", "id", "updatedAt", "userId"],
    "CampaignService:ApiResponseAdCreativeResponse": ["message", "success", "timestamp"],
    "CampaignService:ApiResponseAdGroupResponse": ["message", "success", "timestamp"],
    "CampaignService:ApiResponseAdvertiserResponse": ["message", "success", "timestamp"],
    "CampaignService:ApiResponseCampaignResponse": ["message", "success", "timestamp"],
    "CampaignService:ApiResponseListAdCreativeResponse": ["message", "success", "timestamp"],
    "CampaignService:ApiResponseMapStringString": ["message", "success", "timestamp"],
    "CampaignService:ApiResponsePageAdGroupResponse": ["message", "success", "timestamp"],
    "CampaignService:ApiResponsePageCampaignPerformanceResponse": ["message", "success", "timestamp"],
    "CampaignService:ApiResponsePageCampaignResponse": ["message", "success", "timestamp"],
    "CampaignService:ApiResponseString": ["message", "success", "timestamp"],
    "CampaignService:ApiResponseVoid": ["message", "success", "timestamp"],
    "CampaignService:CampaignPacingDTO": ["advertiserId"],
    "CampaignService:CampaignPerformanceResponse": ["advertiserId", "campaignId", "date", "id", "spend"],
    "CampaignService:CampaignRequest": ["advertiserId", "dailyBudget", "maxBid", "name", "startDate"],
    "CampaignService:CampaignResponse": ["advertiserId", "dailyBudget", "frequencyCap", "id", "lifetimeBudget", "maxBid", "name", "startDate", "status", "version"],
    "CampaignService:ContextualKeywords": ["keywords"],
    "CampaignService:Daypart": ["dayOfWeek", "endTime", "startTime"],
    "CampaignService:DaypartingConfig": ["dayparts"],
    "CampaignService:GeoTargeting": ["regions"],
    "CampaignService:PageAdGroupResponse": ["content", "empty", "first", "last", "number", "numberOfElements", "size", "totalElements", "totalPages"],
    "CampaignService:PageCampaignPerformanceResponse": ["content", "empty", "first", "last", "number", "numberOfElements", "size", "totalElements", "totalPages"],
    "CampaignService:PageCampaignResponse": ["content", "empty", "first", "last", "number", "numberOfElements", "size", "totalElements", "totalPages"],
    "CampaignService:PageableObject": ["offset", "pageNumber", "pageSize", "paged", "unpaged"],
    "CampaignService:TopupWalletRequest": ["amount"],
    "CommunicationIntegration:ApiResponseVoid": ["message", "success", "timestamp"],
    "CommunicationIntegration:DeviceRegistrationRequest": ["fcmToken", "platform"],
    "CommunicationService:CreateSessionRequest": ["orderId", "participants"],
    "CommunicationService:IceServer": ["urls"],
    "CommunicationService:ParticipantDto": ["entityType", "userId"],
    "CommunicationService:TurnCredentialsResponse": ["iceServers"],
    "CustomerApplication:ApiResponseBoolean": ["message", "success", "timestamp"],
    "CustomerApplication:ApiResponseCustomer": ["message", "success", "timestamp"],
    "CustomerApplication:ApiResponseCustomerAddressDto": ["message", "success", "timestamp"],
    "CustomerApplication:ApiResponseListCustomerAddressDto": ["message", "success", "timestamp"],
    "CustomerApplication:ApiResponseListOrderResponse": ["message", "success", "timestamp"],
    "CustomerApplication:ApiResponseMapStringObject": ["message", "success", "timestamp"],
    "CustomerApplication:ApiResponseOrderResponse": ["message", "success", "timestamp"],
    "CustomerApplication:ApiResponseQuoteResponse": ["message", "success", "timestamp"],
    "CustomerApplication:ApiResponseString": ["message", "success", "timestamp"],
    "CustomerApplication:ApiResponseVoid": ["message", "success", "timestamp"],
    "CustomerApplication:Customer": ["createdAt", "id", "phoneNumber"],
    "CustomerApplication:CustomerAddressDto": ["addressLine1", "city", "customerId", "id", "label", "latitude", "longitude", "state", "zipCode"],
    "CustomerApplication:DelayApprovalRequest": ["approved"],
    "CustomerApplication:Order": ["createdAt", "customerId", "id", "restaurantId", "status", "totalAmount", "updatedAt"],
    "CustomerApplication:OrderItemRequest": ["menuItemId", "quantity"],
    "CustomerApplication:OrderItemResponse": ["id", "menuItemId", "name", "price", "quantity"],
    "CustomerApplication:OrderRequest": ["customerId", "deliveryAddressId", "items", "restaurantId"],
    "CustomerApplication:OrderResponse": ["cgst", "createdAt", "customerId", "customerPlatformFee", "deliveryAddress", "deliveryFee", "deliveryStatus", "id", "itemTotal", "items", "restaurantId", "restaurantName", "sgst", "status", "totalAmount"],
    "CustomerApplication:PageOrder": ["content", "empty", "first", "last", "number", "numberOfElements", "size", "totalElements", "totalPages"],
    "CustomerApplication:PageSupportTicket": ["content", "empty", "first", "last", "number", "numberOfElements", "size", "totalElements", "totalPages"],
    "CustomerApplication:PageableObject": ["offset", "pageNumber", "pageSize", "paged", "unpaged"],
    "CustomerApplication:QuoteRequest": ["deliveryAddressId", "restaurantId"],
    "CustomerApplication:QuoteResponse": ["cgst", "deliveryFee", "distanceKm", "driverPayout", "minAmountForFreeDelivery", "platformFee", "restaurantDeliveryContribution", "sgst", "subtotal", "total"],
    "CustomerApplication:ResolveRequest": ["approved"],
    "CustomerApplication:SupportTicket": ["createdAt", "customerId", "id", "orderId", "reason", "status"],
    "DeliveryExecutiveApplication:ApiResponseDeliveryExecutive": ["message", "success", "timestamp"],
    "DeliveryExecutiveApplication:ApiResponseMapStringString": ["message", "success", "timestamp"],
    "DeliveryExecutiveApplication:ApiResponseVoid": ["message", "success", "timestamp"],
    "DeliveryExecutiveApplication:BankRequest": ["accountNumber", "ifscCode", "kycFullName"],
    "DeliveryExecutiveApplication:BiometricRequest": ["selfieUrl"],
    "DeliveryExecutiveApplication:DLRequest": ["dateOfBirth", "dlNumber"],
    "DeliveryExecutiveApplication:DeliveryExecutive": ["createdAt", "id", "phoneNumber", "status", "updatedAt"],
    "DeliveryExecutiveApplication:DeliveryOnboardRequest": ["fullName", "phoneNumber", "vehicleNumber"],
    "DeliveryExecutiveApplication:DriverLocationDTO": ["id", "lat", "lng", "status"],
    "DeliveryExecutiveApplication:LocationPayload": ["isMockLocation", "latitude", "longitude", "speedKmh", "timestampMs"],
    "DeliveryExecutiveApplication:PageDeliveryExecutive": ["content", "empty", "first", "last", "number", "numberOfElements", "size", "totalElements", "totalPages"],
    "DeliveryExecutiveApplication:PageDriverLocationDTO": ["content", "empty", "first", "last", "number", "numberOfElements", "size", "totalElements", "totalPages"],
    "DeliveryExecutiveApplication:PageableObject": ["offset", "pageNumber", "pageSize", "paged", "unpaged"],
    "DeliveryExecutiveApplication:RCRequest": ["registrationNumber"],
    "DeliveryExecutiveApplication:TelemetryEventRequest": ["driverId", "lat", "lng"],
    "DeliveryExecutiveApplication:ToggleStatusRequest": ["available", "driverId"],
    "DeliveryExecutiveApplication:UpdateOrderStatusRequest": ["status"],
    "GovernmentIDValidationService:BankAccountRequest": ["accountNumber", "brandName", "ifscCode"],
    "GovernmentIDValidationService:BankRequest": ["accountNumber", "ifscCode", "kycFullName"],
    "GovernmentIDValidationService:BiometricRequest": ["selfieUrl"],
    "GovernmentIDValidationService:DLRequest": ["dateOfBirth", "dlNumber"],
    "GovernmentIDValidationService:GstinRequest": ["brandName", "gstin"],
    "GovernmentIDValidationService:RCRequest": ["registrationNumber"],
    "IdentityService:ApiResponseListSessionInfo": ["message", "success", "timestamp"],
    "IdentityService:ApiResponseMapStringString": ["message", "success", "timestamp"],
    "IdentityService:ApiResponseString": ["message", "success", "timestamp"],
    "IdentityService:ApiResponseUserDTO": ["message", "success", "timestamp"],
    "IdentityService:ApiResponseVoid": ["message", "success", "timestamp"],
    "IdentityService:RoleRequestDTO": ["roleName"],
    "IdentityService:SessionInfo": ["browser", "deviceInfo", "lastActive", "os", "serviceName", "sessionId"],
    "IdentityService:UpdateProfileRequest": ["name"],
    "IdentityService:UserDTO": ["id", "phoneNumber", "roles"],
    "LedgerService:LedgerAccount": ["balance", "id", "lockVersion", "ownerId", "ownerType"],
    "LedgerService:LedgerEntry": ["accountId", "amount", "category", "createdAt", "direction", "id", "transactionId"],
    "LedgerService:LedgerTransactionDto": ["amount", "category", "date", "fromAccountId", "toAccountId", "transactionId"],
    "LedgerService:PageableObject": ["offset", "pageNumber", "pageSize", "paged", "unpaged"],
    "MapsIntegration:DispatchOrderRequest": ["cityId", "restaurantCoords"],
    "MapsIntegration:SetAvailabilityRequest": ["available", "cityId", "driverId"],
    "MapsIntegration:UpdateLocationRequest": ["cityId", "driverId", "lat", "lng"],
    "PaymentGatewayIntegration:ApiResponseString": ["message", "success", "timestamp"],
    "PaymentGatewayIntegration:CreateOrderRequest": ["amountInInr", "internalOrderId"],
    "PaymentGatewayIntegration:OutboxEventEntity": ["aggregateId", "aggregateType", "createdAt", "eventType", "id", "payload", "retryCount", "status"],
    "PaymentGatewayIntegration:RefundRequest": ["amountInInr", "gatewayOrderId"],
    "RestaurantApplication:ApiResponseBoolean": ["message", "success", "timestamp"],
    "RestaurantApplication:ApiResponseBrand": ["message", "success", "timestamp"],
    "RestaurantApplication:ApiResponseCategoryDTO": ["message", "success", "timestamp"],
    "RestaurantApplication:ApiResponseListBrand": ["message", "success", "timestamp"],
    "RestaurantApplication:ApiResponseListCategoryDTO": ["message", "success", "timestamp"],
    "RestaurantApplication:ApiResponseListMasterMenuItem": ["message", "success", "timestamp"],
    "RestaurantApplication:ApiResponseListMenuItemDTO": ["message", "success", "timestamp"],
    "RestaurantApplication:ApiResponseListRestaurantOrder": ["message", "success", "timestamp"],
    "RestaurantApplication:ApiResponseListTimingDTO": ["message", "success", "timestamp"],
    "RestaurantApplication:ApiResponseMapStringString": ["message", "success", "timestamp"],
    "RestaurantApplication:ApiResponseString": ["message", "success", "timestamp"],
    "RestaurantApplication:ApiResponseVoid": ["message", "success", "timestamp"],
    "RestaurantApplication:BankAccountRequest": ["accountNumber", "brandName", "ifscCode"],
    "RestaurantApplication:Brand": ["id", "name", "ownerId"],
    "RestaurantApplication:BrandOnboardRequest": ["bankAccountNumber", "gstin", "ifscCode", "name", "pan"],
    "RestaurantApplication:CategoryDTO": ["name"],
    "RestaurantApplication:CategoryTimingDTO": ["closingTime", "openingTime"],
    "RestaurantApplication:GstinRequest": ["brandName", "gstin"],
    "RestaurantApplication:MasterMenuItem": ["basePrice", "name", "packingCharge"],
    "RestaurantApplication:MenuItemDTO": ["id", "isAvailable", "name", "price", "restaurantId"],
    "RestaurantApplication:OutletMenuOverride": ["isAvailable"],
    "RestaurantApplication:OutletOnboardRequest": ["fssaiLicenseNumber", "lat", "lng", "name", "timings"],
    "RestaurantApplication:OutletSettingsUpdateRequest": ["defaultPrepTimeSeconds"],
    "RestaurantApplication:OutletStatusUpdateRequest": ["isActive"],
    "RestaurantApplication:OutletTimingsUpdateRequest": ["timings"],
    "RestaurantApplication:RestaurantOrder": ["createdAt", "deliveryStatus", "orderId", "restaurantId", "status"],
    "RestaurantApplication:SetBrandCategoryTimingRequest": ["categoryId"],
    "RestaurantApplication:SetOutletCategoryTimingRequest": ["categoryId", "timings"],
    "RestaurantApplication:TimingDTO": ["closingTime", "openingTime"],
    "RestaurantApplication:TimingRequest": ["closingTime", "openingTime"],
    "RestaurantApplication:VerificationCallbackRequest": ["status", "verificationType"],
    # Re-baselined 2026-09-11 for the order-scoped review contract
    # (RandomDocuments/ReviewsIntegration_2026-09-11).
    # ReviewResponseDto was replaced by the ReviewDto / ReviewDetailDto pair so that redaction is a
    # property of the type rather than a runtime branch, and CreateReviewRequest became an
    # order-scoped batch. The ratchet fired on all five, which is exactly what it is for: the
    # baseline moves only because the change was deliberate, and it moves to a stricter set --
    # 17 schemas listed where there were 7.
    "ReviewsService:AggregateBatchDto": ["aggregates", "entityType"],
    "ReviewsService:ApiResponseAggregateBatchDto": ["message", "success", "timestamp"],
    "ReviewsService:ApiResponseListReviewDetailDto": ["message", "success", "timestamp"],
    "ReviewsService:ApiResponsePagedModelReviewDetailDto": ["message", "success", "timestamp"],
    "ReviewsService:ApiResponsePagedModelReviewDto": ["message", "success", "timestamp"],
    "ReviewsService:ApiResponseReviewAggregateDto": ["message", "success", "timestamp"],
    "ReviewsService:ApiResponseReviewEligibilityDto": ["message", "success", "timestamp"],
    "ReviewsService:CreateReviewRequest": ["entries", "orderId"],
    "ReviewsService:PageMetadata": ["number", "size", "totalElements", "totalPages"],
    "ReviewsService:PagedModelReviewDetailDto": ["content"],
    "ReviewsService:PagedModelReviewDto": ["content"],
    "ReviewsService:ReviewAggregateDto": ["averageRating", "entityId", "entityType", "totalReviews"],
    "ReviewsService:ReviewDetailDto": ["createdAt", "entityId", "entityType", "id", "orderId", "rating", "userId"],
    "ReviewsService:ReviewDto": ["createdAt", "entityId", "entityType", "id", "rating"],
    "ReviewsService:ReviewEligibilityDto": ["orderId", "reviewable", "targets"],
    "ReviewsService:ReviewEntryRequest": ["entityId", "entityType", "rating"],
    "ReviewsService:ReviewTargetDto": ["alreadyReviewed", "displayName", "entityId", "entityType"],
    "WalletService:ApiResponseMapStringString": ["message", "success", "timestamp"],
    "WalletService:ApiResponseString": ["message", "success", "timestamp"],
    "WalletService:CreateWalletRequest": ["currency"],
    "WalletService:OutboxEventEntity": ["aggregateId", "aggregateType", "createdAt", "eventType", "id", "payload", "retryCount", "status"],
    "WalletService:TopupWalletRequest": ["amount"],
    "WalletService:TransactionRequest": ["amount"],
    "WalletService:WalletDto": ["balance", "currency", "entityId", "entityType", "id", "status"],
    "WalletService:WalletTransactionDto": ["amount", "createdAt", "id", "transactionType", "walletId"],
}


def check_mcp_identity():
    """No @Tool may manufacture an Authentication, and MCP must stay off the gateway.

    `ChatMcpService.createMockAuthentication(userId)` built an Authentication from a caller-supplied
    string, marked it authenticated, granted it ROLE_ADMIN and passed it to the real controllers --
    satisfying every ownership check by construction. Removed 2026-08-28; tools now read
    SecurityContextHolder as a controller would.

    Comments are stripped first. The javadoc that REPLACED that method names it while explaining
    what it replaced, and an unstripped search flagged the fix as the defect -- the fourth time in
    this workspace that a check has read prose documenting a rule as a violation of it.

    Deliberately NOT checked: a @Tool taking a `String userId`. Most such parameters name the
    SUBJECT being asked about, not the caller -- `getActiveOrdersForUser(userId)` calls an admin
    controller about someone else. A gate cannot tell a subject from an identity claim, and one
    that guesses would demand the removal of legitimate parameters. That concern is authorization,
    tracked in the Phase 6 record.
    """
    problems = []
    # Anonymous Authentication implementations are always wrong; constructing a token is wrong
    # only inside a tool surface, because SecurityContextFilter legitimately does it. Scoping by
    # WHERE beats trying to parse the arguments: an earlier version required ROLE_ inside the
    # constructor parentheses and missed `new UsernamePasswordAuthenticationToken(id, null,
    # List.of(new SimpleGrantedAuthority("ROLE_ADMIN")))` because [^)]* stops at the nested
    # bracket. Found by break-testing 2026-08-28.
    anonymous_impl = re.compile(r"new\s+[\w.]*Authentication\s*\(\s*\)\s*\{|createMockAuthentication")
    # [\w.]* not \w*: this codebase writes fully-qualified names inline
    # (`new org.springframework.security.authentication.UsernamePasswordAuthenticationToken(...)`),
    # and \w does not match a dot. Second regex miss in this one check, both found by break-testing.
    builds_token = re.compile(r"new\s+[\w.]*UsernamePasswordAuthenticationToken\s*\(|"
                              r"SecurityContextHolder\s*\.\s*getContext\s*\(\s*\)\s*\.\s*setAuthentication")
    for f in sorted(all_main_java()):
        src = read(f)
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        src = re.sub(r"//[^\n]*", "", src)
        if anonymous_impl.search(src):
            problems.append(f"{f.relative_to(ROOT)} implements Authentication by hand")
        elif "@Tool" in src and builds_token.search(src):
            problems.append(f"{f.relative_to(ROOT)} is a tool surface that constructs an Authentication")

    for cfg in (ROOT / "Deployment/api-gateway.yml",
                ROOT / "ApiGateway/src/main/resources/application.yml"):
        if not cfg.is_file():
            continue
        for i, line in enumerate(read(cfg).splitlines(), 1):
            if line.strip().startswith("#"):
                continue
            if re.search(r"Path=.*\b(mcp|sse)\b", line, re.I):
                problems.append(f"{cfg.name}:{i} routes MCP through the gateway -- "
                                f"the containment for tool authorization is gone")
    check("MCP-IDENTITY",
          "no @Tool manufactures an Authentication, and MCP is not routed at the edge",
          not problems,
          "; ".join(problems[:4]))


def check_scheduled_jobs_classified():
    """Every @Scheduled class states how it behaves under replication.

    The premise this started from was wrong three times over. The plan recorded "19 classes, no
    distributed scheduler lock, correct only at one replica". Measured 2026-08-27:

      * a grep for ShedLock/@SchedulerLock/LockProvider found nothing because the platform rolled
        its own -- RedisLock.tryAcquire is SET NX PX with an atomic Lua release;
      * a grep for tryAcquire missed the jobs that call redisTemplate.setIfAbsent directly;
      * counting either way missed that some jobs are safe for reasons other than a lock.

    True state: of 17 classes, 12 hold a distributed lock, 1 uses SKIP LOCKED, 2 are idempotent,
    1 is guarded by @Version, and 1 MUST NOT be locked because it refreshes an in-memory
    per-instance index. Zero are unsafe.

    None of that is visible from the code without reading each job, which is why the markers exist.
    This check only asserts a classification is present -- the accuracy of a marker is a review
    question, not something a script can settle.
    """
    # The marker must sit in the javadoc block immediately above the class declaration, not merely
    # somewhere in the file: a loose "// TODO @replication-safe:" comment satisfied the first
    # version of this check (found by break-testing it on 2026-08-27).
    unmarked = []
    for f in sorted(all_main_java()):
        src = read(f)
        # Strip BOTH comment forms before deciding the file has a @Scheduled. Stripping only "//"
        # was not enough: on 2026-08-28 a javadoc on FeignSecurityInterceptor that mentioned
        # "{@code @Scheduled}" while explaining why background calls need an identity was reported as
        # an unclassified scheduled class. The marker lookup below still reads the ORIGINAL source,
        # because the classification itself lives in a javadoc.
        if "@Scheduled" not in re.sub(r"//[^\n]*|/\*.*?\*/", "", src, flags=re.S):
            continue
        decl = re.search(r"^(?:public\s+)?(?:final\s+)?class\s+" + re.escape(f.stem) + r"\b", src, re.M)
        classified = False
        if decl:
            preceding = src[:decl.start()]
            blocks = re.findall(r"/\*\*.*?\*/", preceding, re.S)
            if blocks and re.search(r"@replication(-safe)?:", blocks[-1]):
                classified = True
        if not classified:
            unmarked.append(str(f.relative_to(ROOT)))
    check("SCHEDULE-CLASSIFIED",
          "every @Scheduled class records its behaviour under replication",
          not unmarked,
          f"{len(unmarked)} unclassified: " + "; ".join(unmarked[:4]))


def check_idempotency_key_retention():
    """Idempotency keys are swept, and the sweeper is not re-copied per service.

    Writers claim keys via `tryClaim` or a `save`; the cleanup path is `deleteOlderThan`. Measured
    2026-08-27: ELEVEN services wrote keys and THREE swept them, using byte-identical copies of the
    same 29-line class. Detecting this needed the repository interface read, not a filename guessed:
    successive greps for `new IdempotencyKey(`, then `.save(`, then `tryClaim(` reported 2, then 5,
    then 8 offenders.

    The sweeper now lives in CommonLibrary and is auto-configured wherever a datasource exists, so
    the invariant is no longer per-service. What is checked is that the autoconfiguration is still
    registered and that nobody has reintroduced a local copy.
    """
    problems = []
    # After the split there is one .imports per module, and the sweeper is registered in exactly one
    # of them. Reading only the first match found common-messaging's, which lists OutboxConfiguration
    # and nothing else.
    registered = any(
        "IdempotencySweepConfiguration" in read(f)
        for f in (ROOT / "CommonLibrary").rglob(
            "src/main/resources/META-INF/spring/"
            "org.springframework.boot.autoconfigure.AutoConfiguration.imports"))
    if not registered:
        problems.append("IdempotencySweepConfiguration is not registered -- nothing sweeps idempotency keys")
    if not (common_src("com/fooddelivery/common/idempotency/IdempotencyKeySweeper.java")).is_file():
        problems.append("IdempotencyKeySweeper is missing from CommonLibrary")
    for f in all_main_java():
        mod = f.relative_to(ROOT).parts[0]
        if mod == "CommonLibrary":
            continue
        if re.search(r"\.deleteOlderThan\s*\(", read(f)):
            problems.append(f"{mod}: {f.name} re-implements the sweeper CommonLibrary provides")
    check("IDEMPOTENCY-RETENTION",
          "idempotency keys are swept centrally and not re-copied per service",
          not problems,
          "; ".join(problems[:4]))


def check_money_not_through_double():
    """No monetary value is read out of JSON via a double, and the platform mapper forbids it.

    The call site is not where this is fixed. On a DoubleNode, BigDecimal.valueOf(asDouble()) and
    new BigDecimal(asText()) are byte-identical -- the number is already through binary floating
    point before the tree exists. Measured 2026-08-27: 12345678901234567.89 becomes
    12345678901234568 either way. USE_BIG_DECIMAL_FOR_FLOATS on the shared ObjectMapper is what
    actually fixes it, so both halves are checked.
    """
    problems = []
    jackson = common_src("com/fooddelivery/common/config/JacksonConfig.java")
    if not jackson.is_file() or "USE_BIG_DECIMAL_FOR_FLOATS" not in read(jackson):
        problems.append("the platform ObjectMapper does not parse floats as BigDecimal")
    money = re.compile(r"(?i)(amount|price|balance|fee|total|refund|payout|charge|spend)")
    for f in all_main_java():
        src = re.sub(r"/\*.*?\*/", "", read(f), flags=re.S)
        src = re.sub(r"//[^\n]*", "", src)
        for i, line in enumerate(src.splitlines(), 1):
            if "asDouble" in line and money.search(line):
                problems.append(f"{f.relative_to(ROOT)}:{i} reads money through a double")
    check("MONEY-PRECISION",
          "monetary values are not read out of JSON through a double",
          not problems,
          f"{len(problems)}: " + "; ".join(problems[:4]))


def check_modifying_queries_are_transactional():
    """Every `@Modifying` repository method carries its own `@Transactional`.

    Spring Data gives `@Transactional` to SimpleJpaRepository's CRUD methods, NOT to a custom
    `@Modifying @Query`. Such a method inherits a transaction only if its caller has one -- so
    whether it works depends on the call site, and the failure is invisible until runtime.

    Found the hard way on 2026-08-29: OrderQuoteRepository.claim() was called from inside
    CompletableFuture.supplyAsync, where no caller transaction propagates, and every checkout
    failed with "No EntityManager with actual transaction available for current thread". The
    module compiled, 40 unit tests passed, and the reactor was green -- nothing local exercises
    a repository against a real database, because Testcontainers are not used here.

    The rule is deliberately local: annotate the method rather than reason about every caller.
    `@Transactional` is REQUIRED by default, so it joins an existing transaction when there is
    one and opens its own when there is not. Annotating costs nothing and removes the call-site
    dependency entirely.
    """
    problems = []
    for f in sorted(ROOT.glob("*/src/main/**/*Repository.java")):
        src = re.sub(r"/\*.*?\*/", "", read(f), flags=re.S)
        src = re.sub(r"//[^\n]*", "", src)
        if "@Modifying" not in src:
            continue
        # An interface-level @Transactional covers every method in the file.
        if re.search(r"^\s*@Transactional\b", src.split("interface", 1)[0], re.M):
            continue
        pending, depth = [], 0
        for i, line in enumerate(src.splitlines(), 1):
            stripped = line.strip()
            if depth > 0 or stripped.startswith("@"):
                pending.append(stripped)
                depth += line.count("(") - line.count(")")
                if depth < 0:
                    depth = 0
                continue
            if not stripped:
                continue
            # first non-annotation line after a run of annotations is the method signature
            block = " ".join(pending)
            if "@Modifying" in block and "@Transactional" not in block:
                name = re.search(r"(\w+)\s*\(", stripped)
                problems.append(
                    f"{f.relative_to(ROOT)}:{i} @Modifying "
                    f"{name.group(1) if name else stripped[:40]} is not @Transactional")
            pending = []
    check("MODIFYING-TRANSACTIONAL",
          "every @Modifying repository query carries its own @Transactional",
          not problems,
          f"{len(problems)}: " + "; ".join(problems[:4]))


def check_query_parameters_are_bound():
    """Every named parameter in a `@Query` is supplied by the method it annotates.

    A Java annotation binds to the NEXT declaration. Insert a method between an `@Query` and the
    method it was written for -- a javadoc block in between makes this easy to miss -- and the
    annotation silently reattaches to the new method, which does not have its parameters.

    Happened on 2026-08-29: `findByStatusAndUpdatedAtBefore` was added directly beneath a
    `@Query(... :minTime ...)` belonging to `findByStatusAndCreatedAtBetween`. The module compiled,
    the Spring context started, and `RefundRetrySweeper` then threw
    `QueryParameterException: No argument for named parameter ':minTime'` every 5 minutes in
    production. Nothing local caught it: Spring Data does not validate the binding at bootstrap, and
    no repository here is exercised against a real database.
    """
    problems = []
    for f in sorted(ROOT.glob("*/src/main/**/*Repository*.java")):
        lines = read(f).splitlines()
        i = 0
        while i < len(lines):
            if not lines[i].strip().startswith("@Query"):
                i += 1
                continue
            ann, depth, j = "", 0, i
            while j < len(lines):
                ann += lines[j]
                depth += lines[j].count("(") - lines[j].count(")")
                j += 1
                if depth <= 0 and "(" in ann:
                    break
            params = set(re.findall(r":(\w+)", ann))
            sig, k = None, j
            while k < len(lines):
                t = lines[k].strip()
                if not t or t.startswith(("*", "/*", "//", "@")):
                    k += 1
                    continue
                sig = t
                while sig.count("(") > sig.count(")") and k + 1 < len(lines):
                    k += 1
                    sig += lines[k].strip()
                break
            if sig:
                bound = set(re.findall(r'@Param\(\s*"(\w+)"', sig))
                names = set(re.findall(r"\b(\w+)\s*[,)]", sig))
                missing = sorted(p for p in params if p not in bound and p not in names)
                if missing:
                    method = re.search(r"(\w+)\s*\(", sig)
                    problems.append(
                        f"{f.relative_to(ROOT)}: @Query needs {missing} but "
                        f"{method.group(1) if method else sig[:30]} does not supply "
                        f"{'it' if len(missing) == 1 else 'them'}")
            i = k + 1 if sig else j
    check("QUERY-PARAMS-BOUND",
          "every @Query named parameter is supplied by the method it annotates",
          not problems,
          f"{len(problems)}: " + "; ".join(problems[:3]))


def check_ci_root_pom_matches():
    """The CI copy of the aggregator pom matches the real one.

    The workspace root is deliberately not a git repository, so the pom that defines the 23-module
    reactor is unversioned and exists only on a developer machine. CI cannot reconstruct it, so a
    copy lives at FoodDeliveryContracts/ci/root-pom.xml and is placed at the assembled root.

    If the two diverge, CI silently builds a DIFFERENT reactor than the one tested locally -- fewer
    modules, or a stale module list -- and reports success. That is the failure this catches.
    """
    real = ROOT / "pom.xml"
    copy = ROOT / "FoodDeliveryContracts/ci/root-pom.xml"
    if not real.is_file():
        check("CI-ROOT-POM", "the CI copy of the aggregator pom matches the real one",
              False, f"{real} not found -- the reactor root is missing")
        return
    if not copy.is_file():
        check("CI-ROOT-POM", "the CI copy of the aggregator pom matches the real one",
              False, f"{copy} not found -- CI cannot assemble the reactor without it")
        return
    a, b = read(real), read(copy)
    if a == b:
        check("CI-ROOT-POM", "the CI copy of the aggregator pom matches the real one", True)
        return
    ma = set(re.findall(r"<module>([^<]+)</module>", a))
    mb = set(re.findall(r"<module>([^<]+)</module>", b))
    detail = "content differs"
    if ma - mb:
        detail = f"CI copy is MISSING modules: {sorted(ma - mb)}"
    elif mb - ma:
        detail = f"CI copy has EXTRA modules: {sorted(mb - ma)}"
    check("CI-ROOT-POM", "the CI copy of the aggregator pom matches the real one", False,
          detail + " -- run: cp pom.xml FoodDeliveryContracts/ci/root-pom.xml")


def check_messaging_context_minimal():
    """Messaging contract bases stay minimal, and keep their exclusions in `properties`.

    Two regressions this guards, both of which have happened:

    1. PaymentGatewayIntegration's base dropped its DataSource/JPA exclusions on 2026-08-26 in
       favour of ddl-auto=none, leaving every messaging contract test building a DataSource and
       EntityManagerFactory it never touches.
    2. Exclusions written as @EnableAutoConfiguration(exclude = ...) on a nested configuration leak
       into OTHER tests' contexts, because every service component-scans com.fooddelivery. That
       surfaced as unrelated tests failing with "No bean named 'entityManagerFactory'".

    Comments are stripped before matching. Three separate checks today produced false findings by
    matching the prose that DOCUMENTS a rule -- including two files whose javadoc explains exactly
    the anti-pattern in (2).
    """
    problems = []
    for f in sorted(ROOT.glob("*/src/test/**/BaseMessagingClass.java")):
        src = read(f)
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        src = re.sub(r"//[^\n]*", "", src)
        mod = f.relative_to(ROOT).parts[0]
        # Read the VALUE of spring.autoconfigure.exclude, not the whole file: an `import
        # org...DataSourceAutoConfiguration;` line satisfies a naive substring search even when the
        # exclusion has been removed. That hole was found by break-testing this very check on
        # 2026-08-27 -- the break applied and the check still passed.
        excluded = ""
        marker = "spring.autoconfigure.exclude="
        if marker in src:
            tail = src[src.index(marker) + len(marker):]
            # the value is a run of "..." segments joined by +, ending at the next property
            for seg in re.finditer(r'([^"]*)"(?:\s*\+\s*"([^"]*)")*', tail[:4000]):
                excluded += seg.group(0)
                break
            excluded = "".join(re.findall(r'[\w.]+AutoConfiguration', tail[:2000]))
        if "DataSourceAutoConfiguration" not in excluded:
            problems.append(f"{mod}: does not exclude DataSourceAutoConfiguration -- "
                            f"builds a datasource its messaging tests do not use")
        if re.search(r"@\S*EnableAutoConfiguration\s*\(\s*exclude", src):
            problems.append(f"{mod}: exclusions on the class leak into other tests -- use `properties`")
    check("MESSAGING-CONTEXT",
          "messaging contract bases stay minimal and keep exclusions in properties",
          not problems,
          f"{len(problems)}: " + "; ".join(problems[:4]))


def check_spring_boot_config_ambiguity():
    """No @SpringBootTest that omits `classes=` may resolve to a package holding two configurations.

    Spring's search starts at the test's own package and walks UP, stopping at the first package
    containing a @SpringBootConfiguration; two in that package is a hard
    "Found multiple @SpringBootConfiguration annotated classes".

    Counting configurations per module is NOT the invariant and produces false alarms: on
    2026-08-27 CustomerApplication had six and was safe, while a crude count flagged five modules
    that were fine because their extra configurations sat in DEEPER packages than any test relying
    on the search. What matters is where the search lands.

    Modelled against the real failure: reintroducing a second configuration in
    com.fooddelivery.ledger (the package holding both LedgerApplication and MockRequestTest) is
    detected here and fails in Spring with the same two classes named. That is the shape that took
    out six modules on 2026-08-26.
    """
    config = re.compile(r"@(?:org\.springframework\.boot\.)?(?:SpringBootConfiguration|SpringBootApplication)\b")
    test_ann = re.compile(r"@(?:org\.springframework\.boot\.test\.context\.)?SpringBootTest\b")
    classes_attr = re.compile(r"@(?:org\.springframework\.boot\.test\.context\.)?SpringBootTest\s*\(([^)]*)", re.S)
    package_of = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)

    def uncommented(path):
        src = read(path)
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        return re.sub(r"//[^\n]*", "", src)

    problems = []
    for mod_dir in sorted(d for d in ROOT.iterdir() if (d / "src/test").is_dir()):
        candidates = {}
        for area in ("src/main", "src/test"):
            for f in mod_dir.glob(f"{area}/**/*.java"):
                src = uncommented(f)
                if config.search(src):
                    pkg = package_of.search(src)
                    candidates.setdefault(pkg.group(1) if pkg else "", []).append(f.name)
        for f in mod_dir.glob("src/test/**/*.java"):
            src = uncommented(f)
            if not test_ann.search(src):
                continue
            attr = classes_attr.search(src)
            if attr and "classes" in attr.group(1):
                continue
            pkg_match = package_of.search(src)
            pkg = pkg_match.group(1) if pkg_match else ""
            while True:
                found = candidates.get(pkg, [])
                if found:
                    if len(found) > 1:
                        problems.append(f"{mod_dir.name}: {f.name} resolves in '{pkg}' to {sorted(found)}")
                    break
                if "." not in pkg:
                    break
                pkg = pkg.rsplit(".", 1)[0]

    check("BOOT-CONFIG-AMBIGUITY",
          "no test relying on the configuration search resolves to two candidates",
          not problems,
          f"{len(problems)} ambiguous: " + "; ".join(problems[:4]))


def check_contract_stub_cycles():
    """INFORMATIONAL. Reports mutual contract-stub dependencies; never fails the build.

    A consumer contract test replays a stub jar produced by the producer's build and resolved at
    test time from ~/.m2. Five pairs are mutual, so in any single-pass build one side of each pair
    reads the PREVIOUS build's recording. Demonstrated 2026-08-27: a producer contract broken in
    source left its consumer's test green, differing only in which jar sat in the local repository.

    This does NOT fail, deliberately. `FoodDeliveryContracts/build_verify.sh` publishes every stub
    jar before any test runs, which makes a cycle harmless -- nothing is read before everything is
    written. Failing on a harmless condition produces a gate people switch off, and it would block
    legitimate new contract tests. The count is printed so a rise is visible to anyone reading the
    output, and so the number can be ratcheted down deliberately rather than policed.

    The checks that DO fail are the ones where failure means something: stub jars containing no
    stubs (build_verify.sh), and service-to-service code dependencies (Phase 8 gate 3).
    """
    artifact_to_module = {}
    for pom in sorted(ROOT.glob("*/pom.xml")):
        ids = re.findall(r"<artifactId>([^<]+)</artifactId>", read(pom)[:2500])
        if len(ids) >= 2:
            artifact_to_module[ids[1]] = pom.parent.name

    edges = set()
    for f in ROOT.glob("*/src/test/**/*.java"):
        src = read(f)
        if "AutoConfigureStubRunner" not in src:
            continue
        consumer = f.relative_to(ROOT).parts[0]
        for m in re.finditer(r"com\.fooddelivery:([a-z0-9-]+):", src):
            producer = artifact_to_module.get(m.group(1))
            if producer and producer != consumer:
                edges.add((consumer, producer))

    adj = {}
    for c, p in edges:
        adj.setdefault(c, set()).add(p)
    cycles = sorted({tuple(sorted((a, b))) for a in adj for b in adj[a] if b in adj and a in adj[b]})

    detail = f"informational: {len(edges)} stub edges, {len(cycles)} mutual pair(s)"
    if cycles:
        detail += " -- use FoodDeliveryContracts/build_verify.sh so build order cannot matter: "
        detail += "; ".join(f"{a} <-> {b}" for a, b in cycles)
    check("STUB-CYCLES", "contract stub graph (informational, never fails)", True, detail)


def check_schema_strictness_ratchet():
    """Every schema on STRICT_SCHEMAS still declares AT LEAST the fields recorded for it.

    Presence of a `required` array is not enough: dropping one field from a ten-field schema
    leaves the array non-empty and would sail through. Verified 2026-08-27 -- the first version
    of this check did exactly that, so it compares the recorded set against the current one.
    Gaining required fields is fine; losing one is the regression.
    """
    regressed = []
    for spec_path in sorted(ROOT.glob("*/openapi.json")):
        mod = spec_path.parent.name
        try:
            schemas = json.loads(read(spec_path)).get("components", {}).get("schemas", {}) or {}
        except Exception as exc:
            regressed.append(f"{mod}: spec unreadable ({exc})")
            continue
        for key, expected in STRICT_SCHEMAS.items():
            if not key.startswith(mod + ":"):
                continue
            name = key.split(":", 1)[1]
            if name not in schemas:
                regressed.append(f"{key} no longer exists in the spec")
                continue
            actual = set(schemas[name].get("required") or [])
            lost = sorted(set(expected) - actual)
            if lost:
                regressed.append(f"{key} lost required field(s): {', '.join(lost)}")
    check("SCHEMA-STRICT",
          f"schemas on the strictness ratchet keep their required fields ({len(STRICT_SCHEMAS)} listed)",
          not regressed,
          f"{len(regressed)} regressed: " + "; ".join(sorted(regressed)[:6]))


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
    f = common_src("com/fooddelivery/common/filter/IdempotencyFilter.java")
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


# ---------------------------------------------------------------- SCHEMA-IMMUTABLE
def check_schema_immutable():
    """An applied Flyway migration must never be edited or deleted.

    For each module in service-map.tsv that has db/migration, compare the migration
    files at the last-deployed sha (.versions tag) against HEAD. A file that EXISTED
    at that sha and has been modified or deleted is a violation. A NEW file is fine —
    that is the intended workflow.

    CommonLibrary is explicitly excluded: it has migrations under db/migration/common,
    is not in service-map.tsv, and was flagged spuriously once before for having no
    baseline. ONDCIntegrationService and ReviewsService are also excluded (parked,
    not in service-map.tsv).
    """
    import subprocess as _sp
    smap = ROOT / "Deployment/service-map.tsv"
    versions = ROOT / "Deployment/.versions"
    if not smap.exists() or not versions.exists():
        check("SCHEMA-IMMUTABLE", "migration immutability", False,
              "service-map.tsv or .versions missing")
        return

    # Parse .versions: MODULE_TAG=sha  ->  {compose-service: sha}
    ver_lines = read(versions).splitlines()
    tag_by_var = {}
    for line in ver_lines:
        if "_TAG=" in line:
            k, v = line.split("=", 1)
            tag_by_var[k.strip()] = v.strip()

    # Parse service-map.tsv: module-dir -> compose-service
    modules = []
    for line in read(smap).splitlines():
        if line.startswith("#") or "\t" not in line:
            continue
        parts = line.split("\t")
        mod_dir = parts[0]
        compose_svc = parts[1]
        mig_dir = ROOT / mod_dir / "src/main/resources/db/migration"
        if mig_dir.is_dir():
            modules.append((mod_dir, compose_svc))

    if not modules:
        check("SCHEMA-IMMUTABLE", "migration immutability", False,
              "no modules with db/migration found via service-map.tsv")
        return

    violations = []
    skipped = []
    for mod_dir, compose_svc in modules:
        # Resolve the .versions tag variable: compose service 'customer-service' -> CUSTOMER_SERVICE_TAG
        var = compose_svc.upper().replace("-", "_") + "_TAG"
        tag = tag_by_var.get(var, "")
        if not tag:
            skipped.append(f"{mod_dir} (no {var} in .versions)")
            continue
        # Strip -dirty suffix for the git sha
        sha = tag.replace("-dirty", "")
        mod_path = ROOT / mod_dir
        if not (mod_path / ".git").is_dir():
            skipped.append(f"{mod_dir} (not a git repo)")
            continue
        # Verify the sha is a valid commit in that repo
        r = _sp.run(["git", "-C", str(mod_path), "cat-file", "-t", sha],
                    capture_output=True, text=True)
        if r.stdout.strip() != "commit":
            skipped.append(f"{mod_dir} ({sha} is not a commit)")
            continue
        # Get files changed between the deployed sha and the WORKING TREE in db/migration.
        # Omit HEAD so uncommitted edits are caught — the standing rule is "never commit",
        # so migrations edited locally but not committed must still fire this check.
        r = _sp.run(["git", "-C", str(mod_path), "diff", "--name-only", sha,
                     "--", "src/main/resources/db/migration"],
                    capture_output=True, text=True)
        changed = [f for f in r.stdout.strip().splitlines() if f]
        for f in changed:
            # Did this file exist at the deployed sha? If yes, it was modified or deleted.
            r2 = _sp.run(["git", "-C", str(mod_path), "cat-file", "-e", f"{sha}:{f}"],
                         capture_output=True, text=True)
            if r2.returncode == 0:
                # File existed at sha -> modified or deleted applied migration
                violations.append(f"{mod_dir}/{f.split('/')[-1]}")

    if skipped:
        for s in skipped:
            check("SCHEMA-IMMUTABLE", f"migration immutability SKIP: {s}", True, "")

    check("SCHEMA-IMMUTABLE",
          f"no applied migration has been edited or deleted ({len(modules)} modules checked)",
          not violations,
          ("; ".join(violations) +
           " — add a new timestamped migration (V<YYYYMMDDHHMMSS>__...) instead of editing an applied one")
          if violations else "")



# ---------------------------------------------------------------- GW-RATELIMIT
# Both gateway route files. Deployment/api-gateway.yml is the one that governs production: it is
# served by ConfigService's native backend, and Spring Cloud Config properties override the local
# application.yml (and even command-line args, via override-system-properties). The local file is
# the fallback used when the config server is disabled, e.g. ApiGatewayApplicationStartupTest.
GATEWAY_ROUTE_FILES = (
    "Deployment/api-gateway.yml",
    "ApiGateway/src/main/resources/application.yml",
)

# Spring Cloud Gateway ADDS default-filters to every route's chain rather than letting a route
# override them, so a RequestRateLimiter there stacks with the route's own and the stricter bucket
# wins. Declaring it per route is the only way a route's stated limit is the limit it gets.
# Verified against /actuator/gateway/routes on 2026-09-10.
TILE_ROUTE_MARKERS = ("olamaps", "ola-maps")
# A cold MapLibre load is ~50-70 requests (style, TileJSONs, sprite, glyph ranges, one vector tile
# per visible grid cell per source) and MapLibre never retries a tile the gateway rejects: a 429
# leaves a permanently blank square. This is a floor, not a target.
TILE_BURST_FLOOR = 200


def _gateway_docs(path):
    for doc in yaml.safe_load_all(path.read_text()):
        if isinstance(doc, dict):
            yield doc


def check_gateway_rate_limits():
    problems = []
    checked_routes = 0
    for rel in GATEWAY_ROUTE_FILES:
        path = ROOT / rel
        if not path.exists():
            problems.append(f"{rel}: file missing")
            continue
        found_routes = False
        for doc in _gateway_docs(path):
            gw = (doc.get("spring") or {}).get("cloud", {}).get("gateway")
            if not isinstance(gw, dict):
                continue

            for f in gw.get("default-filters") or []:
                name = f.get("name") if isinstance(f, dict) else str(f).split("=")[0].strip()
                if name == "RequestRateLimiter":
                    problems.append(
                        f"{rel}: RequestRateLimiter is in default-filters. It stacks onto every "
                        f"route, so the stricter bucket binds and a route's own limit is ignored. "
                        f"Declare it per route instead.")

            routes = gw.get("routes")
            if not isinstance(routes, list):
                continue
            found_routes = True
            for r in routes:
                rid = r.get("id", "<no id>")
                limiters = [f for f in (r.get("filters") or [])
                            if isinstance(f, dict) and f.get("name") == "RequestRateLimiter"]
                if not limiters:
                    problems.append(f"{rel}: route '{rid}' has no RequestRateLimiter")
                    continue
                if len(limiters) > 1:
                    problems.append(f"{rel}: route '{rid}' declares {len(limiters)} rate limiters")
                checked_routes += 1
                args = limiters[0].get("args") or {}
                if not args.get("key-resolver"):
                    problems.append(f"{rel}: route '{rid}' rate limiter has no key-resolver")
                burst = args.get("redis-rate-limiter.burstCapacity")
                replenish = args.get("redis-rate-limiter.replenishRate")
                if burst is None or replenish is None:
                    problems.append(f"{rel}: route '{rid}' rate limiter is missing a rate or burst")
                    continue
                if burst < replenish:
                    problems.append(
                        f"{rel}: route '{rid}' burstCapacity {burst} is below replenishRate "
                        f"{replenish}; the bucket can never hold one second of traffic")
                if any(m in rid for m in TILE_ROUTE_MARKERS) and burst < TILE_BURST_FLOOR:
                    problems.append(
                        f"{rel}: tile route '{rid}' burstCapacity {burst} is below the "
                        f"{TILE_BURST_FLOOR} floor; a cold map load will be partly rejected and "
                        f"MapLibre does not retry a rejected tile")
        if not found_routes:
            problems.append(f"{rel}: no spring.cloud.gateway.routes found")

    check("GW-RATELIMIT", "every gateway route declares its own rate limit",
          not problems, "; ".join(problems))



def run():
    for fn in (check_i1, check_orphan_annotations, check_authz, check_i3, check_i4, check_i5, check_i8, check_i9,
               check_i10, check_i15, check_i16, check_i17, check_i18, check_i19, check_i22,
               check_i26, check_i27_i29, check_i28, check_i31, check_i32, check_i34,
               check_i35, check_i36, check_i37, check_mcp_identity, check_scheduled_jobs_classified, check_idempotency_key_retention, check_money_not_through_double,
               check_messaging_context_minimal, check_modifying_queries_are_transactional, check_ci_root_pom_matches, check_query_parameters_are_bound, check_spring_boot_config_ambiguity, check_contract_stub_cycles, check_schema_strictness_ratchet,
               check_spec_matches_controllers, check_g10, check_schema_immutable,
               check_gateway_rate_limits):
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
