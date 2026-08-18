package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send ondc-order-created events")
    label("ondc_order_created")
    input {
        triggeredBy('fireOndcOrderCreated()')
    }
    outputMessage {
        sentTo('ondc-order-created')
        body([
            eventId: "ondc-999",
            type: "ONDC_ORDER_CREATED",
            payload: [
                networkOrderId: "nw-100",
                localOrderId: 1001
            ]
        ])
    }
}
