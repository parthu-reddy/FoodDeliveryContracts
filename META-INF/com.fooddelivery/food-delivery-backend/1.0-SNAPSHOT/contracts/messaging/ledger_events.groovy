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
            eventId: "led-222",
            type: "LEDGER_ENTRY_CREATED",
            payload: [
                transactionId: "txn-999",
                amount: 15.50
            ]
        ])
    }
}
