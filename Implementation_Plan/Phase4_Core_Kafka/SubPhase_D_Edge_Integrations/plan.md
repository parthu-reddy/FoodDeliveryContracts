# SubPhase 4D: Edge Integrations Kafka Validations

## Objective
Replace empty `@AutoConfigureStubRunner` shell tests in the edge integration layers with actual assertions.

## Target Implementations
1. **`ONDCIntegrationService`**
   - `CatalogDeltaSyncServiceTest.java`: Assert catalog delta synchronization.
   - `ProactiveStatusPublisherTest.java`: Assert ONDC fulfillment status broadcast.
   - `SearchEventProcessorTest.java`: Assert beckn search request processing.
   - `ConfirmEventProcessorTest.java`: Assert beckn confirm request processing.

2. **`MapsIntegration`**
   - `DispatchEventConsumerTest.java`: Assert geocoding external API mocked interactions upon dispatch event.

3. **`CommunicationIntegration`**
   - `NotificationEventConsumerTest.java`: Assert notification dispatch to users.
   - `AdNotificationListenerTest.java`: Assert ad-specific push notification dispatch.

## Steps
1. Trigger the specific beckn or logistics event.
2. Assert that the external gateway (e.g. Map API or ONDC Gateway) is called with the correct payload by spying on the outgoing integration bean.
