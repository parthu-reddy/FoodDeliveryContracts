import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should create an order in payment service")
    request {
        method 'POST'
        urlPath('/api/v1/payments/create-order') {
            queryParameters {
                parameter 'gateway': 'RAZORPAY'
            }
        }
        headers {
            contentType(applicationJson())
        }
        body([
            internalOrderId: "123e4567-e89b-12d3-a456-426614174000",
            amountInInr: 50.00
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
