# FoodDeliveryContracts

**Do not delete this directory. It is not a Maven module and has no pom, which is why nothing
references it — but the tooling here is load-bearing.**

It contains two things with completely different statuses.

## 1. Contract validation tooling — ACTIVE, load-bearing

Eighteen Python scripts. They are not Maven artifacts and are not meant to be referenced from a pom:
they are run by hand, and are scheduled to run in CI (see
`HttpContractRemediation/Phase4_Enforcement/`). Several were used repeatedly during the 2026-08-20
remediation and each one exists because it caught something a manual grep did not.

| Script | Guards against |
|---|---|
| `audit_http_contracts.py` | a contract whose route no endpoint serves |
| `validate_contract_base_coverage.py` | a contract whose controller the test harness never mounts |
| `validate_vacuous_consumer_tests.py` | tests that trigger a stub and assert nothing |
| `validate_messaging_base_isolation.py` | autoconfiguration exclusions leaking across tests |
| `validate_contract_topics.py` | a contract targeting a topic nothing publishes to |
| `sync_messaging_ids.py --check` | hardcoded ids where a regex matcher is required |
| `audit_consumer_contract_shapes.py` | consumer/producer payload-shape mismatches |
| `validate_consumer_assertions.py` | messaging consumer tests that assert nothing |
| `validate_phase3_consumers.py` | HTTP consumer tests that inject a client and never call it |
| `validate_broker_url.py` | stub resolution drifting off `~/.m2` |

The remainder (`fix_*.py`, `set_broker_url.py`, `switch_to_local_stubs.py`, `scaffold_plans.py`,
`remove_boot_start_stop.py`, `update_checklists.py`) are one-shot migration scripts that have already
run. They are kept as a record of how a fleet-wide edit was performed, since each documents a mass
change that would otherwise be invisible in a diff. **Safe to archive, not safe to delete silently.**

`Implementation_Plan/` is the 8-phase contract-testing plan and its status dashboard.

## 2. `META-INF/` — the dead half, and a hazard

`META-INF/com.fooddelivery/<artifact>/<version>/contracts/*.groovy` is the layout Spring Cloud
Contract expects of a **git-based stub broker**. It holds 13 hand-written contracts.

**It was never wired up, and it cannot be.** The intended configuration was
`git://file:///…/FoodDeliveryContracts/.git`. That is structurally unusable here: the workspace path
contains a space, and Spring Cloud Contract decodes `%20` and then re-parses, failing in both the
Maven plugin and `BatchStubRunner`. All 15 services therefore resolve stubs from `~/.m2` with
`stubsMode: LOCAL`, and none reference this tree.

**It has since diverged from the real contracts, in both directions.** As of 2026-08-20:

- `get-order-invoice.groovy` here asserts `totalAmount` — which is **correct**, and was what the live
  contract had wrong until it was fixed that day.
- `get-driver.groovy` here asserts `name` and `status: "AVAILABLE"` — **both wrong**. The entity
  serialises `fullName`, and `DeliveryExecutiveStatus` is `OFFLINE | ONLINE | ON_DELIVERY`. That is the
  exact defect corrected in the live contract on 2026-08-20.

So it is not a stale mirror that could simply be refreshed; it is a partly-right, partly-wrong parallel
set. **If anyone wires this broker up, services will verify against a mixture of correct and incorrect
shapes** — worse than having no broker, because the failures would look authoritative.

### Recommendation

Delete `META-INF/`, or move it to `META-INF.abandoned/` with this note attached. The live contracts in
each service's `src/test/resources/contracts/` are the source of truth. If a shared broker is wanted
later, publish stubs from the services (tracked as item 10 in `RandomDocuments/claude/`) rather than
resurrecting this tree.

## Why "0 pom references" is expected, not a smell

Nothing here is a Java artifact. The scripts are tooling; `META-INF/` was only ever meant to be read
by Spring Cloud Contract over a `git://` URL that never worked. Absence of pom references says nothing
about whether the directory is alive — the scripts are used constantly and referenced from
`HttpContractRemediation/`, `RandomDocuments/claude/`, and this repo's CI plan.
