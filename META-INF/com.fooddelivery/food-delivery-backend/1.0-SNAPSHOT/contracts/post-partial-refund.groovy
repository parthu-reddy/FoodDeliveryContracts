import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should initiate a partial refund for an order")
    request {
        method 'POST'
        urlPath('/api/v1/internal/orders/123e4567-e89b-12d3-a456-426614174000/partial-refund')
        headers {
            contentType(applicationJson())
        }
        body([
            amount: "15.50",
            reason: "Missing item"
        ])
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            status: "SUCCESS",
            refundId: "ref-999"
        ])
    }
}
