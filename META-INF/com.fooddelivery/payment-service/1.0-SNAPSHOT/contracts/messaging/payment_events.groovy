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
            eventId: "pay-111",
            type: "PAYMENT_SUCCESS",
            payload: [
                orderId: 1001,
                paymentId: "txn-999",
                amount: 15.50
            ]
        ])
    }
}
