package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send platform.logistics.dispatch events")
    label("logistics_dispatch")
    input {
        triggeredBy('fireLogisticsDispatch()')
    }
    outputMessage {
        sentTo('platform.logistics.dispatch')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "DISPATCH_ASSIGNED",
            payload: [
                orderId: 1001,
                executiveId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}')))
            ]
        ])
    }
}
