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
            eventId: "menu-333",
            type: "MENU_UPDATED",
            payload: [
                restaurantId: 501,
                itemId: "item-88"
            ]
        ])
    }
}
