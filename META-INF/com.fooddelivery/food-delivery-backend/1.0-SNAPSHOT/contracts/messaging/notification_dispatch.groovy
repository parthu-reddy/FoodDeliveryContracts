package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send platform.notifications.dispatch events")
    label("notification_dispatch")
    input {
        triggeredBy('fireNotificationDispatch()')
    }
    outputMessage {
        sentTo('platform.notifications.dispatch')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "NOTIFICATION_SENT",
            payload: [
                userId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
                message: "Your order is confirmed."
            ]
        ])
    }
}
