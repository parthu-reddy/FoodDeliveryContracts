#!/usr/bin/env python3
"""
Checks that every HTTP contract's owning controller is actually mounted by its module's test base.

THE DEFECT
    Spring Cloud Contract runs generated tests against whatever the base class configured.
    RestAssuredMockMvc.standaloneSetup(controller) mounts ONLY the controllers handed to it, so a
    contract for a route on any other controller returns 404 from an empty dispatcher. In the failure
    output that is indistinguishable from an endpoint that does not exist -- which is exactly why the
    404s in DeliveryExecutiveApplication and RestaurantApplication were misread as missing APIs.

ALSO CHECKED
    Handlers taking an interface Spring resolves via a custom argument resolver (Pageable, Sort).
    Standalone MockMvc registers no resolvers, so these fail with
    "No primary or single unique constructor found for interface ...Pageable" unless the base class
    calls setCustomArgumentResolvers(...).

NOT CHECKED
    Whether the mocked collaborators return data the contract expects. A base class can mount the
    right controller and still fail, because it stubs every repository call to empty and the contract
    asserts rows. That is a fixture problem, visible as a handler 404 or a body mismatch, and it needs
    reading rather than a script.

USAGE
    python3 validate_contract_base_coverage.py           # exit 1 if any contract is unmounted
    python3 validate_contract_base_coverage.py --json
"""
import glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit_http_contracts import (URL_PATS, METHOD_PAT, CLASS_RM_PAT, norm, path_matches, routes_for)

SETUP_PAT = re.compile(r'standaloneSetup\s*\(([^;]*)\)', re.S)
CTOR_PAT = re.compile(r'\bnew\s+(?:[\w.]*\.)?([A-Z]\w*Controller)\s*\(')
RESOLVER_PAT = re.compile(r'setCustomArgumentResolvers\s*\(')
RESOLVED_IFACES = ("Pageable", "Sort")

def base_class_files(module):
    return [f for f in glob.glob(f"{module}/src/test/**/*.java", recursive=True)
            if "ContractTestBase" in os.path.basename(f)]

def mounted_controllers(module):
    """Controller simple-names actually handed to standaloneSetup, plus whether a resolver is set.

    Resolves through local variables: `XController c = new XController(...)` then
    `standaloneSetup(c)`. An earlier version guessed the variable name from the class name, which
    failed for the common `... controller = new InternalDeliveryController(...)` and produced false
    NOT-MOUNTED reports for modules whose builds demonstrably pass.
    """
    names, has_resolver = set(), False
    for f in base_class_files(module):
        src = open(f, errors="replace").read()
        if RESOLVER_PAT.search(src): has_resolver = True
        # var -> ControllerType, from declarations and assignments
        var_type = {}
        # types may be fully qualified and the declaration may span lines
        for m in re.finditer(r'(?:[\w.]*\.)?([A-Z]\w*Controller)\s+(\w+)\s*=\s*new\s+(?:[\w.]*\.)?([A-Z]\w*Controller)\s*\(',
                             src, re.S):
            var_type[m.group(2)] = m.group(3)
        for m in re.finditer(r'\b(\w+)\s*=\s*new\s+(?:[\w.]*\.)?([A-Z]\w*Controller)\s*\(', src, re.S):
            var_type.setdefault(m.group(1), m.group(2))
        for m in SETUP_PAT.finditer(src):
            arg = m.group(1)
            for ctor in CTOR_PAT.findall(arg):       # inlined: standaloneSetup(new XController(...))
                names.add(ctor)
            for ident in re.findall(r'\b(\w+)\b', arg):
                if ident in var_type: names.add(var_type[ident])
    return names, has_resolver

def owning_controller(module, method, url):
    for verb, path, ret, where in routes_for(module):
        if verb == method and path_matches(path, norm(url)):
            return where.split("#")[0].replace(".java", ""), ret, where.split("#")[1]
    return None, None, None

def main():
    results = []
    modules = sorted({f.split(os.sep)[0] for f in glob.glob("*/src/test/resources/contracts/**/*.groovy", recursive=True)})
    for module in modules:
        mounted, has_resolver = mounted_controllers(module)
        for cf in sorted(glob.glob(f"{module}/src/test/resources/contracts/**/*.groovy", recursive=True)):
            s = open(cf, errors="replace").read()
            if "outputMessage" in s or "sentTo" in s: continue
            mm = METHOD_PAT.search(s)
            url = next((p.search(s).group(1) for p in URL_PATS if p.search(s)), None)
            rec = {"module": module, "contract": os.path.basename(cf),
                   "mounted_in_base": sorted(mounted)}
            if not mm or not url:
                rec["verdict"] = "UNPARSED"; results.append(rec); continue
            owner, ret, handler = owning_controller(module, mm.group(1), url)
            rec["handler"] = handler
            rec["owner"] = owner; rec["returns"] = ret
            if owner is None:
                rec["verdict"] = "NO ROUTE"
            elif owner not in mounted:
                rec["verdict"] = "NOT MOUNTED"
            elif ret and any(i in (ret or "") for i in RESOLVED_IFACES) and not has_resolver:
                rec["verdict"] = "NO RESOLVER"
            else:
                rec["verdict"] = "OK"
            # a handler taking Pageable is detectable from the module's routes, not the return type
            results.append(rec)

    # Flag a missing argument resolver ONLY where a contract actually targets a handler that takes
    # one. Flagging any controller in the module produced findings for modules that pass their build.
    for module in modules:
        mounted, has_resolver = mounted_controllers(module)
        if has_resolver: continue
        for rec in [r for r in results if r["module"] == module and r.get("owner")
                    and r["verdict"] == "OK" and r.get("handler")]:
            for f in glob.glob(f"{module}/src/main/**/{rec['owner']}.java", recursive=True):
                src = open(f, errors="replace").read()
                # Only the handler this contract targets matters. Checking the whole controller
                # flagged contracts whose own handler takes no Pageable and which demonstrably pass.
                # Scan from the method name to its opening brace. A naive [^)]* stops at the first
                # ')' -- which in `@PageableDefault(size = 50) Pageable pageable` is the annotation's,
                # truncating the parameter list before the Pageable ever appears.
                idx = src.find(rec["handler"] + "(")
                params = ""
                if idx != -1:
                    brace = src.find("{", idx)
                    params = src[idx:brace] if brace != -1 else src[idx:idx + 500]
                if re.search(r'\bPageable\b', params):
                    rec["verdict"] = "NO RESOLVER"
                    rec["returns"] = "handler takes Pageable"

    if "--json" in sys.argv:
        print(json.dumps(results, indent=2)); return 1 if any(r["verdict"] != "OK" for r in results) else 0

    bad = [r for r in results if r["verdict"] != "OK"]
    print(f"{'module':<30} {'contract':<36} {'verdict':<12} owner")
    print("-" * 110)
    for r in results:
        if r["verdict"] == "OK": continue
        print(f"{r['module']:<30} {r['contract']:<36} {r['verdict']:<12} {r.get('owner') or '-'}")
    print(f"\n{len(results)} check(s); {len(bad)} problem(s).")
    if bad:
        print("\nNOT MOUNTED  -> add the controller to the base class's standaloneSetup(...)")
        print("NO RESOLVER  -> MockMvcBuilders.standaloneSetup(c).setCustomArgumentResolvers(new PageableHandlerMethodArgumentResolver())")
        print("NO ROUTE     -> the endpoint genuinely does not exist (phase 2)")
        return 1
    print("VALIDATION PASSED: every HTTP contract's controller is mounted.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
