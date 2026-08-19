import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should return details for a batch of drivers")
    request {
        method 'POST'
        urlPath('/api/v1/internal/admin/delivery/drivers/batch')
        headers {
            contentType(applicationJson())
        }
        body([
            "123e4567-e89b-12d3-a456-426614174000",
            "123e4567-e89b-12d3-a456-426614174001"
        ])
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            [
                driverId: "123e4567-e89b-12d3-a456-426614174000",
                name: "John Doe",
                status: "AVAILABLE"
            ],
            [
                driverId: "123e4567-e89b-12d3-a456-426614174001",
                name: "Jane Smith",
                status: "ON_DELIVERY"
            ]
        ])
    }
}
