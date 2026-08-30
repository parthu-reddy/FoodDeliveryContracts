#!/usr/bin/env bash
# Two-pass build: publish every artifact first, then verify against it.
#
# WHY TWO PASSES
# --------------
# Consumer contract tests replay a recording (a "stub jar") produced by the PRODUCER's build and
# resolved at test time from ~/.m2. Five producer/consumer pairs are mutual (see
# RandomDocuments/RemainingWork_2026-08-27/Phase8_ContractStubCircularity), so in any single pass
# one side of each pair is guaranteed to read the PREVIOUS build's recording. Demonstrated
# 2026-08-27: a producer contract broken in source still left its consumer's test green, purely
# because a stale jar sat in the local repository.
#
# Pass 1 publishes every jar, test-jar and stub jar. Pass 2 then verifies with everything current,
# so build order stops mattering.
#
# NOTES, all measured rather than assumed:
#   * `-DskipTests` does NOT skip stub generation -- conversion is bound to process-test-resources
#     and packaging to `package`. Pass 1 is therefore fast and still publishes valid stubs.
#   * Pass 2 MUST use `clean`. Without it Spring Cloud Contract silently skips its generated tests:
#     127 test classes instead of 148 on 2026-08-27, and a green build that proves nothing.
#   * Pass 2 cannot run without pass 1: 13 modules depend on common-library's TEST-jar, which the
#     `test` phase never produces.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
# Offline by default: locally ~/.m2 is fully populated, and -o keeps the build fast and
# deterministic. A clean machine has nothing to be offline WITH -- it cannot resolve even
# spring-boot-starter-parent -- so CI sets MVN_OFFLINE="" to allow downloads. Overriding this is
# the only supported way to run on a cold cache; do not drop the -o for local runs.
MVN_OFFLINE="${MVN_OFFLINE--o}"
MVN_FLAGS="-B $MVN_OFFLINE -Dnet.bytebuddy.experimental=true"

# BOTH passes run in parallel. Measured 2026-08-28 on a 10-core machine:
#   serial    pass 1 123s + pass 2 ~23 min  = ~25 min
#   -T 1C     pass 1  76s + pass 2   385s   =  7.7 min, 24/24 modules, 340 tests, 0 failures
# 340 tests in both, so nothing is being skipped to buy the speed.
#
# Parallelising pass 2 required removing shared stub ports first. Stub runners bind TCP ports, which
# no pom declares, so Maven cannot know two modules want the same one -- 8090, 8091, 8092 and 8094
# were each claimed by 2-4 modules and raced under -T with "BindException: Address already in use".
#
# THE INVARIANT IS: no two modules may bind the same port. Fixed ports are fine when unique.
# Most consumers now omit the port entirely and resolve the stub by service id, which only works for
# a @FeignClient WITHOUT an explicit `url`. BudgetLimitingService's CampaignClient does set one, so
# it bypasses discovery and keeps a pinned 8095 -- see the note in its application-contract-test.yml.
# Before adding a stub runner anywhere, check the port is unused:
#   grep -rnE ':\+:stubs:[0-9]+|localhost:80[0-9][0-9]' */src/test
echo "==> Pass 1/2: publishing all artifacts (jars, test-jars, stub jars)"
if ! mvn $MVN_FLAGS clean install -DskipTests -T 1C; then
  echo "FAIL: pass 1 could not publish artifacts"; exit 1
fi

echo "==> Checking every published stub jar actually contains stubs"
python3 - <<'PY' || exit 1
import sys, zipfile
from pathlib import Path
bad = []
jars = sorted((Path.home() / '.m2/repository/com/fooddelivery').rglob('*-stubs.jar'))
for jar in jars:
    try:
        n = sum(1 for e in zipfile.ZipFile(jar).namelist() if e.endswith(('.json', '.groovy')))
    except Exception as exc:
        bad.append(f'{jar.name}: unreadable ({exc})'); continue
    if n == 0:
        bad.append(f'{jar.name}: contains no stubs')
print(f"    {len(jars)} stub jars, {len(bad)} unusable")
for b in bad:
    print("    FAIL:", b)
sys.exit(1 if bad else 0)
PY

echo "==> Pass 2/2: running every test against the freshly published artifacts"
mvn $MVN_FLAGS test -fae -T 1C
STATUS=$?

echo "==> Confirming the generated contract tests actually ran"
echo "    (a non-clean run silently skips them; this is the check that catches that)"

# This was a stub until 2026-08-28: it printed the line above and exited, verifying nothing.
# It now compares the contract test classes Spring Cloud Contract GENERATED against the ones
# surefire actually REPORTED, per module. A generated class with no surefire report is a test that
# was compiled and then silently not run, which is exactly the non-clean-build failure mode.
python3 - <<'PYCHECK'
import sys
from pathlib import Path

generated, executed = {}, {}
for f in Path('.').glob('*/target/generated-test-sources/contracts/**/*Test.java'):
    generated.setdefault(f.parts[0], set()).add(f.stem)
for r in Path('.').glob('*/target/surefire-reports/TEST-*.xml'):
    executed.setdefault(r.parts[0], set()).add(r.stem.replace('TEST-', '').split('.')[-1])

if not generated:
    print("    FAIL: no generated contract tests found at all. Contract generation did not run.")
    sys.exit(1)

missing, total_gen, total_ran = [], 0, 0
for mod in sorted(generated):
    g = generated[mod]
    hit = g & executed.get(mod, set())
    total_gen += len(g)
    total_ran += len(hit)
    for cls in sorted(g - hit):
        missing.append(f"{mod}: {cls}")

if missing:
    print(f"    FAIL: {len(missing)} generated contract test(s) were never executed:")
    for m in missing:
        print(f"           {m}")
    print("    A clean build regenerates and runs these; a non-clean one compiles and skips them.")
    sys.exit(1)

print(f"    OK: {total_ran}/{total_gen} generated contract tests executed across {len(generated)} modules")
PYCHECK
CONTRACT_STATUS=$?
if [ $CONTRACT_STATUS -ne 0 ]; then
  exit $CONTRACT_STATUS
fi

exit $STATUS
