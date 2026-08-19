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
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "AD_DISPLAYED",
            payload: [
                campaignId: 999,
                userId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}')))
            ]
        ])
    }
}
