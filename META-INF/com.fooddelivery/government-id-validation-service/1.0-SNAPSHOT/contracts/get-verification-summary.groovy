import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should return verification summary")
    request {
        method 'GET'
        url('/api/v1/verification/status/123e4567-e89b-12d3-a456-426614174000')
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            allDocsApproved: true,
            bankApproved: true,
            dlVehicleClass: "LMV",
            dlApproved: true,
            rcApproved: true,
            lastBiometricVerificationAt: "2023-10-01T12:00:00Z"
        ])
    }
}
