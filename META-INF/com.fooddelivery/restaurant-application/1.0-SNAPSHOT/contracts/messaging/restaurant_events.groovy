package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send restaurant-events events")
    label("restaurant_events")
    input {
        triggeredBy('fireRestaurantAccepted()')
    }
    outputMessage {
        sentTo('restaurant-events')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "ORDER_ACCEPTED",
            payload: [
                orderId: 1001,
                restaurantId: 501
            ]
        ])
    }
}
