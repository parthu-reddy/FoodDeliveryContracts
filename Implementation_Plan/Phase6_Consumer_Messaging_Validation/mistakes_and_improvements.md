# Phase 6: Consumer Messaging Validation — Findings (phase in progress)

## The try/catch shells were a symptom, not the disease

It is tempting to read the 25 vacuous tests as laziness and "just add assertions". They could not
have worked: `stubTrigger.trigger(label)` routes through a `MessageVerifierSender`, and every
`KafkaMessageVerifier` in the workspace throws `UnsupportedOperationException` from `send()`.
Whoever wrote them hit a real wall and wrapped it in a `catch (Exception)` to get green.

The fix had to be built before any assertion was possible: `KafkaStubMessageSender` implements the
sender, publishes the stub body to the destination topic, and forwards contract headers (skipping
Spring's internal `id`/`timestamp`).

**Lesson:** when a whole category of tests is vacuous in the same way, look for the missing
capability before assuming neglect. The uniformity was the clue.

## An 18-POM build blocker sat underneath the whole phase

`mvn install` failed in **every** service with
`Failed to connect to MBean server at port 9001` — `spring-boot-maven-plugin` `start`/`stop`
executions booting the app during `pre-integration-test`. Consumer CDC resolves stubs from `~/.m2`,
so with installs broken, no consumer test could ever run against a current contract.

Verified safe to remove before touching anything: there is no `maven-failsafe-plugin` and no
`*IT.java` anywhere, so the app was being booted for integration tests that do not exist. This was
already documented as the resolution in Phase 3.1's mistakes file for a single service; it was
never applied fleet-wide.

**Lesson:** when a documented fix exists for one service, check whether the same defect exists in
the other seventeen.

## Stale stub jars validate silently against old contracts

After splitting `wallet_events` into `wallet_events_earnings` and `wallet_events_reversal`, the jar
in `~/.m2` still contained the old single `wallet_events.groovy`. `stubsMode = LOCAL` resolves from
the local repository, so a consumer test would have happily validated against a contract that no
longer exists.

**Lesson:** `mvn install` the producer before running any consumer test, and confirm the stub jar's
contents rather than its timestamp. `unzip -l <stubs.jar> | grep groovy` takes a second.

## Green means nothing here until the negative control runs

Every one of the 25 tests was already green while asserting nothing. For this phase specifically,
a passing test is not evidence of anything. The reference implementation was only trusted after
pointing its trigger at `wallet_events_reversal` (a debit) and confirming the credit assertion
failed.

**Rule for the rollout:** no consumer test counts as done until it has been made to fail on purpose.


## A negative control can itself be invalid — check that it can fail

Verifying `PaymentEventConsumerContractTest`, the first inversion tried was flipping
`verify(repo).method()` to `verify(repo, never()).method()` and expecting a failure. **Both
variants passed**, which looked briefly like a contradiction.

The cause: `never()` inside `await().untilAsserted(...)` is satisfied immediately at t=0, before the
Kafka message has arrived. Awaitility returns on first success, so the assertion never sees the
later call. The inversion proved nothing.

The valid form is to assert an interaction that should **never** occur — here
`verify(orderRepository).findById(any())`, unreachable because the mocked repository returns an
empty `Optional` and the consumer returns early — and confirm the await times out and errors.

**Rule:** a negative control must be capable of failing *for the reason you think*. With Awaitility,
invert by asserting something that never becomes true, never by adding `never()`. Had this gone
unnoticed, four tests would have carried a control that validated nothing.

## The audit found more than the tests would have, far cheaper

Writing consumer tests was finding defects at a high rate, but each cost a full test-writing cycle.
`FoodDeliveryContracts/audit_consumer_contract_shapes.py` compares every `@KafkaListener`'s field
reads against the contract for its topic, and found the remaining mismatches in one run.

**Result: 6 confirmed defects, all one bug class** — producer emits a flat DTO, consumer requires
`{eventType, payload}`, failure is silent (no exception, no DLQ, nothing at error level).

| Consumer | Topic | Effect |
|---|---|---|
| `GenericWalletEventConsumer` | wallet-events | earnings never credited — **FIXED** |
| `TopupEventConsumer` | payment-events | advertiser top-ups never credited |
| `ConfirmEventProcessor` | ondc.order.created | ONDC confirm callback never fires |
| `CampaignEventConsumer` (BiddingEngine) | ad-events | campaigns never indexed/removed from matcher |
| `CampaignSyncConsumer` (BudgetLimiting) | ad-events | pacing data never synced to Redis |
| `AdNotificationListener` (CommunicationIntegration) | ad-events | advertiser alerts never sent |

The last two were found **only** by the audit. Their significance is that all three `ad-events`
consumers are dead: one producer shape mismatch silently disabled an entire fan-out. Paused
campaigns keep serving and keep spending.

### Refining the audit mattered

The first run flagged 10, including two false positives. Two distinctions fixed it:

- `.has("x")` is an existence *probe*; a field only ever probed is optional by construction and must
  not count as a missing field. Only `.get()`/`.path()` are required reads.
- A `root.has("payload") ? root.get("payload") : root` ternary means the consumer tolerates both
  shapes — that is the fix applied to `GenericWalletEventConsumer`, and the audit must recognise it
  or it will keep reporting repaired code.

**Lesson:** a static audit's value is proportional to its precision. At 10 findings with 2 false
positives it invites dismissal; at 8 with 0 it gets acted on. Spend the extra pass on the heuristic.

### Remaining flags are contract gaps, not consumer bugs

- `DispatchEventConsumer` reads `excludedDriverIds`, which `logistics_dispatch.groovy` omits (the
  producer only sets it when non-empty). **The contract should declare it as optional.**
- `PaymentGatewayIntegration.OrderEventConsumer` handles `PAYMENT_REFUND_REQUESTED`, which has no
  contract on order-events.
- `CustomerApplication.OrderEventConsumer` reads `status`, used by other order-events event types
  that have no contracts yet.

Each is a missing contract (Phase 5 work), not a defect.
