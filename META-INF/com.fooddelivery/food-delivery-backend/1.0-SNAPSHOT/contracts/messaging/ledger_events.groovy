package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send ledger-events events")
    label("ledger_events")
    input {
        triggeredBy('fireLedgerEvent()')
    }
    outputMessage {
        sentTo('ledger-events')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "LEDGER_ENTRY_CREATED",
            payload: [
                transactionId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
                amount: 15.50
            ]
        ])
    }
}
