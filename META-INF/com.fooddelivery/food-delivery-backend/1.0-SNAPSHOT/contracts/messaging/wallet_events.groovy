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
            eventId: "wal-111",
            type: "WALLET_DEBITED",
            payload: [
                userId: "user-123",
                amount: 15.50
            ]
        ])
    }
}
