import org.springframework.cloud.contract.spec.Contract

Contract.make {
    description("Should reverse geocode coordinates")
    request {
        method 'GET'
        urlPath('/api/places/reverse-geocode') {
            queryParameters {
                parameter 'lat': '12.971598'
                parameter 'lng': '77.594562'
            }
        }
    }
    response {
        status OK()
        headers {
            contentType(applicationJson())
        }
        body([
            address: "Bangalore, Karnataka, India"
        ])
    }
}
