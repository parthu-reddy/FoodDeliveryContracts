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
            eventId: "map-777",
            type: "DISPATCH_CANDIDATE_FOUND",
            payload: [
                orderId: 1001,
                candidateId: "exec-777"
            ]
        ])
    }
}
