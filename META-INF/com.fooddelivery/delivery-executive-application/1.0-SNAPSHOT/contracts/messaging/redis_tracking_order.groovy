package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should publish telemetry event to Redis channel tracking:order:{orderId}")
    label("redis_tracking_order")
    input {
        triggeredBy('fireTelemetryEvent()')
    }
    outputMessage {
        sentTo('tracking:order:1001')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "TELEMETRY_UPDATED",
            payload: [
                orderId: 1001,
                deliveryExecutiveId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
                lat: 12.971598,
                lng: 77.594562
            ]
        ])
    }
}
