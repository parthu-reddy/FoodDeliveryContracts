#!/usr/bin/env python3
"""
Detects autoconfiguration-exclusion leaks in messaging contract base classes.

THE DEFECT
    A BaseMessagingClass declares a nested @SpringBootConfiguration carrying
    @EnableAutoConfiguration(exclude = {DataSourceAutoConfiguration, HibernateJpaAutoConfiguration, ...}).

    Every service in this workspace component-scans com.fooddelivery. A nested
    @SpringBootConfiguration is therefore discoverable by OTHER tests in the same module, which then
    boot with JPA switched off and fail with "No bean named 'entityManagerFactory'". Measured on
    2026-08-19, this accounted for failures in 6 of the 12 failing reactor modules.

THE FIX THIS SCRIPT ENFORCES
    Exclusions belong in @SpringBootTest(properties = {"spring.autoconfigure.exclude=..."}), which is
    scoped to the declaring test class and cannot leak. LedgerService already does this and passes.

WHY A SCRIPT AND NOT grep
    grep matches the string inside javadoc that *explains* the trap -- it reported LedgerService as
    leaky when LedgerService is the one correct example. This strips comments and string literals
    before matching, and checks annotation structure rather than raw text.

USAGE
    python3 validate_messaging_base_isolation.py          # report; exit 1 if any leak
    python3 validate_messaging_base_isolation.py --json   # machine-readable
"""
import glob, json, os, re, sys

def strip_comments_and_strings(src: str) -> str:
    """Remove //, /* */ and string/char literals so annotations in prose never match."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == '/' and i + 1 < n and src[i+1] == '/':
            while i < n and src[i] != '\n': i += 1
        elif c == '/' and i + 1 < n and src[i+1] == '*':
            i += 2
            while i + 1 < n and not (src[i] == '*' and src[i+1] == '/'): i += 1
            i += 2
        elif c in '"\'':
            q = c; out.append(' '); i += 1
            while i < n:
                if src[i] == '\\': i += 2; continue
                if src[i] == q: i += 1; break
                i += 1
        else:
            out.append(c); i += 1
    return ''.join(out)


def strip_comments_only(src: str) -> str:
    """Remove comments but KEEP string literals, for detecting properties-based exclusions."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == '/' and i + 1 < n and src[i+1] == '/':
            while i < n and src[i] != '\n': i += 1
        elif c == '/' and i + 1 < n and src[i+1] == '*':
            i += 2
            while i + 1 < n and not (src[i] == '*' and src[i+1] == '/'): i += 1
            i += 2
        else:
            out.append(c); i += 1
    return ''.join(out)

EXCLUDE_ATTR = re.compile(
    r'@(?:org\.springframework\.boot\.autoconfigure\.)?EnableAutoConfiguration\s*\(\s*exclude\s*=',
    re.S)
NESTED_CONFIG = re.compile(
    r'@(?:org\.springframework\.boot\.)?SpringBootConfiguration', re.S)
PROPS_EXCLUDE = re.compile(r'spring\.autoconfigure\.exclude')

def analyse(path: str) -> dict:
    raw = open(path, errors='replace').read()
    code = strip_comments_and_strings(raw)
    has_nested_config = bool(NESTED_CONFIG.search(code))
    has_exclude_attr = bool(EXCLUDE_ATTR.search(code))
    # The properties form lives INSIDE a string literal, which strip_comments_and_strings() erases.
    # Check a comment-only strip instead, so the column reports the fix rather than always False.
    has_props_form = bool(PROPS_EXCLUDE.search(strip_comments_only(raw)))
    leaky = has_nested_config and has_exclude_attr
    return {
        "module": path.split(os.sep)[0],
        "path": path,
        "nested_spring_boot_configuration": has_nested_config,
        "exclude_attribute": has_exclude_attr,
        "properties_form": has_props_form,
        "leaky": leaky,
    }

def main() -> int:
    files = sorted(glob.glob(os.path.join("*", "src", "test", "**", "BaseMessagingClass.java"),
                             recursive=True))
    if not files:
        print("No BaseMessagingClass.java found. Run from the workspace root.")
        return 2
    results = [analyse(f) for f in files]

    if "--json" in sys.argv:
        print(json.dumps(results, indent=2)); 
        return 1 if any(r["leaky"] for r in results) else 0

    print(f"{'module':<32} {'nested @Config':<15} {'exclude attr':<13} {'properties':<11} verdict")
    print("-" * 92)
    for r in sorted(results, key=lambda x: x["module"]):
        verdict = "LEAKY" if r["leaky"] else "ok"
        print(f"{r['module']:<32} {str(r['nested_spring_boot_configuration']):<15} "
              f"{str(r['exclude_attribute']):<13} {str(r['properties_form']):<11} {verdict}")
    leaks = [r for r in results if r["leaky"]]
    print()
    print(f"{len(files)} base class(es) checked; {len(leaks)} leak autoconfiguration exclusions.")
    if leaks:
        print("\nEach leaky class must move its exclusions into the enclosing")
        print("@SpringBootTest(properties = {\"spring.autoconfigure.exclude=...\"}).")
        for r in leaks: print(f"  - {r['path']}")
        return 1
    print("VALIDATION PASSED: no base class can leak exclusions into unrelated tests.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
