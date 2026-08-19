import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should return restaurant outlets")
    request {
        method 'GET'
        urlPath('/api/v1/internal/restaurants/owner/550e8400-e29b-41d4-a716-446655440000/outlets')
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            [
                outletId: 501,
                name: "Pizza Hub Downtown",
                status: "ACTIVE"
            ],
            [
                outletId: 502,
                name: "Pizza Hub Uptown",
                status: "ACTIVE"
            ]
        ])
    }
}
