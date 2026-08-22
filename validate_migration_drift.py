#!/usr/bin/env python3
"""
Detect migrations that were amended after they were applied.

Why this exists
---------------
Nothing in this repo is in production, so migrations are amended in place rather than corrected by
a follow-up migration. That is the right call, but it carries an operational half nothing enforced:
**every amendment invalidates every existing database.** Flyway records a checksum when it applies a
migration and refuses to start if the file later changes.

On 2026-08-21 that half was skipped. `frequency_cap` was added to `V1__init_schema.sql` seven hours
after V1 had been applied to `campaign_db`, and three separate signals still reported healthy:

  * six modules built green -- tests run on H2 with ddl-auto=create-drop, which regenerates the
    schema from the entities and therefore can never see the drift;
  * all ten contract validators passed;
  * the platform validator passed 41/41 *including its live-database checks*, against a database
    the application could not start on.

That last one is the real hazard: a green run against a broken database reads as assurance.

What it checks
--------------
For every module with migrations, for every row in that database's `flyway_schema_history`:

  1. the migration file still exists;
  2. its Flyway checksum still matches the one recorded at apply time.

CommonLibrary's migrations ship inside its jar under `db/migration/common/` and are picked up by
Flyway's recursive `classpath:db/migration` scan, so they are resolved for every service too.

Exit codes
----------
  0  every applied migration still matches its recorded checksum
  1  drift found -- at least one applied migration was amended or removed
  2  could not verify (no database reachable, no credentials, driver missing)

**2 is not a pass.** Refusing to report success when it cannot check is the entire point; a
validator that goes quiet when it loses its database recreates the failure it exists to catch.

Usage
-----
    python3 FoodDeliveryContracts/validate_migration_drift.py \
        --host localhost --port 5433 --user postgres --password "$POSTGRES_PASS"

Credentials default to POSTGRES_USER / POSTGRES_PASS from Deployment/.env when present.
"""

import argparse
import glob
import os
import re
import sys
import zlib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMON_MIGRATIONS = os.path.join(REPO, "CommonLibrary/src/main/resources/db/migration")

VERSION_RE = re.compile(r"^V([\d.]+)__")
# ${VAR:default} -> default, so urls like jdbc:postgresql://${DB_HOST:localhost}/${DB_NAME:wallet_db}
# resolve to what the service actually uses when nothing overrides it
PLACEHOLDER_RE = re.compile(r"\$\{[^:}]+:([^}]*)\}")
JDBC_RE = re.compile(r"jdbc:postgresql://[^/\s\"']+/(\w+)")


