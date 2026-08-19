package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send menu-events events")
    label("menu_events")
    input {
        triggeredBy('fireMenuUpdated()')
    }
    outputMessage {
        sentTo('menu-events')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "MENU_UPDATED",
            payload: [
                restaurantId: 501,
                itemId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}')))
            ]
        ])
    }
}
