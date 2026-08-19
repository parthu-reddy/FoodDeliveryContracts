import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should return driver details")
    request {
        method 'GET'
        urlPath('/api/v1/internal/admin/delivery/drivers/123e4567-e89b-12d3-a456-426614174000')
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            driverId: "123e4567-e89b-12d3-a456-426614174000",
            name: "John Doe",
            status: "AVAILABLE",
            vehicleType: "BIKE"
        ])
    }
}
