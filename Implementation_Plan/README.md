# Consumer-Driven Contract Testing — Implementation Plan

Single source of truth for CDC across the Food Delivery microservices. Every status below was
**verified against the codebase and by running the tests**, not carried over from a checkbox.

Last verified: 2026-08-19.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| [Phase1_Foundation](Phase1_Foundation/) | SCC deps, BOM, git broker wiring | Complete |
| [Phase2_Core_HTTP](Phase2_Core_HTTP/) | Contracts for CommonLibrary Feign clients | Complete |
| [Phase3_Service_HTTP](Phase3_Service_HTTP/) | Service-specific HTTP contracts + consumer validation | 5 gaps open |
| [Phase4_Core_Kafka](Phase4_Core_Kafka/) | Messaging contracts + producer verification | Producer side complete |
| [Phase5_Messaging_Realignment](Phase5_Messaging_Realignment/) | Make messaging contracts match real event schemas | Not started - **blocks Phase 6** |
| [Phase6_Consumer_Messaging_Validation](Phase6_Consumer_Messaging_Validation/) | Real assertions for all 25 @KafkaListener consumers | 4 done (financial first), 14 achievable, 8 blocked |
| [Phase7_Edge_Kafka](Phase7_Edge_Kafka/) | eventType headers, enum fallbacks, orphaned annotations | Not started |
| [Phase8_CICD_And_Broker_Publish](Phase8_CICD_And_Broker_Publish/) | Publish stubs to the broker, gate CI on contracts | Not started |

## Current test reality

| Layer | State |
|---|---|
| HTTP producer contracts | 48 local contracts; producer verification green |
| HTTP consumer validation | 21 tests green across 7 services |
| Messaging producer verification | 17 tests green across 8 services |
| Messaging consumer validation | **25 tests, 0 assertions, all swallow exceptions** |

## The one thing to understand before touching Phase 5 or 6

The messaging suite currently proves nothing. Contracts use the envelope
`{eventId, type, payload: {...}}` with integer ids, while the real events are flat serialized DTOs
(`OrderCreatedEvent` = `{orderId: UUID, customerId: UUID, restaurantId: UUID, totalAmount, ...}`)
whose fields every consumer reads at the **root**. The producer tests pass only because each
`triggeredBy` method hand-writes the same invented JSON the contract asserts - a closed loop that
never touches production code.

Fixing the contract body alone does not fix this. The trigger must publish through the real
production path (the Outbox), otherwise the fiction just moves. That is Phase 5.

## Recommended order

Phase 5 first (it is the only item where the current state actively misleads), then 6, then the
Phase 3 gaps, then 7, then 8. Do **not** publish to the broker (Phase 8) before Phase 5 settles -
roughly a third of the contracts are about to change shape.

## Conventions

- Every phase folder holds exactly `plan.md`, `checklist.md`, `validation.md`, and gains
  `mistakes_and_improvements.md` on completion.
- `validation.md` defines **programmatic** checks (Python/AST/YAML/XML parsers or exact test
  counters). Never `grep`/`sed` alone - see Phase 1 for a nesting bug grep cannot see.
- Reusable validators live in `FoodDeliveryContracts/`. Current state at a glance:

  ```bash
  python3 FoodDeliveryContracts/validate_broker_url.py            # Phase 1  -> passes
  python3 FoodDeliveryContracts/validate_phase2_paths.py          # Phase 2  -> passes
  python3 FoodDeliveryContracts/validate_phase3_consumers.py      # Phase 3  -> 6 problems
  python3 FoodDeliveryContracts/sync_messaging_ids.py --check     # Phase 4  -> passes
  python3 FoodDeliveryContracts/validate_consumer_assertions.py   # Phase 6  -> 25/25 fail
  ```

  Phases 5, 7 and 8 define their validators in their own `validation.md`; they are written as part
  of executing those phases.
- Lessons are centralised in
  [CommonMistakesDocumentation/ContractTesting](../../CommonMistakesDocumentation/ContractTesting/).
