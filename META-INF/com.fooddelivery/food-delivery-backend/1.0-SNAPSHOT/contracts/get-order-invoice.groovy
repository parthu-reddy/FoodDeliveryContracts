import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should return order invoice details")
    request {
        method 'GET'
        urlPath('/api/v1/internal/orders/123e4567-e89b-12d3-a456-426614174000/invoice')
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            orderId: "123e4567-e89b-12d3-a456-426614174000",
            totalAmount: 45.99,
            tax: 2.50,
            status: "PAID"
        ])
    }
}
