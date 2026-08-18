import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should initiate login via Identity Service")
    request {
        method 'POST'
        urlPath('/api/v1/internal/auth/initiate') {
            queryParameters {
                parameter 'phoneNumber': '+1234567890'
            }
        }
        headers {
            header('X-Calling-Service': 'gateway')
        }
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            success: true,
            data: "OTP sent successfully",
            message: "Success"
        ])
    }
}
