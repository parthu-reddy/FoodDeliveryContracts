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
            eventId: "not-444",
            type: "NOTIFICATION_SENT",
            payload: [
                userId: "user-123",
                message: "Your order is confirmed."
            ]
        ])
    }
}
