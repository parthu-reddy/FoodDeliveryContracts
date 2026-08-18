import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should create an order in payment service")
    request {
        method 'POST'
        urlPath('/api/v1/payments/create-order') {
            queryParameters {
                parameter 'gateway': 'STRIPE'
            }
        }
        headers {
            contentType(applicationJson())
        }
        body([
            orderId: 1001,
            amount: 50.00,
            currency: "USD"
        ])
    }
    response {
        status OK()
        headers {
            contentType(textPlain())
        }
        body("PAYMENT_LINK_URL")
    }
}
