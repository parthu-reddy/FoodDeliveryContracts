package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send order-events events")
    label("order_events_dispatch")
    input {
        triggeredBy('fireDispatchCandidateFound()')
    }
    outputMessage {
        sentTo('order-events')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "DISPATCH_CANDIDATE_FOUND",
            payload: [
                orderId: 1001,
                candidateId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}')))
            ]
        ])
    }
}
