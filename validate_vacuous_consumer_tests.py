#!/usr/bin/env python3
"""
Identifies consumer tests that verify nothing, so they can be removed safely.

A test qualifies as VACUOUS only if ALL of these hold:
  1. it calls stubTrigger.trigger(...)
  2. it declares exactly one @Test method
  3. it contains no assertion of any kind (JUnit, AssertJ, Hamcrest, Awaitility)
  4. it contains no Mockito verify(...)
  5. it catches Exception around the trigger and does not rethrow

Such a class cannot fail for any reason related to the code under test: the trigger either works or
throws, and the throw is swallowed. It is green whether the consumer is correct, broken, or absent.

Measured 2026-08-20: 21 such classes across 14 modules, costing 41.8 minutes of build time, and
accounting for 7 of the failing test classes in the reactor.

DELETION IS ONLY HALF THE JOB. These classes mark consumers that still need real coverage; the list
is recorded in RandomDocuments/claude/06_Phase6ConsumerTests/. Removing them without writing real
tests trades a false signal for a missing one.

USAGE
    python3 validate_vacuous_consumer_tests.py            # report; exit 1 if any remain
    python3 validate_vacuous_consumer_tests.py --json     # machine-readable
"""
import glob, json, os, re, sys

ASSERT_PAT = re.compile(
    r'\bassert[A-Z]\w*\s*\(|\bassertThat\s*\(|\bAssertions\.|\bassertEquals\b|\bassertTrue\b'
    r'|\bassertNotNull\b|\bawait\(\)|\bassertThatThrownBy\b|\bcatchThrowable\b')
VERIFY_PAT = re.compile(r'\bMockito\.verify\s*\(|\bverify\s*\(\s*\w')
TRIGGER_PAT = re.compile(r'stubTrigger\s*\.\s*trigger\s*\(')
TEST_PAT = re.compile(r'@Test\b')
SWALLOW_PAT = re.compile(r'catch\s*\(\s*(?:final\s+)?Exception\s+\w+\s*\)\s*\{(?:(?!throw).)*?\}', re.S)

def analyse(path):
    src = open(path, errors='replace').read()
    n_tests = len(TEST_PAT.findall(src))
    return {
        "path": path,
        "module": path.split(os.sep)[0],
        "class": os.path.basename(path)[:-5],
        "triggers_stub": bool(TRIGGER_PAT.search(src)),
        "test_methods": n_tests,
        "has_assertion": bool(ASSERT_PAT.search(src)),
        "has_verify": bool(VERIFY_PAT.search(src)),
        "swallows": bool(SWALLOW_PAT.search(src)),
    }

def is_vacuous(r):
    return (r["triggers_stub"] and r["test_methods"] == 1
            and not r["has_assertion"] and not r["has_verify"] and r["swallows"])

def main():
    files = sorted(glob.glob(os.path.join("*", "src", "test", "**", "*.java"), recursive=True))
    results = [analyse(f) for f in files if TRIGGER_PAT.search(open(f, errors='replace').read())]
    vac = [r for r in results if is_vacuous(r)]
    keep = [r for r in results if not is_vacuous(r)]

    if "--json" in sys.argv:
        print(json.dumps({"vacuous": vac, "meaningful": keep}, indent=2))
        return 1 if vac else 0

    print(f"{'module':<30} {'class':<46} tests assert verify swallow")
    print("-" * 104)
    for r in sorted(vac, key=lambda x: (x["module"], x["class"])):
        print(f"{r['module']:<30} {r['class']:<46} {r['test_methods']:^5} "
              f"{str(r['has_assertion']):^6} {str(r['has_verify']):^6} {str(r['swallows']):^7}")
    print()
    print(f"{len(results)} stub-triggering test class(es) examined.")
    print(f"  VACUOUS (verify nothing, safe to delete): {len(vac)}")
    print(f"  meaningful (kept):                        {len(keep)}")
    if keep:
        print("\n  kept because they assert or verify:")
        for r in sorted(keep, key=lambda x: x["module"]):
            why = []
            if r["has_assertion"]: why.append("asserts")
            if r["has_verify"]: why.append("verifies")
            if r["test_methods"] != 1: why.append(f"{r['test_methods']} tests")
            if not r["swallows"]: why.append("propagates exceptions")
            print(f"    {r['module']}/{r['class']}  ({', '.join(why)})")
    return 1 if vac else 0

if __name__ == "__main__":
    sys.exit(main())
