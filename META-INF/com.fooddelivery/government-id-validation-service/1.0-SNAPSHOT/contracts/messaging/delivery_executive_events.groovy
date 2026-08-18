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
            eventId: "gov-888",
            type: "EXECUTIVE_VALIDATED",
            payload: [
                executiveId: "exec-777",
                status: "APPROVED"
            ]
        ])
    }
}
