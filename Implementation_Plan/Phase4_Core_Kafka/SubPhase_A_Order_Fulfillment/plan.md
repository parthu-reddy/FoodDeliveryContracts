# SubPhase 4A: Order Fulfillment Kafka Validations

## Objective
Replace empty `@AutoConfigureStubRunner` shell tests in the core fulfillment domains with actual assertions.

## Target Implementations
1. **`CustomerApplication`** 
   - `OrderEventConsumerTest.java`: Trigger `order-events` and assert order status changes in the local DB.
   - `MenuCacheInvalidationListenerTest.java`: Trigger `restaurant-events` and assert cache invalidation behavior.
   
2. **`RestaurantApplication`** 
   - `OrderEventConsumerTest.java`: Trigger `order-events` and assert restaurant order state.

3. **`DeliveryExecutiveApplication`**
   - `OrderEventConsumerTest.java`: Trigger `order-events` and assert logistics state.

## Steps
1. In the `@Test` method, use `stubTrigger.trigger("label")` to fire the Kafka message.
2. Introduce `Awaitility` or `Thread.sleep` to allow async `@KafkaListener` processing.
3. Fetch the record from the repository/database or verify mock interactions to ensure the event was consumed and state was mutated correctly.
