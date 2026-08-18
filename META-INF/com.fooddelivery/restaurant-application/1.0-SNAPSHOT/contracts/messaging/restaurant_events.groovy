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
            eventId: "res-222",
            type: "ORDER_ACCEPTED",
            payload: [
                orderId: 1001,
                restaurantId: 501
            ]
        ])
    }
}
