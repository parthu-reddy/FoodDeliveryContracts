#!/usr/bin/env python3
"""
Audits every HTTP contract against the controller route it claims to describe.

WHY
    Contract tests are only worth anything if the contract describes the real API. Three separate
    cases found by hand on 2026-08-20 say that is not safe to assume here:
      * LedgerService  getOrderLedgerAmount  -> the endpoint did not exist at all
      * BiddingEngine  fetchAds              -> returns List<SponsoredListingDTO>, contract claims
                                                a single object with a field that does not exist
      * DeliveryExecutive / Restaurant       -> ContractVerifierTest failing on content
    This script finds the rest programmatically instead of one at a time.

WHAT IT CHECKS
    1. Every HTTP contract parses (method + URL extractable).
    2. A controller route in the SAME module matches that method + path, allowing for {pathVariable}
       segments and the class-level @RequestMapping prefix.
    3. Reports the handler's return type so a human can compare it against the contract body.

    It deliberately does NOT try to compare response bodies automatically: the return types are
    generic (ResponseEntity<Page<X>>, Mono<ResponseEntity<List<Y>>>) and a naive comparison would
    produce false confidence. The return type is printed so the shape can be judged by reading.

USAGE
    python3 audit_http_contracts.py            # exit 1 if any contract has no matching route
    python3 audit_http_contracts.py --json
"""
import glob, json, os, re, sys

URL_PATS = [
    re.compile(r"url(?:Path)?\s*\(\s*'([^']+)'"),
    re.compile(r'url(?:Path)?\s*\(\s*"([^"]+)"'),
    re.compile(r"url(?:Path)?\s+'([^']+)'"),
    re.compile(r'url(?:Path)?\s+"([^"]+)"'),
    re.compile(r"url(?:Path)?\s*\(\s*\$\(.*?producer\s*\(\s*'([^']+)'", re.S),
    re.compile(r"url(?:Path)?\s*\(\s*value\s*\(.*?producer\s*\(\s*'([^']+)'", re.S),
]
METHOD_PAT = re.compile(r"method\s+'?\"?([A-Z]+)")
MAPPING_PAT = re.compile(
    r'@(Get|Post|Put|Delete|Patch|Request)Mapping\s*(?:\(\s*(?:value\s*=\s*)?["\']([^"\']*)["\'])?')
CLASS_RM_PAT = re.compile(r'@RequestMapping\s*\(\s*["\']([^"\']+)["\']\s*\)')

def norm(p):
    """Normalise a path for comparison: strip query, collapse {var} and concrete ids to '*'."""
    p = p.split('?')[0].rstrip('/')
    out=[]
    for seg in p.split('/'):
        if not seg: continue
        if seg.startswith('{') or re.fullmatch(r'[0-9a-fA-F-]{8,}|\d+', seg):
            out.append('*')
        else:
            out.append(seg)
    return '/' + '/'.join(out)


def path_matches(route: str, actual: str) -> bool:
    """A route segment of '*' (a {pathVariable}) matches ANY single concrete segment.

    Needed because a contract spells path variables out concretely -- /api/v1/wallets/CUSTOMER/<uuid>
    against a route of /api/v1/wallets/{entityType}/{entityId}. Comparing normalised strings marked
    that as a missing route when the endpoint plainly exists.
    """
    r, a = route.strip('/').split('/'), actual.strip('/').split('/')
    if len(r) != len(a): return False
    return all(rs == '*' or rs == as_ for rs, as_ in zip(r, a))

def routes_for(module):
    """Every (METHOD, normalised-path, returnType, where) the module's controllers expose.

    Mapping annotations and method signatures are found SEPARATELY. Trying to capture both in one
    regex silently missed every handler with another annotation in between (@PreAuthorize, @Operation),
    which produced false NO-ROUTE reports for endpoints that plainly exist.
    """
    found=[]
    for f in glob.glob(f"{module}/src/main/**/*.java", recursive=True):
        src=open(f, errors="replace").read()
        if "@RestController" not in src and "@Controller" not in src: continue
        head = src[:src.find("class ")] if "class " in src else src
        cm = CLASS_RM_PAT.search(head)
        prefix = cm.group(1) if cm else ""
        lines = src.split("\n")
        for i, line in enumerate(lines):
            m = re.search(r'@(Get|Post|Put|Delete|Patch)Mapping\b\s*(?:\(\s*(?:value\s*=\s*)?["\']([^"\']*)["\'])?', line)
            if not m: continue
            verb = m.group(1).upper()
            path = m.group(2) or ""
            # walk forward past any further annotations to the method signature
            ret, name = "?", "?"
            for j in range(i+1, min(i+8, len(lines))):
                sig = re.search(r'(?:public|protected|private)\s+([\w<>,.\[\]\? ]+?)\s+(\w+)\s*\(', lines[j])
                if sig:
                    ret, name = sig.group(1).strip(), sig.group(2); break
            found.append((verb, norm(prefix + "/" + path), ret, f"{os.path.basename(f)}#{name}"))
    return found

def main():
    results=[]
    for cf in sorted(glob.glob("*/src/test/resources/contracts/**/*.groovy", recursive=True)):
        s=open(cf, errors="replace").read()
        if "outputMessage" in s or "sentTo" in s: continue
        module = cf.split(os.sep)[0]
        mm = METHOD_PAT.search(s)
        url=None
        for pat in URL_PATS:
            u=pat.search(s)
            if u: url=u.group(1); break
        rec = {"module":module, "contract":os.path.basename(cf), "path":cf,
               "method": mm.group(1) if mm else None, "url": url}
        # A contract marked ignored() is a SPECIFICATION for something not built yet: Spring Cloud
        # Contract generates a @Disabled test, so it cannot produce a false green. Report it, but do
        # not count it as a problem -- otherwise the audit never reaches zero and people stop reading it.
        rec["pending"] = bool(re.search(r'^\s*ignored\s*\(\s*\)', s, re.M))
        if not mm or not url:
            rec["verdict"]="UNPARSED"; results.append(rec); continue
        want=(mm.group(1), norm(url))
        hits=[r for r in routes_for(module) if r[0]==want[0] and path_matches(r[1], want[1])]
        if hits:
            rec["verdict"]="OK"; rec["handler"]=hits[0][3]; rec["returns"]=hits[0][2]
        elif rec["pending"]:
            rec["verdict"]="PENDING"; rec["note"]="ignored() - specified, not yet implemented"
        else:
            near=[r for r in routes_for(module) if path_matches(r[1], want[1])]
            rec["verdict"]="NO ROUTE"
            rec["note"]=f"path exists under {[n[0] for n in near]}" if near else "no controller serves this path"
        results.append(rec)

    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
        return 1 if any(r["verdict"] not in ("OK", "PENDING") for r in results) else 0

    bad=[r for r in results if r["verdict"] not in ("OK", "PENDING")]
    print(f"{'module':<30} {'contract':<34} {'verdict':<9} detail")
    print("-"*128)
    for r in results:
        detail = r.get("handler","") + ("  -> "+r["returns"] if r.get("returns") else "") or r.get("note","")
        print(f"{r['module']:<30} {r['contract']:<34} {r['verdict']:<9} {detail[:60]}")
    pend=[r for r in results if r["verdict"]=="PENDING"]
    print(f"\n{len(results)} HTTP contract(s); {len(bad)} need attention"
          + (f"; {len(pend)} specified but not yet implemented (ignored())." if pend else "."))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
