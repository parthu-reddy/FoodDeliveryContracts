package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send payment-events events")
    label("payment_events")
    input {
        triggeredBy('firePaymentSuccess()')
    }
    outputMessage {
        sentTo('payment-events')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "PAYMENT_SUCCESS",
            payload: [
                orderId: 1001,
                paymentId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
                amount: 15.50
            ]
        ])
    }
}
