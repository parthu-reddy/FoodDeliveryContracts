import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should return daily budgets for a batch of campaigns")
    
    request {
        method 'POST'
        url '/api/v1/internal/campaigns/batch/budgets'
        body(["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"])
        headers {
            contentType('application/json')
        }
    }
    
    response {
        status 200
        body([
            "11111111-1111-1111-1111-111111111111": [
                dailyBudget: 500.00,
                advertiserId: "550e8400-e29b-41d4-a716-446655440000"
            ],
            "22222222-2222-2222-2222-222222222222": [
                dailyBudget: 1500.50,
                advertiserId: "550e8400-e29b-41d4-a716-446655440001"
            ]
        ])
        headers {
            contentType('application/json')
        }
    }
}
