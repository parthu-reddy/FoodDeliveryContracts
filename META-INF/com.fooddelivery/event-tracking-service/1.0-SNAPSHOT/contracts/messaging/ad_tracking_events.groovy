package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send ad-tracking-events events")
    label("ad_tracking_events")
    input {
        triggeredBy('fireAdTracking()')
    }
    outputMessage {
        sentTo('ad-tracking-events')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "AD_CLICKED",
            payload: [
                campaignId: 999,
                userId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}')))
            ]
        ])
    }
}
