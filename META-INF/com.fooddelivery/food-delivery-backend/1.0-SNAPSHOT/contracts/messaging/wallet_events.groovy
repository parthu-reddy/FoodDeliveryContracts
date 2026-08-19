package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send wallet-events events")
    label("wallet_events")
    input {
        triggeredBy('fireWalletEvent()')
    }
    outputMessage {
        sentTo('wallet-events')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "WALLET_DEBITED",
            payload: [
                userId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
                amount: 15.50
            ]
        ])
    }
}
