package contracts.messaging

org.springframework.cloud.contract.spec.Contract.make {
    description("Should send ad-billing-events events")
    label("ad_billing_events")
    input {
        triggeredBy('fireAdBilling()')
    }
    outputMessage {
        sentTo('ad-billing-events')
        body([
            eventId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            type: "AD_CLICK_BILLED",
            payload: [
                campaignId: 999,
                cost: 0.50
            ]
        ])
    }
}
