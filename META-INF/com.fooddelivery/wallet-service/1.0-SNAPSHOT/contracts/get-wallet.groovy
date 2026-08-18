import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should return wallet balance for valid entity")
    request {
        method 'GET'
        url('/api/v1/wallets/customer/123e4567-e89b-12d3-a456-426614174000')
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            id: $(uuid()),
            entityType: "customer",
            entityId: "123e4567-e89b-12d3-a456-426614174000",
            balance: 500.00
        ])
    }
}
