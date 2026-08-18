package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send order-events events")
    label("order_created")
    input {
        triggeredBy('fireOrderCreated()')
    }
    outputMessage {
        sentTo('order-events')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "ORDER_CREATED",
            payload: [
                orderId: 1001,
                customerId: "user-123",
                restaurantId: 501,
                totalAmount: 15.50
            ]
        ])
    }
}
