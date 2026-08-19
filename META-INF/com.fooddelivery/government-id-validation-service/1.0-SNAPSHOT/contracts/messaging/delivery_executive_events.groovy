package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send delivery-executive-events events")
    label("delivery_executive_events")
    input {
        triggeredBy('fireExecutiveValidated()')
    }
    outputMessage {
        sentTo('delivery-executive-events')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "EXECUTIVE_VALIDATED",
            payload: [
                executiveId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
                status: "APPROVED"
            ]
        ])
    }
}
