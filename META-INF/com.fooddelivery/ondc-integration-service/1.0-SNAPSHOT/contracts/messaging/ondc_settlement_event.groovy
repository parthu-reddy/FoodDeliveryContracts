package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send ondc-settlement-event events")
    label("ondc_settlement_event")
    input {
        triggeredBy('fireOndcSettlementEvent()')
    }
    outputMessage {
        sentTo('ondc-settlement-event')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "ONDC_SETTLEMENT_PROCESSED",
            payload: [
                networkOrderId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
                settlementId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
                amount: 15.50
            ]
        ])
    }
}
