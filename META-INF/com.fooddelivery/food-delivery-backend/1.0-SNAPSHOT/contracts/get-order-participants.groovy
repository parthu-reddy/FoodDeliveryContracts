import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should return order participants")
    request {
        method 'GET'
        urlPath('/api/v1/internal/orders/1001/participants')
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            orderId: 1001,
            customerId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            deliveryExecutiveId: $(producer(regex('[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'))),
            restaurantId: 501
        ])
    }
}
