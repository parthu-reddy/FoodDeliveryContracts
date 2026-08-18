package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send ad-events events")
    label("ad_events")
    input {
        triggeredBy('fireAdEvent()')
    }
    outputMessage {
        sentTo('ad-events')
        body([
            eventId: "ad-333",
            type: "AD_DISPLAYED",
            payload: [
                campaignId: 999,
                userId: "user-123"
            ]
        ])
    }
}
