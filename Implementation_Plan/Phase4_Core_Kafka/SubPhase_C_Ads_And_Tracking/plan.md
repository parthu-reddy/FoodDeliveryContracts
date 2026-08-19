# SubPhase 4C: Ads & Tracking Kafka Validations

## Objective
Replace empty `@AutoConfigureStubRunner` shell tests in the advertising and tracking domains with actual assertions.

## Target Implementations
1. **`CampaignService`**
   - `KafkaAnalyticsConsumerTest.java`: Trigger `ad-tracking-events` and assert analytics aggregation.

2. **`BiddingEngine`**
   - `CampaignEventConsumerTest.java`: Assert bidding engine state updates.

3. **`BudgetLimitingService`**
   - `CampaignSyncConsumerTest.java`: Assert budget constraints cache updates.

## Steps
1. Trigger the tracking mock events via `stubTrigger`.
2. Wait for async processing.
3. Assert cache or DB states reflecting the analytical aggregations.