def flyway_checksum(path):
    """Reproduce Flyway's ChecksumCalculator: CRC32 over each line's UTF-8 bytes, BOM stripped.

    Line terminators are excluded, which is why a file that differs only in line endings keeps the
    same checksum -- and why a single changed character does not.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8-sig", errors="replace")
    crc = 0
    for line in re.split(r"\r\n|\r|\n", text):
        crc = zlib.crc32(line.encode("utf-8"), crc)
    return crc - (1 << 32) if crc >= (1 << 31) else crc  # Flyway stores a signed int


def migration_files(module_dir):
    """version -> path, for a module's own migrations plus CommonLibrary's jar-shipped ones."""
    found = {}
    for root in (os.path.join(module_dir, "src/main/resources/db/migration"), COMMON_MIGRATIONS):
        for path in glob.glob(os.path.join(root, "**", "*.sql"), recursive=True):
            m = VERSION_RE.match(os.path.basename(path))
            if m:
                found[m.group(1)] = path
    return found


def _scan(paths):
    for cfg in sorted(paths):
        try:
            with open(cfg, encoding="utf-8", errors="ignore") as fh:
                text = PLACEHOLDER_RE.sub(r"\1", fh.read())
        except OSError:
            continue
        m = JDBC_RE.search(text)
        if m:
            return m.group(1), cfg
    return None, None


def database_for(module_dir):
    """The database a module targets.

    Checks the module's own config first, then the config-server manifests in Deployment/ -- several
    services carry no datasource of their own and are configured entirely from there. Returns
    (database, source) so the caller can say where the answer came from, or (None, None) when it
    cannot be resolved at all. An unresolved module is reported, never silently skipped.
    """
    db, src = _scan(glob.glob(os.path.join(module_dir, "src/main/resources/application*.yml")))
    if db:
        return db, os.path.relpath(src, REPO)

    # fall back to Deployment/<spring.application.name>.yml
    name = None
    for cfg in glob.glob(os.path.join(module_dir, "src/main/resources/application.yml")):
        with open(cfg, encoding="utf-8", errors="ignore") as fh:
            m = re.search(r"application:\s*\n\s*name:\s*([A-Za-z0-9._-]+)", fh.read())
            if m:
                name = m.group(1)
    if name:
        db, src = _scan([os.path.join(REPO, "Deployment", f"{name}.yml")])
        if db:
            return db, os.path.relpath(src, REPO)
    return None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--host", default=os.environ.get("PGHOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PGPORT", "5433")))
    ap.add_argument("--user", default=os.environ.get("POSTGRES_USER"))
    ap.add_argument("--password", default=os.environ.get("POSTGRES_PASS"))
    args = ap.parse_args()

    # fall back to Deployment/.env, which is where these actually live
    env_path = os.path.join(REPO, "Deployment/.env")
    if (not args.user or not args.password) and os.path.isfile(env_path):
        with open(env_path, encoding="utf-8", errors="ignore") as fh:
            env = dict(
                line.split("=", 1) for line in fh.read().splitlines()
                if "=" in line and not line.strip().startswith("#")
            )
        args.user = args.user or env.get("POSTGRES_USER", "").strip()
        args.password = args.password or env.get("POSTGRES_PASS", "").strip()

    try:
        import psycopg2
    except ImportError:
        print("CANNOT VERIFY: psycopg2 is not installed (pip install psycopg2-binary)")
        return 2
    if not args.user or not args.password:
        print("CANNOT VERIFY: no credentials (pass --user/--password, or set them in Deployment/.env)")
        return 2

    # CommonLibrary is a library, not a service: its migrations ship inside the jar and are applied
    # to whichever service's database includes it. It owns no datasource, so there is nothing here
    # to check against -- its files are resolved as part of every service below.
    LIBRARIES = {"CommonLibrary"}

    # <REPO>/<Module>/src/main/resources/db/migration -> <REPO>/<Module>
    modules = sorted(
        p.split(os.sep + "src" + os.sep)[0]
        for p in glob.glob(os.path.join(REPO, "*/src/main/resources/db/migration"))
        if os.path.basename(p.split(os.sep + "src" + os.sep)[0]) not in LIBRARIES
    )
    if not modules:
        print("CANNOT VERIFY: found no modules with db/migration -- is this the right repo root?")
        return 2

    drift, checked, unreachable, unresolved = [], 0, [], []

    for module_dir in modules:
        module = os.path.basename(module_dir)
        db, src = database_for(module_dir)
        if not db:
            unresolved.append(module)
            print(f"  {module:30} UNRESOLVED  no postgres datasource found in its config or Deployment/")
            continue

        try:
            conn = psycopg2.connect(
                host=args.host, port=args.port, user=args.user,
                password=args.password, dbname=db, connect_timeout=5,
            )
        except Exception as exc:
            unreachable.append((module, db, str(exc).strip().splitlines()[0][:70]))
            print(f"  {module:30} UNREACHABLE  {db}")
            continue

        try:
            cur = conn.cursor()
            try:
                cur.execute("SELECT version, checksum, installed_on FROM flyway_schema_history "
                            "WHERE version IS NOT NULL ORDER BY installed_rank")
                rows = cur.fetchall()
            except Exception:
                conn.rollback()
                print(f"  {module:30} no history  {db} has never been migrated")
                continue

            files = migration_files(module_dir)
            problems = []
            for version, recorded, installed_on in rows:
                checked += 1
                path = files.get(version)
                if path is None:
                    problems.append(f"V{version} applied {installed_on:%Y-%m-%d %H:%M} "
                                    f"but no migration file exists for it any more")
                    continue
                if recorded is None:
                    continue  # baseline rows carry no checksum
                actual = flyway_checksum(path)
                if actual != recorded:
                    problems.append(
                        f"V{version} AMENDED after apply -- {os.path.basename(path)}\n"
                        f"      recorded {recorded} at {installed_on:%Y-%m-%d %H:%M}, file is now {actual}"
                    )
            if problems:
                print(f"  {module:30} DRIFT     {db}")
                for p in problems:
                    print(f"      {p}")
                drift.extend((module, p) for p in problems)
            else:
                print(f"  {module:30} ok        {db} ({len(rows)} applied)")
        finally:
            conn.close()

    print()
    if unresolved and not drift:
        print(f"CANNOT VERIFY: could not resolve a database for {len(unresolved)} module(s): "
              + ", ".join(unresolved))
        print("Refusing to report success while any module went unchecked.")
        return 2
    if unreachable and not drift:
        print(f"CANNOT VERIFY: {len(unreachable)} database(s) unreachable, no drift found in the rest.")
        for module, db, err in unreachable:
            print(f"  - {module}/{db}: {err}")
        print("Refusing to report success while any database went unchecked.")
        return 2
    if drift:
        print(f"FAIL: {len(drift)} migration(s) amended after being applied.")
        print("Recreate the affected database(s) -- amending in place is correct here, but it")
        print("invalidates every database the old version was applied to.")
        return 1
    if checked == 0:
        print("CANNOT VERIFY: no applied migrations were read from any database.")
        print("Refusing to report success on an empty corpus -- that is the failure this check exists")
        print("to catch, and it would be absurd to reproduce it here.")
        return 2
    print(f"PASS: {checked} applied migration(s) still match their recorded checksums.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
