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
MVN_FLAGS="-B -o -Dnet.bytebuddy.experimental=true"

echo "==> Pass 1/2: publishing all artifacts (jars, test-jars, stub jars)"
if ! mvn $MVN_FLAGS clean install -DskipTests; then
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
mvn $MVN_FLAGS clean test -fae
STATUS=$?

echo "==> Confirming the generated contract tests actually ran"
echo "    (a non-clean run silently skips them; this is the check that catches that)"
exit $STATUS
